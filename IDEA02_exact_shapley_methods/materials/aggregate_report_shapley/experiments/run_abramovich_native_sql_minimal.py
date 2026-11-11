from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from fractions import Fraction
from pathlib import Path

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
from aggregate_report_shapley.d1p import load_d1p_spec  # noqa: E402
from aggregate_report_shapley.d1p_sql import create_d1p_database  # noqa: E402
from aggregate_report_shapley.exact_shapley import exact_shapley_subset  # noqa: E402


OUT = ROOT / "outputs" / "v4_0" / "AB_NATIVE_SQL"
AGGREGATE_SQL = """
SELECT
    COUNT(*)::BIGINT AS record_count,
    SUM(CASE WHEN b.category_a_id = 'E2' THEN 1 ELSE 0 END)::BIGINT AS category_a_target_sum
FROM (
    SELECT * FROM BasicSource_A1
    UNION ALL SELECT * FROM BasicSource_A2
    UNION ALL SELECT * FROM BasicSource_B1
    UNION ALL SELECT * FROM BasicSource_B2
) b
JOIN Hierarchy h USING (leaf_node_id)
WHERE b.leaf_node_id = 'A1'
""".strip()

GROUNDING_SQL = """
SELECT
    b.player_index,
    b.record_id,
    1::BIGINT AS record_count_coefficient,
    CASE WHEN b.category_a_id = 'E2' THEN 1 ELSE 0 END::BIGINT AS category_a_target_sum_coefficient
FROM (
    SELECT * FROM BasicSource_A1
    UNION ALL SELECT * FROM BasicSource_A2
    UNION ALL SELECT * FROM BasicSource_B1
    UNION ALL SELECT * FROM BasicSource_B2
) b
JOIN Hierarchy h USING (leaf_node_id)
WHERE b.leaf_node_id = 'A1'
ORDER BY b.player_index
""".strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def official_scalar(dnf: list[set[str]]) -> dict[str, float]:
    circuit = DNFCircuit(dnf)
    scale = (2 ** len(circuit.vars)) / math.factorial(len(circuit.vars))
    return {
        str(value.label): sum(float(g) * float(p) for g, p in zip(value.grad, value.prob)) * scale
        for value in circuit.vars
    }


def instrumented_official_scalar(dnf: list[set[str]]) -> tuple[dict[str, float], float, float]:
    """Split official construction/backward phases without editing official files."""
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


def oracle_rows(connection: duckdb.DuckDBPyConnection, player_count: int) -> list[tuple[int, int, int]]:
    sql = f"""
    WITH masks AS (SELECT range AS mask FROM range({1 << player_count})),
    base AS (
        SELECT * FROM BasicSource_A1
        UNION ALL SELECT * FROM BasicSource_A2
        UNION ALL SELECT * FROM BasicSource_B1
        UNION ALL SELECT * FROM BasicSource_B2
    )
    SELECT m.mask,
           COUNT(b.record_id)::BIGINT AS record_count,
           COALESCE(SUM(CASE WHEN b.category_a_id = 'E2' THEN 1 ELSE 0 END), 0)::BIGINT AS category_a_target_sum
    FROM masks m
    LEFT JOIN base b
      ON b.leaf_node_id = 'A1' AND ((m.mask >> b.player_index) & 1) = 1
    GROUP BY m.mask
    ORDER BY m.mask
    """
    return [(int(mask), int(count), int(target)) for mask, count, target in connection.execute(sql).fetchall()]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    spec = load_d1p_spec(ROOT / "config" / "d1p_design.yaml")
    connection = duckdb.connect(":memory:")
    create_d1p_database(connection, spec)

    full_sql_result = connection.execute(AGGREGATE_SQL).fetchone()
    source_started = time.perf_counter()
    grounding_rows = connection.execute(GROUNDING_SQL).fetchall()
    source_compile_seconds = time.perf_counter() - source_started
    if [row[1] for row in grounding_rows] != ["p1", "p2"]:
        raise AssertionError("AB-N1 grounding 与冻结 A1 数据不一致")

    expressions: dict[str, list[tuple[list[set[str]], Fraction]]] = {
        "record_count": [],
        "category_a_target_sum": [],
    }
    for _index, record_id, count_coefficient, sum_coefficient in grounding_rows:
        if count_coefficient:
            expressions["record_count"].append(([{str(record_id)}], Fraction(int(count_coefficient))))
        if sum_coefficient:
            expressions["category_a_target_sum"].append(([{str(record_id)}], Fraction(int(sum_coefficient))))

    payments = {metric: {record.record_id: 0.0 for record in spec.records} for metric in expressions}
    phase_timings: dict[str, dict[str, float]] = {}
    end_to_end_started = time.perf_counter()
    for metric, components in expressions.items():
        compile_seconds = 0.0
        solve_seconds = 0.0
        for dnf, coefficient in components:
            untouched = official_scalar(dnf)
            instrumented, compile_part, solve_part = instrumented_official_scalar(dnf)
            if untouched.keys() != instrumented.keys() or any(
                abs(untouched[key] - instrumented[key]) > 1e-12 for key in untouched
            ):
                raise AssertionError("官方完整调用与分阶段计时调用不一致")
            compile_seconds += compile_part
            solve_seconds += solve_part
            for player, value in untouched.items():
                payments[metric][player] += float(coefficient) * value
        phase_timings[metric] = {
            "official_dtree_compile_seconds": compile_seconds,
            "official_backward_solve_seconds": solve_seconds,
        }
    official_end_to_end_seconds = time.perf_counter() - end_to_end_started

    # This exhaustive SQL table is created only after the source expressions and
    # official estimates exist.  It is an independent correctness oracle, never
    # an estimator input.
    oracle_started = time.perf_counter()
    exhaustive = oracle_rows(connection, spec.player_count)
    oracle_sql_seconds = time.perf_counter() - oracle_started
    tables = {
        "record_count": [row[1] for row in exhaustive],
        "category_a_target_sum": [row[2] for row in exhaustive],
    }
    expression_value_errors: dict[str, float] = {}
    payment_errors: dict[str, float] = {}
    exact_payments: dict[str, dict[str, str]] = {}
    coefficient_by_metric = {
        metric: {
            next(iter(dnf[0])): coefficient
            for dnf, coefficient in components
        }
        for metric, components in expressions.items()
    }
    for metric, table in tables.items():
        coefficients = coefficient_by_metric[metric]
        expression_values = [
            sum(
                float(coefficient)
                for player, coefficient in coefficients.items()
                if mask & (1 << next(r.player_index for r in spec.records if r.record_id == player))
            )
            for mask in range(1 << spec.player_count)
        ]
        expression_value_errors[metric] = max(abs(a - b) for a, b in zip(expression_values, table))
        exact = exact_shapley_subset([Fraction(value) for value in table], spec.player_count)
        exact_payments[metric] = {
            record.record_id: f"{exact[index].numerator}/{exact[index].denominator}"
            for index, record in enumerate(spec.records)
        }
        payment_errors[metric] = max(
            abs(payments[metric][record.record_id] - float(exact[index]))
            for index, record in enumerate(spec.records)
        )
    if max(expression_value_errors.values()) > 0 or max(payment_errors.values()) > 1e-12:
        raise AssertionError("AB-N1 联盟等价或 Shapley 正确性关卡失败")

    serialized_expression = {
        metric: [
            {"dnf": [sorted(clause) for clause in dnf], "coefficient": str(coefficient)}
            for dnf, coefficient in components
        ]
        for metric, components in expressions.items()
    }
    expression_json = json.dumps(serialized_expression, ensure_ascii=False, sort_keys=True)
    payload = {
        "stage": "AB-N1",
        "status": "MINIMAL_NATIVE_SQL_ADAPTATION_VALIDATED",
        "scope": "D1-P A1 单层 COUNT 与条件 SUM；未执行 AB-N2 至 AB-N5",
        "official_source_modified": False,
        "players": [record.record_id for record in spec.records],
        "player_binding": "one record_id -> one endogenous Boolean variable; hierarchy rows are exogenous",
        "aggregate_sql": AGGREGATE_SQL,
        "grounding_sql": GROUNDING_SQL,
        "full_database_sql_result": {
            "record_count": int(full_sql_result[0]),
            "category_a_target_sum": int(full_sql_result[1]),
        },
        "grounding_rows": [list(row) for row in grounding_rows],
        "source_expression": serialized_expression,
        "source_expression_size": {
            "components": sum(len(items) for items in expressions.values()),
            "clauses": sum(len(dnf) for items in expressions.values() for dnf, _ in items),
            "literal_occurrences": sum(len(clause) for items in expressions.values() for dnf, _ in items for clause in dnf),
            "serialized_utf8_bytes": len(expression_json.encode("utf-8")),
        },
        "construction_used_coalition_values": False,
        "construction_used_exact_payments": False,
        "official_payments": payments,
        "exact_payments": exact_payments,
        "maximum_coalition_value_error": expression_value_errors,
        "maximum_payment_error": payment_errors,
        "timings": {
            "sql_to_grounding_source_compile_seconds": source_compile_seconds,
            "per_metric_official_phases": phase_timings,
            "official_end_to_end_seconds": official_end_to_end_seconds,
            "posthoc_4096_coalition_sql_oracle_seconds": oracle_sql_seconds,
            "timing_note": "compile/solve split uses official internal classes in an independent harness and is cross-checked against the untouched DNFCircuit constructor",
        },
        "hashes": {
            "official_shapley_source_sha256": sha256(OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyCircuit.py"),
            "d1p_design_sha256": sha256(ROOT / "config" / "d1p_design.yaml"),
            "value_spec_sha256": sha256(ROOT / "config" / "value_spec_v3_2.yaml"),
        },
        "boundary": "This validates a handwritten native compiler for one simple SPJ+COUNT/SUM query, not a general SQL-to-lineage compiler and not V1/V2.",
    }
    (OUT / "ab_n1_minimal_validation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT / "ab_n1_source_expression.json").write_text(
        json.dumps(serialized_expression, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
