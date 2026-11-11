from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

import duckdb


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
sys.path[:0] = [str(ROOT / "src"), str(OFFICIAL)]

from Algorithms.LExaShap.ShapleyCircuit import (  # noqa: E402
    DNFCircuit,
    DNFCircuitNode,
    lift_recursively,
)
from Algorithms.LExaShap.ShapleyEngine import Value  # noqa: E402
from aggregate_report_shapley.d1p import all_incremental_states, load_d1p_spec  # noqa: E402
from aggregate_report_shapley.d1p_sql import create_d1p_database  # noqa: E402
from aggregate_report_shapley.d1p_values import D1PValueSuite  # noqa: E402
from aggregate_report_shapley.exact_shapley import exact_shapley_subset  # noqa: E402


OUT = ROOT / "outputs" / "v4_0" / "AB_N2_AB_J1_2026_10_31"
N1_OUT = OUT / "AB_N1_SUPPLEMENT"
N2_OUT = OUT / "AB_N2"
J1_OUT = OUT / "AB_J1"
N4_OUT = OUT / "AB_N4_STRUCTURE_AUDIT"
HISTORICAL_N1 = (
    ROOT / "outputs" / "v4_0" / "AB_NATIVE_SQL" / "ab_n1_minimal_validation.json",
    ROOT / "outputs" / "v4_0" / "AB_NATIVE_SQL" / "ab_n1_source_expression.json",
    ROOT / "reports" / "Abramovich原生SQL最小适配验证_2026-10-31.md",
    ROOT / "experiments" / "AB_native_SQL_experiment_protocol_2026-10-31.md",
)
METRICS = ("record_count", "category_a_target_count", "attribute_present_count")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"不能写入空CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def process_rss_bytes() -> int | None:
    try:
        import psutil

        return int(psutil.Process().memory_info().rss)
    except (ImportError, OSError):
        return None


def stage_memory_start() -> tuple[int | None, int]:
    gc.collect()
    tracemalloc.reset_peak()
    return process_rss_bytes(), tracemalloc.get_traced_memory()[0]


def stage_memory_end(start: tuple[int | None, int]) -> dict[str, int | None]:
    rss_end = process_rss_bytes()
    current, peak = tracemalloc.get_traced_memory()
    return {
        "rss_start_bytes": start[0],
        "rss_end_bytes": rss_end,
        "rss_observed_change_bytes": None if start[0] is None or rss_end is None else rss_end - start[0],
        "python_tracemalloc_start_bytes": start[1],
        "python_tracemalloc_end_bytes": current,
        "python_tracemalloc_peak_bytes": peak,
    }


def official_scalar(dnf: list[set[str]]) -> dict[str, float]:
    circuit = DNFCircuit(dnf)
    scale = (2 ** len(circuit.vars)) / math.factorial(len(circuit.vars))
    return {
        str(value.label): sum(float(g) * float(p) for g, p in zip(value.grad, value.prob)) * scale
        for value in circuit.vars
    }


def instrumented_official_scalar(dnf: list[set[str]]) -> tuple[dict[str, float], float, float]:
    """Separate official d-tree construction and backward solve without editing source."""
    started = time.perf_counter()
    labels = {item for clause in dnf for item in clause}
    values = {label: Value(0.5, {label}, label=label) for label in labels}
    lifted = lift_recursively([{values[label] for label in clause} for clause in dnf])
    DNFCircuitNode.start_time = time.time()
    root = DNFCircuitNode(lifted, "root")
    root.recursively_expand()
    compile_seconds = time.perf_counter() - started
    started = time.perf_counter()
    root.value.backward()
    solve_seconds = time.perf_counter() - started
    scale = (2 ** len(values)) / math.factorial(len(values))
    scalar = {
        str(value.label): sum(float(g) * float(p) for g, p in zip(value.grad, value.prob)) * scale
        for value in values.values()
    }
    return scalar, compile_seconds, solve_seconds


def run_component(
    dnf: list[set[str]], coefficient: Fraction
) -> tuple[dict[str, float], dict[str, float]]:
    started = time.perf_counter()
    untouched = official_scalar(dnf)
    untouched_seconds = time.perf_counter() - started
    instrumented, compile_seconds, solve_seconds = instrumented_official_scalar(dnf)
    if untouched.keys() != instrumented.keys() or any(
        abs(untouched[key] - instrumented[key]) > 1e-12 for key in untouched
    ):
        raise AssertionError("未修改官方构造器与分阶段计时harness不一致")
    return (
        {player: float(coefficient) * value for player, value in untouched.items()},
        {
            "official_untouched_end_to_end_seconds": untouched_seconds,
            "official_dtree_compile_seconds": compile_seconds,
            "official_backward_solve_seconds": solve_seconds,
        },
    )


def d1p_base_sql() -> str:
    return """
        SELECT * FROM BasicSource_A1
        UNION ALL SELECT * FROM BasicSource_A2
        UNION ALL SELECT * FROM BasicSource_B1
        UNION ALL SELECT * FROM BasicSource_B2
    """.strip()


def audit_n1(connection: duckdb.DuckDBPyConnection, player_count: int) -> dict[str, Any]:
    stage_started = time.perf_counter()
    memory_start = stage_memory_start()
    base = d1p_base_sql()
    raw_sql = f"""
    WITH masks AS (SELECT range AS mask FROM range({1 << player_count})),
    base AS ({base})
    SELECT m.mask,
           (SELECT COUNT(*) FROM base b
             WHERE b.leaf_node_id='A1' AND ((m.mask >> b.player_index) & 1)=1) AS raw_count,
           (SELECT SUM(CASE WHEN b.category_a_id='E2' THEN 1 ELSE 0 END) FROM base b
             WHERE b.leaf_node_id='A1' AND ((m.mask >> b.player_index) & 1)=1) AS raw_sum
    FROM masks m
    ORDER BY m.mask
    """
    started = time.perf_counter()
    rows = connection.execute(raw_sql).fetchall()
    sql_seconds = time.perf_counter() - started
    plan = "\n".join(str(row[-1]) for row in connection.execute("EXPLAIN " + raw_sql).fetchall())
    validation: list[dict[str, Any]] = []
    null_count = 0
    max_count_error = 0
    max_sum_error = 0
    for mask, raw_count, raw_sum in rows:
        mask = int(mask)
        expression_count = int(bool(mask & 1)) + int(bool(mask & 2))
        expression_sum = int(bool(mask & 2))
        normalized_sum = 0 if raw_sum is None else int(raw_sum)
        null_count += int(raw_sum is None)
        max_count_error = max(max_count_error, abs(int(raw_count) - expression_count))
        max_sum_error = max(max_sum_error, abs(normalized_sum - expression_sum))
        validation.append(
            {
                "mask": mask,
                "coalition_size": mask.bit_count(),
                "has_A1_record": bool(mask & 0b11),
                "raw_sql_count": int(raw_count),
                "raw_sql_sum": raw_sum,
                "normalized_sum_after_explicit_coalesce": normalized_sum,
                "source_expression_count": expression_count,
                "source_expression_sum": expression_sum,
                "count_error": int(raw_count) - expression_count,
                "normalized_sum_error": normalized_sum - expression_sum,
            }
        )
    if len(rows) != 4096 or null_count != 1024 or max_count_error != 0 or max_sum_error != 0:
        raise AssertionError("AB-N1 NULL/空联盟补充审计失败")
    empty = validation[0]
    p1_only = validation[1]
    if empty["raw_sql_sum"] is not None or p1_only["raw_sql_sum"] != 0:
        raise AssertionError("原始SUM边界行为不符合SQL语义")
    write_csv(N1_OUT / "ab_n1_alliance_sql_null_audit.csv", validation)
    result = {
        "stage": "AB-N1-SUPPLEMENT",
        "status": "AUDITED_EXPLICIT_NULL_TO_ZERO_BOUNDARY_REQUIRED",
        "raw_sql": raw_sql.strip(),
        "raw_sql_sha256": hashlib.sha256(raw_sql.encode("utf-8")).hexdigest(),
        "duckdb_version": duckdb.__version__,
        "sql_execution_plan": plan,
        "sql_rows_returned": len(rows),
        "sql_execution_seconds": sql_seconds,
        "empty_coalition": empty,
        "coalitions_without_A1_records": 1024,
        "raw_sum_null_count": null_count,
        "p1_only_nonempty_but_no_E2": p1_only,
        "normalization_policy": "原始SUM保持NULL；进入数值价值/评分边界时显式COALESCE(raw_sum,0)。",
        "historical_oracle_finding": (
            "历史AB-N1的4096联盟oracle确实由DuckDB SQL执行，但在oracle SQL内部使用COALESCE，"
            "没有同时保存原始NULL列；数值游戏正确，SQL语义审计记录不完整。"
        ),
        "maximum_count_error": max_count_error,
        "maximum_normalized_sum_error": max_sum_error,
        "stage_wall_seconds": time.perf_counter() - stage_started,
        "memory": stage_memory_end(memory_start),
    }
    json_write(N1_OUT / "audit.json", result)
    return result


def n2_grounding_sql() -> str:
    base = d1p_base_sql()
    return f"""
    WITH base AS ({base}),
    joined AS (
        SELECT b.player_index, b.record_id, b.leaf_node_id, b.category_a_id,
               o.record_id AS optional_record_id, o.category_b_id
        FROM base b
        LEFT JOIN OptionalAttribute o USING (record_id)
    )
    SELECT j.player_index, j.record_id, nodes.node_id,
           1::BIGINT AS record_count_coefficient,
           CASE WHEN j.category_a_id='E2' THEN 1 ELSE 0 END::BIGINT AS category_a_target_count_coefficient,
           CASE WHEN j.optional_record_id IS NOT NULL THEN 1 ELSE 0 END::BIGINT AS attribute_present_count_coefficient,
           j.optional_record_id
    FROM joined j
    JOIN Hierarchy h USING (leaf_node_id)
    CROSS JOIN UNNEST([j.leaf_node_id, h.parent_node_id, h.root_node_id]) AS nodes(node_id)
    ORDER BY j.player_index, nodes.node_id
    """.strip()


def n2_oracle_sql(player_count: int, nodes: tuple[str, ...]) -> str:
    base = d1p_base_sql()
    node_values = ",".join(f"('{node}')" for node in nodes)
    return f"""
    WITH masks AS (SELECT range AS mask FROM range({1 << player_count})),
    base AS ({base}),
    joined AS (
        SELECT b.player_index, b.record_id, b.leaf_node_id, b.category_a_id,
               o.record_id AS optional_record_id
        FROM base b
        LEFT JOIN OptionalAttribute o USING (record_id)
    ),
    expanded AS (
        SELECT j.player_index, j.record_id, j.category_a_id, j.optional_record_id, nodes.node_id
        FROM joined j
        JOIN Hierarchy h USING (leaf_node_id)
        CROSS JOIN UNNEST([j.leaf_node_id, h.parent_node_id, h.root_node_id]) AS nodes(node_id)
    ),
    report_nodes(node_id) AS (VALUES {node_values})
    SELECT m.mask, n.node_id,
           COUNT(e.record_id)::BIGINT AS record_count,
           COUNT(CASE WHEN e.category_a_id='E2' THEN 1 END)::BIGINT AS category_a_target_count,
           COUNT(e.optional_record_id)::BIGINT AS attribute_present_count
    FROM masks m
    CROSS JOIN report_nodes n
    LEFT JOIN expanded e
      ON e.node_id=n.node_id AND ((m.mask >> e.player_index) & 1)=1
    GROUP BY m.mask, n.node_id
    ORDER BY m.mask, n.node_id
    """.strip()


def run_n2(connection: duckdb.DuckDBPyConnection, spec) -> dict[str, Any]:
    stage_started = time.perf_counter()
    memory_start = stage_memory_start()
    grounding_sql = n2_grounding_sql()
    started = time.perf_counter()
    grounding = connection.execute(grounding_sql).fetchall()
    grounding_sql_seconds = time.perf_counter() - started
    grounding_rows: list[dict[str, Any]] = []
    components: dict[tuple[str, str], list[tuple[list[set[str]], Fraction]]] = defaultdict(list)
    started = time.perf_counter()
    for player_index, record_id, node, count_c, e2_c, attr_c, optional_record_id in grounding:
        coefficients = {
            "record_count": int(count_c),
            "category_a_target_count": int(e2_c),
            "attribute_present_count": int(attr_c),
        }
        grounding_rows.append(
            {
                "player_index": int(player_index),
                "record_id": str(record_id),
                "node": str(node),
                **{f"{metric}_coefficient": value for metric, value in coefficients.items()},
                "optional_row_present": optional_record_id is not None,
            }
        )
        for metric, coefficient in coefficients.items():
            if coefficient:
                components[(str(node), metric)].append(([{str(record_id)}], Fraction(coefficient)))
    source_assembly_seconds = time.perf_counter() - started
    component_counts = Counter(metric for (_node, metric), items in components.items() for _ in items)
    expected = {
        "record_count": 36,
        "category_a_target_count": 18,
        "attribute_present_count": 30,
    }
    if len(grounding_rows) != 36 or dict(component_counts) != expected:
        raise AssertionError(f"AB-N2组件数不符: {dict(component_counts)}")

    base_stats = connection.execute(
        f"""
        WITH base AS ({d1p_base_sql()})
        SELECT COUNT(*) AS rows, COUNT(DISTINCT record_id) AS distinct_records,
               COUNT(DISTINCT player_index) AS distinct_player_indexes
        FROM base
        """
    ).fetchone()
    optional_stats = connection.execute(
        "SELECT COUNT(*), COUNT(DISTINCT record_id) FROM OptionalAttribute"
    ).fetchone()
    joined_stats = connection.execute(
        f"""
        WITH base AS ({d1p_base_sql()})
        SELECT COUNT(*) AS joined_rows, COUNT(DISTINCT b.record_id) AS distinct_records,
               COUNT(CASE WHEN o.record_id IS NULL THEN 1 END) AS missing_optional_preserved
        FROM base b LEFT JOIN OptionalAttribute o USING(record_id)
        """
    ).fetchone()
    duplicate_check_rows = connection.execute(
        f"""
        WITH base AS ({d1p_base_sql()}), joined AS (
          SELECT b.record_id, b.leaf_node_id FROM base b LEFT JOIN OptionalAttribute o USING(record_id)
        ), expanded AS (
          SELECT j.record_id, nodes.node_id FROM joined j JOIN Hierarchy h USING(leaf_node_id)
          CROSS JOIN UNNEST([j.leaf_node_id,h.parent_node_id,h.root_node_id]) nodes(node_id)
        )
        SELECT node_id, COUNT(*) AS bag_count, COUNT(DISTINCT record_id) AS distinct_count
        FROM expanded GROUP BY node_id ORDER BY node_id
        """
    ).fetchall()
    if base_stats != (12, 12, 12) or optional_stats != (10, 10) or joined_stats != (12, 12, 2):
        raise AssertionError("AB-N2玩家绑定或LEFT JOIN关卡失败")
    if any(int(bag) != int(distinct) for _node, bag, distinct in duplicate_check_rows):
        raise AssertionError("冻结D1-P意外出现JOIN重复")
    if any(sum(row[f"{metric}_coefficient"] for row in grounding_rows if row["record_id"] == record.record_id) not in (0, 3)
           for record in spec.records for metric in METRICS):
        raise AssertionError("同一玩家的三层级贡献计数异常")

    expression_payload: dict[str, list[dict[str, Any]]] = {}
    official_payments: dict[tuple[str, str], dict[str, float]] = {}
    timing_totals = {
        "official_untouched_end_to_end_seconds": 0.0,
        "official_dtree_compile_seconds": 0.0,
        "official_backward_solve_seconds": 0.0,
    }
    for node in spec.nodes:
        for metric in METRICS:
            key = (node, metric)
            official_payments[key] = {record.record_id: 0.0 for record in spec.records}
            expression_payload[f"{node}|{metric}"] = []
            for dnf, coefficient in components.get(key, []):
                payment, timing = run_component(dnf, coefficient)
                for name in timing_totals:
                    timing_totals[name] += timing[name]
                for player, value in payment.items():
                    official_payments[key][player] += value
                expression_payload[f"{node}|{metric}"].append(
                    {"dnf": [sorted(clause) for clause in dnf], "coefficient": fraction_text(coefficient)}
                )

    oracle_sql = n2_oracle_sql(spec.player_count, spec.nodes)
    started = time.perf_counter()
    oracle = connection.execute(oracle_sql).fetchall()
    oracle_sql_seconds = time.perf_counter() - started
    if len(oracle) != (1 << spec.player_count) * len(spec.nodes):
        raise AssertionError("AB-N2最终报表骨架未返回全部mask×node")
    raw_group_sql = f"""
    WITH masks AS (SELECT range AS mask FROM range({1 << spec.player_count})),
    base AS ({d1p_base_sql()}),
    joined AS (
      SELECT b.player_index,b.record_id,b.leaf_node_id,b.category_a_id,o.record_id AS optional_record_id
      FROM base b LEFT JOIN OptionalAttribute o USING(record_id)
    ), expanded AS (
      SELECT j.*,nodes.node_id FROM joined j JOIN Hierarchy h USING(leaf_node_id)
      CROSS JOIN UNNEST([j.leaf_node_id,h.parent_node_id,h.root_node_id]) nodes(node_id)
    )
    SELECT m.mask,e.node_id,COUNT(*) FROM masks m JOIN expanded e
      ON ((m.mask >> e.player_index)&1)=1
    GROUP BY m.mask,e.node_id
    """
    raw_group_rows = connection.execute(raw_group_sql).fetchall()

    contribution_counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for key, items in components.items():
        for dnf, coefficient in items:
            contribution_counters[key][next(iter(dnf[0]))] += int(coefficient)
    tables: dict[tuple[str, str], list[int]] = {
        (node, metric): [0] * (1 << spec.player_count) for node in spec.nodes for metric in METRICS
    }
    validation_rows: list[dict[str, Any]] = []
    max_value_error = 0
    for mask, node, count_value, e2_value, attr_value in oracle:
        mask = int(mask)
        values = {
            "record_count": int(count_value),
            "category_a_target_count": int(e2_value),
            "attribute_present_count": int(attr_value),
        }
        for metric, sql_value in values.items():
            key = (str(node), metric)
            tables[key][mask] = sql_value
            expression_value = sum(
                coefficient
                for player, coefficient in contribution_counters[key].items()
                if mask & (1 << next(r.player_index for r in spec.records if r.record_id == player))
            )
            error = expression_value - sql_value
            max_value_error = max(max_value_error, abs(error))
            validation_rows.append(
                {
                    "mask": mask,
                    "coalition_size": mask.bit_count(),
                    "node": str(node),
                    "metric": metric,
                    "sql_value": sql_value,
                    "source_expression_value": expression_value,
                    "error": error,
                }
            )
    if max_value_error != 0:
        raise AssertionError("AB-N2来源表达与SQL联盟值不一致")

    started = time.perf_counter()
    shapley_rows: list[dict[str, Any]] = []
    max_payment_error = 0.0
    max_efficiency_error = 0.0
    for node in spec.nodes:
        for metric in METRICS:
            key = (node, metric)
            exact = exact_shapley_subset([Fraction(value) for value in tables[key]], spec.player_count)
            official_sum = sum(official_payments[key].values())
            efficiency_target = tables[key][-1] - tables[key][0]
            max_efficiency_error = max(max_efficiency_error, abs(official_sum - efficiency_target))
            for index, record in enumerate(spec.records):
                estimate = official_payments[key][record.record_id]
                error = estimate - float(exact[index])
                max_payment_error = max(max_payment_error, abs(error))
                shapley_rows.append(
                    {
                        "node": node,
                        "metric": metric,
                        "record_id": record.record_id,
                        "player_index": record.player_index,
                        "official_shapley": estimate,
                        "exact_shapley": fraction_text(exact[index]),
                        "error": error,
                    }
                )
    exact_seconds = time.perf_counter() - started
    if max_payment_error > 1e-12 or max_efficiency_error > 1e-12:
        raise AssertionError("AB-N2官方Shapley关卡失败")

    write_csv(N2_OUT / "grounding.csv", grounding_rows)
    write_csv(N2_OUT / "alliance_node_validation.csv", validation_rows)
    write_csv(N2_OUT / "shapley_comparison.csv", shapley_rows)
    json_write(N2_OUT / "source_expressions.json", expression_payload)
    result = {
        "stage": "AB-N2",
        "status": "FULL_SAME_GAME_NATIVE_SQL_COUNT_VALIDATED",
        "players": [record.record_id for record in spec.records],
        "player_binding": "Basic与OptionalAttribute按record_id共享同一玩家变量；Hierarchy为外生固定关系。",
        "grounding_sql": grounding_sql,
        "oracle_sql": oracle_sql,
        "oracle_sql_sha256": hashlib.sha256(oracle_sql.encode("utf-8")).hexdigest(),
        "oracle_rows": len(oracle),
        "raw_grouped_sql_rows_without_skeleton": len(raw_group_rows),
        "final_report_skeleton_rows": len(oracle),
        "empty_cell_policy": "原始GROUP BY省略空节点；最终报表SQL显式使用mask×node骨架并以COUNT返回0。",
        "null_policy": "OptionalAttribute缺失时optional_record_id为NULL；COUNT(optional_record_id)=0，LEFT JOIN保留基础记录。",
        "identity_checks": {
            "basic_rows_distinct_records_distinct_players": list(base_stats),
            "optional_rows_distinct_records": list(optional_stats),
            "joined_rows_distinct_records_missing_optional_preserved": list(joined_stats),
            "expanded_grounding_rows": len(grounding_rows),
            "distinct_player_variables": len({row["record_id"] for row in grounding_rows}),
            "levels_per_player": 3,
        },
        "duplicate_audit": {
            "frozen_data_has_join_duplicates": False,
            "per_node_count_star_vs_count_distinct": [
                {"node": str(node), "count_star": int(bag), "count_distinct_record_id": int(distinct)}
                for node, bag, distinct in duplicate_check_rows
            ],
            "scope_note": "冻结D1-P没有激活重复JOIN路径；bag与去重语义差异由独立AB-J1检验。",
        },
        "component_counts": dict(component_counts),
        "component_count_total": sum(component_counts.values()),
        "expected_component_counts": expected,
        "source_expression_size": {
            "coordinates": len(spec.nodes) * len(METRICS),
            "components": sum(component_counts.values()),
            "clauses": sum(component_counts.values()),
            "literal_occurrences": sum(component_counts.values()),
            "serialized_utf8_bytes": len(json.dumps(expression_payload, ensure_ascii=False).encode("utf-8")),
        },
        "construction_used_coalition_values": False,
        "construction_used_exact_payments": False,
        "maximum_coalition_value_error": max_value_error,
        "maximum_payment_error": max_payment_error,
        "maximum_efficiency_error": max_efficiency_error,
        "timings_seconds": {
            "sql_grounding": grounding_sql_seconds,
            "source_expression_assembly": source_assembly_seconds,
            **timing_totals,
            "algorithm_end_to_end_excluding_oracles": (
                grounding_sql_seconds
                + source_assembly_seconds
                + timing_totals["official_untouched_end_to_end_seconds"]
            ),
            "posthoc_4096_alliance_sql_oracle": oracle_sql_seconds,
            "posthoc_exact_shapley": exact_seconds,
            "whole_stage_including_csv_and_oracles": time.perf_counter() - stage_started,
        },
        "memory": stage_memory_end(memory_start),
        "official_source_modified": False,
    }
    json_write(N2_OUT / "result.json", result)
    return result


def dnf_value(dnf: list[set[str]], selected: set[str]) -> int:
    return int(any(clause <= selected for clause in dnf))


def run_j1() -> dict[str, Any]:
    stage_started = time.perf_counter()
    memory_start = stage_memory_start()
    connection = duckdb.connect(":memory:")
    connection.execute("CREATE TABLE JLeft(record_id VARCHAR, join_key VARCHAR, output_key VARCHAR)")
    connection.execute("CREATE TABLE JRight(record_id VARCHAR, join_key VARCHAR)")
    connection.executemany("INSERT INTO JLeft VALUES (?, ?, ?)", [("p1", "k", "out"), ("p2", "k", "out")])
    connection.execute("INSERT INTO JRight VALUES ('p3','k')")
    grounding_sql = """
    SELECT l.output_key, l.record_id AS left_player, r.record_id AS right_player
    FROM JLeft l JOIN JRight r USING(join_key)
    ORDER BY left_player, right_player
    """.strip()
    started = time.perf_counter()
    grounding = connection.execute(grounding_sql).fetchall()
    grounding_seconds = time.perf_counter() - started
    if grounding != [("out", "p1", "p3"), ("out", "p2", "p3")]:
        raise AssertionError("AB-J1 grounding不符")
    grounding_rows = [
        {"grounding_id": index + 1, "output_key": output, "left_player": left, "right_player": right,
         "clause": json.dumps(sorted([left, right]))}
        for index, (output, left, right) in enumerate(grounding)
    ]
    bag_components = [([{left, right}], Fraction(1)) for _output, left, right in grounding]
    distinct_dnf = [{left, right} for _output, left, right in grounding]
    expressions = {
        "A_COUNT_STAR_BAG": [
            {"dnf": [sorted(clause) for clause in dnf], "coefficient": "1"}
            for dnf, _coefficient in bag_components
        ],
        "B_COUNT_DISTINCT_KEY_MANUAL_REDUCTION": [
            {"dnf": [sorted(clause) for clause in distinct_dnf], "coefficient": "1"}
        ],
        "C_BOOLEAN_OUTPUT_TUPLE": {"dnf": [sorted(clause) for clause in distinct_dnf]},
    }
    source_assembly_seconds = time.perf_counter() - started - grounding_seconds

    oracle_sql = """
    WITH masks AS (SELECT range AS mask FROM range(8))
    SELECT m.mask,
      (SELECT COUNT(*) FROM JLeft l JOIN JRight r USING(join_key)
        WHERE ((m.mask >> CASE l.record_id WHEN 'p1' THEN 0 ELSE 1 END)&1)=1
          AND ((m.mask >> 2)&1)=1) AS count_star,
      (SELECT COUNT(DISTINCT l.output_key) FROM JLeft l JOIN JRight r USING(join_key)
        WHERE ((m.mask >> CASE l.record_id WHEN 'p1' THEN 0 ELSE 1 END)&1)=1
          AND ((m.mask >> 2)&1)=1) AS count_distinct_key,
      EXISTS(SELECT 1 FROM JLeft l JOIN JRight r USING(join_key)
        WHERE l.output_key='out'
          AND ((m.mask >> CASE l.record_id WHEN 'p1' THEN 0 ELSE 1 END)&1)=1
          AND ((m.mask >> 2)&1)=1) AS boolean_output_tuple
    FROM masks m ORDER BY m.mask
    """.strip()
    started = time.perf_counter()
    oracle = connection.execute(oracle_sql).fetchall()
    oracle_seconds = time.perf_counter() - started
    players = ("p1", "p2", "p3")
    tables = {name: [] for name in ("A_COUNT_STAR_BAG", "B_COUNT_DISTINCT_KEY", "C_BOOLEAN_OUTPUT_TUPLE")}
    validation_rows: list[dict[str, Any]] = []
    for mask, bag_sql, distinct_sql, boolean_sql in oracle:
        selected = {players[index] for index in range(3) if int(mask) & (1 << index)}
        bag_expression = sum(dnf_value(dnf, selected) for dnf, _coefficient in bag_components)
        distinct_expression = dnf_value(distinct_dnf, selected)
        boolean_expression = distinct_expression
        tables["A_COUNT_STAR_BAG"].append(int(bag_sql))
        tables["B_COUNT_DISTINCT_KEY"].append(int(distinct_sql))
        tables["C_BOOLEAN_OUTPUT_TUPLE"].append(int(bool(boolean_sql)))
        validation_rows.append(
            {
                "mask": int(mask),
                "coalition": json.dumps(sorted(selected)),
                "sql_count_star": int(bag_sql),
                "expression_count_star": bag_expression,
                "sql_count_distinct_key": int(distinct_sql),
                "expression_count_distinct_key": distinct_expression,
                "sql_boolean_output_tuple": int(bool(boolean_sql)),
                "expression_boolean_output_tuple": boolean_expression,
            }
        )
    if validation_rows[-1]["sql_count_star"] != 2 or validation_rows[-1]["sql_count_distinct_key"] != 1:
        raise AssertionError("AB-J1未激活bag与distinct差异")
    if any(
        row["sql_count_star"] != row["expression_count_star"]
        or row["sql_count_distinct_key"] != row["expression_count_distinct_key"]
        or row["sql_boolean_output_tuple"] != row["expression_boolean_output_tuple"]
        for row in validation_rows
    ):
        raise AssertionError("AB-J1来源表达与SQL不一致")

    official: dict[str, dict[str, float]] = {
        name: {player: 0.0 for player in players}
        for name in tables
    }
    timing_by_game: dict[str, dict[str, float]] = {}
    for name in tables:
        timing_by_game[name] = {
            "official_untouched_end_to_end_seconds": 0.0,
            "official_dtree_compile_seconds": 0.0,
            "official_backward_solve_seconds": 0.0,
        }
    for dnf, coefficient in bag_components:
        payment, timing = run_component(dnf, coefficient)
        for key, value in timing.items():
            timing_by_game["A_COUNT_STAR_BAG"][key] += value
        for player, value in payment.items():
            official["A_COUNT_STAR_BAG"][player] += value
    for name in ("B_COUNT_DISTINCT_KEY", "C_BOOLEAN_OUTPUT_TUPLE"):
        payment, timing = run_component(distinct_dnf, Fraction(1))
        timing_by_game[name] = timing
        for player, value in payment.items():
            official[name][player] += value

    shapley_rows: list[dict[str, Any]] = []
    max_payment_error = 0.0
    for name, table in tables.items():
        exact = exact_shapley_subset([Fraction(value) for value in table], 3)
        for index, player in enumerate(players):
            estimate = official[name][player]
            error = estimate - float(exact[index])
            max_payment_error = max(max_payment_error, abs(error))
            shapley_rows.append(
                {
                    "game": name,
                    "player": player,
                    "official_shapley": estimate,
                    "exact_shapley": fraction_text(exact[index]),
                    "error": error,
                }
            )
    if max_payment_error > 1e-12:
        raise AssertionError("AB-J1官方Shapley不一致")
    write_csv(J1_OUT / "grounding.csv", grounding_rows)
    write_csv(J1_OUT / "alliance_validation.csv", validation_rows)
    write_csv(J1_OUT / "shapley_comparison.csv", shapley_rows)
    json_write(J1_OUT / "source_expressions.json", expressions)
    result = {
        "stage": "AB-J1",
        "status": "JOIN_BAG_DISTINCT_BOOLEAN_VALIDATED_WITH_INTERFACE_QUALIFICATION",
        "independent_from_d1p": True,
        "players": list(players),
        "grounding_sql": grounding_sql,
        "oracle_sql": oracle_sql,
        "grounding_count": len(grounding),
        "deduplicated_output_keys": 1,
        "full_coalition_values": {"COUNT_STAR": 2, "COUNT_DISTINCT_KEY": 1, "BOOLEAN_TUPLE": 1},
        "maximum_payment_error": max_payment_error,
        "official_support": {
            "A_COUNT_STAR_BAG": {
                "mathematics": "DIRECT_SUM_OF_GROUNDING_DNFS",
                "released_input": "SUPPORTED_AS_LIST_OF_DNFS_AND_COEFFICIENTS",
                "sql_compiler": "MANUAL_MINIMAL_COMPILER",
            },
            "B_COUNT_DISTINCT_KEY": {
                "mathematics": "EXACT_REDUCTION_TO_ONE_BOOLEAN_DNF_PER_DISTINCT_KEY_THEN_SUM",
                "released_input": "NO_EXPLICIT_COUNT_DISTINCT_SQL_INTERFACE; BOOLEAN_DNF_ENGINE_ACCEPTS_REDUCED_INPUT",
                "sql_compiler": "MANUAL_DEDUPLICATION_AND_OR_MERGE",
            },
            "C_BOOLEAN_OUTPUT_TUPLE": {
                "mathematics": "DIRECT_BOOLEAN_DNF",
                "released_input": "SUPPORTED",
                "sql_compiler": "MANUAL_MINIMAL_COMPILER",
            },
        },
        "timings_seconds": {
            "sql_grounding": grounding_seconds,
            "source_expression_assembly": source_assembly_seconds,
            "posthoc_sql_oracle": oracle_seconds,
            "official_by_game": timing_by_game,
            "algorithm_end_to_end_excluding_oracle": (
                grounding_seconds
                + source_assembly_seconds
                + sum(v["official_untouched_end_to_end_seconds"] for v in timing_by_game.values())
            ),
            "whole_stage_including_csv_and_oracle": time.perf_counter() - stage_started,
        },
        "memory": stage_memory_end(memory_start),
        "official_source_modified": False,
    }
    json_write(J1_OUT / "result.json", result)
    return result


def audit_n4_structure(spec, states, suite) -> dict[str, Any]:
    stage_started = time.perf_counter()
    memory_start = stage_memory_start()
    summary_rows: list[dict[str, Any]] = []
    reachable_rows: list[dict[str, Any]] = []
    overall_max_error = Fraction()
    maximum_state_count = 0
    for node in spec.nodes:
        for metric in ("category_a_target_share", "category_b_target_share"):
            if metric == "category_a_target_share":
                full_t = suite.full.counts[node][0]
                full_c = suite.full.counts[node][1]
                state_index = (1, 0)
            else:
                full_t = suite.full.counts[node][2]
                full_c = suite.full.counts[node][3]
                state_index = (3, 2)
            state_counter: Counter[tuple[int, int]] = Counter()
            zero_denominator_cases = 0
            max_error = Fraction()
            for state in states:
                current_c = state.counts[node][state_index[0]]
                current_t = state.counts[node][state_index[1]]
                state_counter[(current_c, current_t)] += 1
                zero_denominator_cases += int(current_t == 0)
                original = suite.coordinate_score(state, node, metric)
                algebraic = Fraction(current_t, full_t) - Fraction(
                    abs(current_c * full_t - current_t * full_c), full_t * full_t
                )
                error = algebraic - original
                max_error = max(max_error, abs(error))
                overall_max_error = max(overall_max_error, abs(error))
            theoretical_states = (full_c + 1) * (full_t - full_c + 1)
            maximum_state_count = max(maximum_state_count, len(state_counter))
            summary_rows.append(
                {
                    "node": node,
                    "metric": metric,
                    "full_denominator_F": full_t,
                    "full_target_C": full_c,
                    "alliances_checked": len(states),
                    "t_equals_zero_cases": zero_denominator_cases,
                    "reachable_count_states": len(state_counter),
                    "theoretical_rectangular_state_bound": theoretical_states,
                    "maximum_identity_error": fraction_text(max_error),
                }
            )
            for (current_c, current_t), count in sorted(state_counter.items()):
                reachable_rows.append(
                    {
                        "node": node,
                        "metric": metric,
                        "c": current_c,
                        "t": current_t,
                        "coalition_count": count,
                    }
                )
    if overall_max_error != 0:
        raise AssertionError("AB-N4比例评分恒等式失败")
    write_csv(N4_OUT / "ratio_identity_summary.csv", summary_rows)
    write_csv(N4_OUT / "reachable_count_states.csv", reachable_rows)
    result = {
        "stage": "AB-N4-STRUCTURE-AUDIT",
        "status": "IDENTITY_VERIFIED_COMPACT_STATE_DP_PLAUSIBLE_NO_N4_ADAPTATION_RUN",
        "alliances_checked_per_coordinate": len(states),
        "ratio_coordinates": len(summary_rows),
        "identity": "score(c,t)=t/F-|cF-tC|/F^2",
        "t_zero_rule": "联盟中t=0时必有c=0，代数式精确给出0，与冻结NULL->score 0约定一致。",
        "maximum_exact_identity_error": fraction_text(overall_max_error),
        "maximum_reachable_count_states": maximum_state_count,
        "dynamic_programming_analysis": {
            "mathematical_representation": (
                "每个比例坐标只依赖(c,t)两个整数计数。可按记录逐步卷积，维护(已处理记录数,c,t,子集大小)的计数，"
                "再按Shapley子集大小权重累加边际；目标/非目标记录还可利用对称性。"
            ),
            "state_bound_per_coordinate": "(C+1)*(F-C+1); 冻结D1-P实测最大49个可达(c,t)状态",
            "complexity_scope": (
                "冻结D1-P为单位计数，F不超过记录数，状态DP对F是多项式；若推广到二进制编码的大整数权重，"
                "同类按总权重建状态的方法通常只能称为伪多项式。该路径不依赖预枚举4096个联盟。"
            ),
            "official_interface": (
                "发布LExaShap的正DNF与线性SUM/COUNT输入不接受聚合结果ABS；Max_LExaBan既不是Shapley接口，"
                "其MAX-of-output-tuples语义也不等同于max of two global sums。"
            ),
            "expression_scale": (
                "历史稠密Harsanyi展开说明该基表示很大，但不能据此推出所有精确算法都指数；小计数状态DP是独立候选路径。"
            ),
            "literature_boundary": "本轮未完成与现有计数DP/生成函数文献的系统归约，不将该结构称为新算法。",
        },
        "full_n4_adaptation_executed": False,
        "audit_wall_seconds": time.perf_counter() - stage_started,
        "memory": stage_memory_end(memory_start),
    }
    json_write(N4_OUT / "audit.json", result)
    return result


def main() -> None:
    for directory in (N1_OUT, N2_OUT, J1_OUT, N4_OUT):
        directory.mkdir(parents=True, exist_ok=True)
    before = {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL_N1}
    tracemalloc.start()
    run_started = time.perf_counter()
    spec = load_d1p_spec(ROOT / "config" / "d1p_design.yaml")
    states = all_incremental_states(spec)
    suite = D1PValueSuite(spec, states[-1], ROOT / "config" / "value_spec_v3_2.yaml")
    connection = duckdb.connect(":memory:")
    create_d1p_database(connection, spec)
    n1 = audit_n1(connection, spec.player_count)
    n2 = run_n2(connection, spec)
    j1 = run_j1()
    n4 = audit_n4_structure(spec, states, suite)
    after = {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL_N1}
    if before != after:
        raise AssertionError("历史AB-N1文件被修改")
    current, final_stage_peak = tracemalloc.get_traced_memory()
    maximum_observed_stage_peak = max(
        result["memory"]["python_tracemalloc_peak_bytes"] for result in (n1, n2, j1, n4)
    )
    j1_official = j1["timings_seconds"]["official_by_game"]
    timing_memory_rows = [
        {
            "stage": "AB-N1-SUPPLEMENT",
            "sql_grounding_or_audit_seconds": n1["sql_execution_seconds"],
            "source_expression_assembly_seconds": "",
            "official_dtree_compile_seconds": "",
            "official_shapley_solve_seconds": "",
            "official_end_to_end_seconds": "",
            "algorithm_end_to_end_excluding_oracle_seconds": "",
            "posthoc_oracle_seconds": n1["sql_execution_seconds"],
            "stage_wall_seconds": n1["stage_wall_seconds"],
            "python_tracemalloc_peak_bytes": n1["memory"]["python_tracemalloc_peak_bytes"],
        },
        {
            "stage": "AB-N2",
            "sql_grounding_or_audit_seconds": n2["timings_seconds"]["sql_grounding"],
            "source_expression_assembly_seconds": n2["timings_seconds"]["source_expression_assembly"],
            "official_dtree_compile_seconds": n2["timings_seconds"]["official_dtree_compile_seconds"],
            "official_shapley_solve_seconds": n2["timings_seconds"]["official_backward_solve_seconds"],
            "official_end_to_end_seconds": n2["timings_seconds"]["official_untouched_end_to_end_seconds"],
            "algorithm_end_to_end_excluding_oracle_seconds": n2["timings_seconds"]["algorithm_end_to_end_excluding_oracles"],
            "posthoc_oracle_seconds": (
                n2["timings_seconds"]["posthoc_4096_alliance_sql_oracle"]
                + n2["timings_seconds"]["posthoc_exact_shapley"]
            ),
            "stage_wall_seconds": n2["timings_seconds"]["whole_stage_including_csv_and_oracles"],
            "python_tracemalloc_peak_bytes": n2["memory"]["python_tracemalloc_peak_bytes"],
        },
        {
            "stage": "AB-J1",
            "sql_grounding_or_audit_seconds": j1["timings_seconds"]["sql_grounding"],
            "source_expression_assembly_seconds": j1["timings_seconds"]["source_expression_assembly"],
            "official_dtree_compile_seconds": sum(v["official_dtree_compile_seconds"] for v in j1_official.values()),
            "official_shapley_solve_seconds": sum(v["official_backward_solve_seconds"] for v in j1_official.values()),
            "official_end_to_end_seconds": sum(v["official_untouched_end_to_end_seconds"] for v in j1_official.values()),
            "algorithm_end_to_end_excluding_oracle_seconds": j1["timings_seconds"]["algorithm_end_to_end_excluding_oracle"],
            "posthoc_oracle_seconds": j1["timings_seconds"]["posthoc_sql_oracle"],
            "stage_wall_seconds": j1["timings_seconds"]["whole_stage_including_csv_and_oracle"],
            "python_tracemalloc_peak_bytes": j1["memory"]["python_tracemalloc_peak_bytes"],
        },
        {
            "stage": "AB-N4-STRUCTURE-AUDIT",
            "sql_grounding_or_audit_seconds": "",
            "source_expression_assembly_seconds": "",
            "official_dtree_compile_seconds": "",
            "official_shapley_solve_seconds": "",
            "official_end_to_end_seconds": "",
            "algorithm_end_to_end_excluding_oracle_seconds": "",
            "posthoc_oracle_seconds": "",
            "stage_wall_seconds": n4["audit_wall_seconds"],
            "python_tracemalloc_peak_bytes": n4["memory"]["python_tracemalloc_peak_bytes"],
        },
    ]
    write_csv(OUT / "timing_memory_summary.csv", timing_memory_rows)
    manifest = {
        "status": "COMPLETED_AB_N2_AND_AB_J1_ONLY",
        "ab_n1_supplement": n1["status"],
        "ab_n2": n2["status"],
        "ab_j1": j1["status"],
        "ab_n4": n4["status"],
        "ab_n3_executed": False,
        "ab_n4_full_adaptation_executed": False,
        "ab_n5_executed": False,
        "historical_ab_n1_hashes_before": before,
        "historical_ab_n1_hashes_after": after,
        "total_wall_seconds": time.perf_counter() - run_started,
        "final_python_tracemalloc_current_bytes": current,
        "final_stage_peak_after_resets_bytes": final_stage_peak,
        "maximum_observed_stage_python_tracemalloc_peak_bytes": maximum_observed_stage_peak,
        "environment": {
            "python": sys.version,
            "duckdb": duckdb.__version__,
            "official_shapley_source_sha256": sha256(
                OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyCircuit.py"
            ),
            "d1p_design_sha256": sha256(ROOT / "config" / "d1p_design.yaml"),
            "value_spec_sha256": sha256(ROOT / "config" / "value_spec_v3_2.yaml"),
        },
    }
    json_write(OUT / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
