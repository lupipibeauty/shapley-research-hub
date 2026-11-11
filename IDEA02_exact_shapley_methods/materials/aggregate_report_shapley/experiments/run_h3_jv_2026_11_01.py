from __future__ import annotations

import csv
import gc
import hashlib
import json
import math
import statistics
import sys
import time
import tracemalloc
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

import duckdb


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "experiments"), str(OFFICIAL)]

from aggregate_report_shapley.h3_jv import (  # noqa: E402
    LAMBDA,
    LEAVES,
    METRICS,
    NODES,
    PLAYERS,
    REVENUE,
    JVInstance,
    evidence_deltas,
    exact_shapley,
    generate_instance,
    groundings,
    lineage_components,
    make_value_functions,
    old_d1p_state,
    player_index,
    report_for_mask,
    report_from_evidence_state,
    report_signature,
    score_ratio,
)
from aggregate_report_shapley.h5_shared import (  # noqa: E402
    S4PrefixSuffix,
    S6ReverseMultilinearAD,
    StateGame,
    max_abs_error,
    s0_per_focus_b2,
    s1_per_focus_b3,
)
from run_ab_n2_ab_j1_2026_10_31 import run_component  # noqa: E402


OUT = ROOT / "outputs" / "v4_0" / "H3_JV"
DATA = OUT / "data"
SQL_DIR = OUT / "sql"
SEEDS = (7301, 7302, 7303, 7304, 7305)
FIXED_SEED = 7301
TOL = 1e-9
CAP = 100_000
REPEATS = 3

HISTORICAL = tuple(
    path
    for path in (
        ROOT / "config" / "d1p_design.yaml",
        ROOT / "config" / "value_spec_v3_2.yaml",
        ROOT / "docs" / "H0_模型与实验设计审计.md",
        ROOT / "reports" / "H5_V2_JOINT_STATE实验审计报告_2026-10-31.md",
        ROOT / "reports" / "H5_SCALE联合状态与规模结构审计报告_2026-11-01.md",
        ROOT / "reports" / "H5_R_经典精确算法全玩家共享计算审计报告_2026-11-01.md",
        ROOT / "experiments" / "run_ab_j2_2026_10_31.py",
        ROOT / "experiments" / "run_h5_r_shared_all_players_2026_11_01.py",
        OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyCircuit.py",
        OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyEngine.py",
        OFFICIAL / "Advancing_Fact_Attribution_for_Query_Answering.pdf",
    )
    if path.exists()
)


DDL = """
CREATE TABLE BasicSource(record_id VARCHAR, player_index INTEGER, player_id VARCHAR,
 entity_key VARCHAR, leaf_node_id VARCHAR, category_id VARCHAR, amount INTEGER);
CREATE TABLE EventSource(record_id VARCHAR, player_index INTEGER, player_id VARCHAR,
 event_key VARCHAR, leaf_node_id VARCHAR, category_id VARCHAR, amount INTEGER);
CREATE TABLE RelationSource(record_id VARCHAR, player_index INTEGER, player_id VARCHAR,
 entity_key VARCHAR, event_key VARCHAR, weight INTEGER);
CREATE TABLE J0Fact(record_id VARCHAR, player_index INTEGER, player_id VARCHAR,
 leaf_node_id VARCHAR, category_id VARCHAR, amount INTEGER, business_key VARCHAR);
CREATE TABLE Hierarchy(leaf_node_id VARCHAR, parent_node_id VARCHAR, root_node_id VARCHAR);
CREATE TABLE CategoryDimension(category_id VARCHAR, is_target BOOLEAN);
CREATE TABLE PlayerMap(player_id VARCHAR, player_index INTEGER, relation_name VARCHAR,
 logical_record_id VARCHAR, physical_row_count INTEGER);
""".strip()


def grounding_cte(join_id: str) -> str:
    if join_id == "J0":
        return """
grounding AS (
 SELECT 'J0_' || record_id AS grounding_id, leaf_node_id, category_id, amount,
        business_key, player_index AS p1, NULL::INTEGER AS p2, NULL::INTEGER AS p3
 FROM J0Fact
)
""".strip()
    if join_id == "J1":
        return """
grounding AS (
 SELECT 'J1_BS_' || s.record_id AS grounding_id, b.leaf_node_id, b.category_id,
        b.amount+s.weight AS amount, 'X_' || b.entity_key AS business_key,
        b.player_index AS p1, s.player_index AS p2, NULL::INTEGER AS p3
 FROM BasicSource b JOIN RelationSource s USING(entity_key)
 UNION ALL
 SELECT 'J1_SE_' || s.record_id, e.leaf_node_id, e.category_id,
        e.amount+s.weight, 'Y_' || e.event_key,
        s.player_index, e.player_index, NULL::INTEGER
 FROM RelationSource s JOIN EventSource e USING(event_key)
)
""".strip()
    if join_id == "J2":
        return """
grounding AS (
 SELECT 'J2_' || s.record_id AS grounding_id, b.leaf_node_id, e.category_id,
        b.amount+e.amount+s.weight AS amount, 'Y_' || e.event_key AS business_key,
        b.player_index AS p1, s.player_index AS p2, e.player_index AS p3
 FROM BasicSource b JOIN RelationSource s USING(entity_key)
 JOIN EventSource e USING(event_key)
)
""".strip()
    raise ValueError(join_id)


def alliance_sql(join_id: str) -> str:
    return f"""
WITH masks AS (SELECT range::INTEGER AS mask FROM range(4096)),
{grounding_cte(join_id)},
selected AS (
 SELECT m.mask, g.*
 FROM masks m JOIN grounding g
 ON ((m.mask >> g.p1) & 1)=1
 AND (g.p2 IS NULL OR ((m.mask >> g.p2) & 1)=1)
 AND (g.p3 IS NULL OR ((m.mask >> g.p3) & 1)=1)
),
expanded AS (
 SELECT s.*, u.node_id
 FROM selected s JOIN Hierarchy h USING(leaf_node_id)
 CROSS JOIN UNNEST([s.leaf_node_id,h.parent_node_id,h.root_node_id]) u(node_id)
),
nodes(node_id) AS (VALUES ('A1'),('A2'),('B1'),('B2'),('PA'),('PB'),('NAT'))
SELECT m.mask,n.node_id,
 COUNT(e.grounding_id)::BIGINT AS bag_count,
 COUNT(DISTINCT e.business_key)::BIGINT AS distinct_count,
 SUM(e.amount)::BIGINT AS raw_amount_sum,
 COALESCE(SUM(e.amount),0)::BIGINT AS amount_sum,
 COUNT(CASE WHEN e.category_id='C1' THEN 1 END)::BIGINT AS target_count,
 COUNT(DISTINCT CASE WHEN e.category_id='C1' THEN e.business_key END)::BIGINT AS target_distinct_count
FROM masks m CROSS JOIN nodes n
LEFT JOIN expanded e ON e.mask=m.mask AND e.node_id=n.node_id
GROUP BY m.mask,n.node_id
ORDER BY m.mask,n.node_id
""".strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"拒绝写入空CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def rss() -> int | None:
    try:
        import psutil
        return int(psutil.Process().memory_info().rss)
    except (ImportError, OSError):
        return None


def timed(call: Callable[[], Any]) -> tuple[Any, dict[str, Any]]:
    gc.collect()
    tracemalloc.start()
    start_rss = rss()
    started = time.perf_counter()
    try:
        result = call()
    finally:
        elapsed = time.perf_counter() - started
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    end_rss = rss()
    return result, {
        "elapsed_seconds": elapsed,
        "python_peak_bytes": peak,
        "rss_start_bytes": start_rss,
        "rss_end_bytes": end_rss,
    }


def create_database(instance: JVInstance) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(DDL)
    con.executemany(
        "INSERT INTO BasicSource VALUES (?,?,?,?,?,?,?)",
        [(f.record_id, player_index(f.player), f.player, f.entity_key, f.leaf, f.category, f.amount) for f in instance.basic],
    )
    con.executemany(
        "INSERT INTO EventSource VALUES (?,?,?,?,?,?,?)",
        [(f.record_id, player_index(f.player), f.player, f.event_key, f.leaf, f.category, f.amount) for f in instance.events],
    )
    con.executemany(
        "INSERT INTO RelationSource VALUES (?,?,?,?,?,?)",
        [(f.record_id, player_index(f.player), f.player, f.entity_key, f.event_key, f.weight) for f in instance.relations],
    )
    con.executemany(
        "INSERT INTO J0Fact VALUES (?,?,?,?,?,?,?)",
        [(f.record_id, player_index(f.player), f.player, f.leaf, f.category, f.amount, f"I_{f.record_id}") for f in instance.j0_facts],
    )
    con.executemany(
        "INSERT INTO Hierarchy VALUES (?,?,?)",
        [(leaf, "PA" if leaf.startswith("A") else "PB", "NAT") for leaf in LEAVES],
    )
    con.executemany("INSERT INTO CategoryDimension VALUES (?,?)", [("C1", True), ("C2", False)])
    map_rows = []
    for index, player in enumerate(PLAYERS):
        relation = "BasicSource" if index < 4 else "EventSource" if index < 8 else "RelationSource"
        physical = 1 if index < 8 else 2
        map_rows.append((player, index, relation, f"logical_{player}", physical))
    con.executemany("INSERT INTO PlayerMap VALUES (?,?,?,?,?)", map_rows)
    return con


def sql_reports(con: duckdb.DuckDBPyConnection, join_id: str) -> tuple[list[dict[str, Any]], dict[int, dict[tuple[str, str], int]], float]:
    sql = alliance_sql(join_id)
    started = time.perf_counter()
    rows = con.execute(sql).fetchall()
    elapsed = time.perf_counter() - started
    output: list[dict[str, Any]] = []
    reports: dict[int, dict[tuple[str, str], int]] = defaultdict(dict)
    for mask, node, bag, distinct, raw_sum, amount, target, target_distinct in rows:
        output.append(
            {
                "join_id": join_id, "mask": int(mask), "coalition_size": int(mask).bit_count(),
                "node": node, "bag_count": int(bag), "distinct_count": int(distinct),
                "raw_amount_sum": raw_sum, "normalized_amount_sum": int(amount),
                "target_count": int(target), "target_distinct_count": int(target_distinct),
            }
        )
        reports[int(mask)].update(
            {
                (node, "bag_count"): int(bag), (node, "distinct_count"): int(distinct),
                (node, "amount_sum"): int(amount), (node, "target_count"): int(target),
                (node, "target_distinct_count"): int(target_distinct),
            }
        )
    return output, reports, elapsed


def state_game(join_id: str, game_id: str, items, full, value_fn) -> StateGame:
    if join_id == "J0":
        deltas_list = []
        for item in items:
            delta = [0] * 16
            offset = LEAVES.index(item.leaf) * 4
            delta[offset : offset + 4] = [1, int(item.category == "C1"), item.amount, 0]
            deltas_list.append(tuple(delta))
        deltas = tuple(deltas_list)

        def report_from_state(state):
            report = {}
            for node in NODES:
                leaf_indices = [i for i, leaf in enumerate(LEAVES) if node in (leaf, "PA" if leaf.startswith("A") else "PB", "NAT")]
                bag = sum(state[4 * i] for i in leaf_indices)
                target = sum(state[4 * i + 1] for i in leaf_indices)
                amount = sum(state[4 * i + 2] for i in leaf_indices)
                report[(node, "bag_count")] = bag
                report[(node, "distinct_count")] = bag
                report[(node, "amount_sum")] = amount
                report[(node, "target_count")] = target
                report[(node, "target_distinct_count")] = target
            return report
    else:
        deltas = evidence_deltas(items)
        report_from_state = lambda state: report_from_evidence_state(items, state)
    return StateGame(
        f"{join_id}-{game_id}", PLAYERS, deltas,
        lambda state: value_fn(report_from_state(state)),
        tuple(index % 4 for index in range(12)), 4, len(deltas[0]) // 4,
    )


def run_b1_official(components) -> tuple[list[float], dict[str, Any]]:
    grouped: dict[tuple[tuple[str, ...], ...], Fraction] = defaultdict(Fraction)
    raw_clause_occurrences = 0
    duplicate_clauses_removed = 0
    for dnf, coefficient, _node, _metric in components:
        raw_clauses = [tuple(sorted(clause)) for clause in dnf]
        raw_clause_occurrences += len(raw_clauses)
        key = tuple(sorted(set(raw_clauses)))
        duplicate_clauses_removed += len(raw_clauses) - len(key)
        grouped[key] += coefficient
    payments = {player: 0.0 for player in PLAYERS}
    compile_seconds = solve_seconds = untouched_seconds = 0.0
    for key, coefficient in grouped.items():
        result, costs = run_component([set(clause) for clause in key], coefficient)
        for player, value in result.items():
            payments[player] += value
        compile_seconds += costs["official_dtree_compile_seconds"]
        solve_seconds += costs["official_backward_solve_seconds"]
        untouched_seconds += costs["official_untouched_end_to_end_seconds"]
    return [payments[p] for p in PLAYERS], {
        "unique_dnf_components": len(grouped),
        "official_dtree_compile_seconds": compile_seconds,
        "official_backward_solve_seconds": solve_seconds,
        "official_untouched_end_to_end_seconds": untouched_seconds,
        "raw_clause_occurrences": raw_clause_occurrences,
        "duplicate_boolean_clauses_removed": duplicate_clauses_removed,
    }


def run_b2_coordinate(game_join: str, items, full) -> tuple[list[float], dict[str, Any]]:
    total = [0.0] * 12
    terminal = transitions = 0
    started = time.perf_counter()
    for node in NODES:
        for coordinate in range(5):
            if coordinate < 4:
                metric = METRICS[coordinate]
                reference = full[(node, metric)]
                coordinate_value = lambda report, n=node, m=metric, f=reference: 0.0 if f == 0 else report[(n, m)] / f
            else:
                coordinate_value = lambda report, n=node: score_ratio(
                    report[(n, "target_count")], report[(n, "bag_count")],
                    full[(n, "target_count")], full[(n, "bag_count")],
                )
            game = state_game(game_join, f"G1_{node}_{coordinate}", items, full, coordinate_value)
            mapping, diag = s0_per_focus_b2(game, range(12), state_cap=CAP)
            for player in range(12):
                total[player] += REVENUE * mapping[player] / 35
            terminal += int(diag["terminal_state_visits"])
            transitions += int(diag["state_transitions"])
    return total, {
        "terminal_state_visits": terminal,
        "state_transitions": transitions,
        "coordinate_games": 35,
        "solve_seconds_internal": time.perf_counter() - started,
    }


def run_s4(game: StateGame) -> tuple[list[float], dict[str, Any]]:
    solver = S4PrefixSuffix(game, state_cap=CAP)
    allocation = solver.solve_all()
    return allocation, solver.diagnostics()


def run_s6(game: StateGame) -> tuple[list[float], dict[str, Any]]:
    solver = S6ReverseMultilinearAD(game, state_cap=CAP)
    allocation = solver.solve_all()
    return allocation, solver.diagnostics()


def source_value(components, mask: int) -> float:
    selected = {PLAYERS[i] for i in range(12) if mask & (1 << i)}
    value = Fraction()
    for dnf, coefficient, _node, _metric in components:
        if any(clause <= selected for clause in dnf):
            value += coefficient
    return float(value)


def find_counterexamples(instance, join_id, items, reports, values_by_game) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    old_groups: dict[tuple[int, ...], list[int]] = defaultdict(list)
    evidence_groups: dict[tuple[int, ...], list[int]] = defaultdict(list)
    deltas = evidence_deltas(items)
    for mask in range(4096):
        old_groups[old_d1p_state(instance, mask)].append(mask)
        evidence = tuple(sum(delta[k] for p, delta in enumerate(deltas) if mask & (1 << p)) for k in range(len(items)))
        evidence_groups[evidence].append(mask)
    old_example = None
    for state, masks in old_groups.items():
        signatures = {report_signature(reports[m]) for m in masks}
        if len(signatures) > 1:
            pair = next((a, b) for a in masks for b in masks if report_signature(reports[a]) != report_signature(reports[b]))
            candidate = (sum(pair), pair, state)
            if old_example is None or candidate[0] < old_example[0]:
                old_example = candidate
    rows.append(
        {
            "join_id": join_id, "test": "OLD_16D_STATE_REPORT_SUFFICIENCY",
            "status": "FAIL_COUNTEREXAMPLE_FOUND" if old_example else "PASS",
            "mask_1": "" if not old_example else old_example[1][0],
            "mask_2": "" if not old_example else old_example[1][1],
            "state": "" if not old_example else json.dumps(old_example[2]),
            "detail": "旧状态相同但SQL报表不同" if old_example else "旧状态决定完整SQL报表",
        }
    )
    evidence_conflicts = 0
    for masks in evidence_groups.values():
        if len({report_signature(reports[m]) for m in masks}) > 1:
            evidence_conflicts += 1
    rows.append(
        {
            "join_id": join_id, "test": "JOIN_EVIDENCE_STATE_REPORT_SUFFICIENCY",
            "status": "PASS" if evidence_conflicts == 0 else "FAIL",
            "mask_1": "", "mask_2": "", "state": "",
            "detail": f"reachable_states={len(evidence_groups)}; conflicts={evidence_conflicts}",
        }
    )
    for game_id, values in values_by_game.items():
        example = None
        groups: dict[float, list[int]] = defaultdict(list)
        for mask, value in enumerate(values):
            groups[round(value, 12)].append(mask)
        for masks in groups.values():
            for i, left in enumerate(masks):
                for right in masks[i + 1 :]:
                    for player in range(12):
                        bit = 1 << player
                        if left & bit or right & bit:
                            continue
                        lm = values[left | bit] - values[left]
                        rm = values[right | bit] - values[right]
                        if abs(lm - rm) > 1e-9:
                            example = (left, right, player, lm, rm)
                            break
                    if example:
                        break
                if example:
                    break
            if example:
                break
        rows.append(
            {
                "join_id": join_id, "test": f"CURRENT_VALUE_NOT_INCREMENTALLY_SUFFICIENT_{game_id}",
                "status": "COUNTEREXAMPLE_FOUND" if example else "NO_COUNTEREXAMPLE",
                "mask_1": "" if not example else example[0], "mask_2": "" if not example else example[1],
                "state": "" if not example else f"add_player={PLAYERS[example[2]]}",
                "detail": "" if not example else f"marginals={example[3]},{example[4]}",
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    before = {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL}
    write_json(OUT / "config.json", {
        "experiment": "H3-JV", "fixed_seed": FIXED_SEED, "replicate_seeds": list(SEEDS),
        "players": list(PLAYERS), "revenue": REVENUE, "lambda": LAMBDA,
        "timing_repeats_fixed_instance": REPEATS, "tolerance": TOL,
    })
    SQL_DIR.mkdir(parents=True, exist_ok=True)
    (SQL_DIR / "create_relations.sql").write_text(DDL, encoding="utf-8")
    for join_id in ("J0", "J1", "J2"):
        print(f"SQL_GATE {join_id}", flush=True)
        (SQL_DIR / f"{join_id.lower()}_all_coalitions.sql").write_text(alliance_sql(join_id), encoding="utf-8")

    instance = generate_instance(FIXED_SEED)
    con = create_database(instance)
    input_rows: list[dict[str, Any]] = []
    for fact in instance.basic:
        input_rows.append({"relation": "BasicSource", "record_id": fact.record_id, "player": fact.player, "leaf": fact.leaf, "category": fact.category, "amount": fact.amount, "entity_key": fact.entity_key, "event_key": "", "weight": ""})
    for fact in instance.events:
        input_rows.append({"relation": "EventSource", "record_id": fact.record_id, "player": fact.player, "leaf": fact.leaf, "category": fact.category, "amount": fact.amount, "entity_key": "", "event_key": fact.event_key, "weight": ""})
    for fact in instance.relations:
        input_rows.append({"relation": "RelationSource", "record_id": fact.record_id, "player": fact.player, "leaf": "", "category": "", "amount": "", "entity_key": fact.entity_key, "event_key": fact.event_key, "weight": fact.weight})
    write_csv(DATA / "input_relations.csv", input_rows)
    write_csv(DATA / "player_map.csv", [
        {"player": p, "player_index": i, "controlled_relation": "BasicSource" if i < 4 else "EventSource" if i < 8 else "RelationSource", "physical_rows": 1 if i < 8 else 2}
        for i, p in enumerate(PLAYERS)
    ])
    write_csv(DATA / "hierarchy.csv", [
        {"leaf_node_id": leaf, "parent_node_id": "PA" if leaf.startswith("A") else "PB", "root_node_id": "NAT"}
        for leaf in LEAVES
    ])

    sql_rows: list[dict[str, Any]] = []
    value_rows: list[dict[str, Any]] = []
    truth_rows: list[dict[str, Any]] = []
    algorithm_rows: list[dict[str, Any]] = []
    payment_rows: list[dict[str, Any]] = []
    structural_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    source_payload: dict[str, Any] = {}
    truths: dict[tuple[str, str], list[float]] = {}
    reports_by_join: dict[str, dict[int, dict[tuple[str, str], int]]] = {}
    items_by_join = {}
    full_by_join = {}
    value_functions_by_join = {}

    # Gate 1: every coalition is evaluated by DuckDB SQL and independently by lineage.
    for join_id in ("J0", "J1", "J2"):
        sql_output, reports, sql_seconds = sql_reports(con, join_id)
        sql_rows.extend(sql_output)
        reports_by_join[join_id] = reports
        items = groundings(instance, join_id)
        items_by_join[join_id] = items
        max_report_error = 0
        for mask in range(4096):
            independent = report_for_mask(items, mask)
            max_report_error = max(
                max_report_error,
                max(abs(independent[key] - reports[mask][key]) for key in independent),
            )
        if max_report_error != 0:
            raise AssertionError(f"{join_id} SQL/lineage mismatch {max_report_error}")
        full = reports[4095]
        full_by_join[join_id] = full
        value_fns = make_value_functions(full)
        value_functions_by_join[join_id] = value_fns
        game_values = {}
        for game_id, value_fn in value_fns.items():
            values = [value_fn(reports[mask]) for mask in range(4096)]
            game_values[game_id] = values
            truths[(join_id, game_id)] = exact_shapley(values)
            for mask, value in enumerate(values):
                value_rows.append({
                    "join_id": join_id, "game_id": game_id, "mask": mask,
                    "coalition_size": mask.bit_count(), "value": value,
                    "empty_value": values[0], "full_value": values[-1],
                })
            for player, shapley in zip(PLAYERS, truths[(join_id, game_id)], strict=True):
                truth_rows.append({
                    "join_id": join_id, "game_id": game_id, "player": player,
                    "exact_shapley": shapley,
                    "efficiency_target": values[-1] - values[0],
                })
        state_rows.extend(find_counterexamples(instance, join_id, items, reports, game_values))
        components = lineage_components(items, full)
        source_error = max(abs(source_value(components, mask) - game_values["G0"][mask]) for mask in range(4096))
        if source_error > 1e-10:
            raise AssertionError(f"{join_id} G0 source mismatch {source_error}")
        dnf_clauses = sum(len(component[0]) for component in components)
        variable_occurrences = sum(len(clause) for component in components for clause in component[0])
        distinct_keys = len({item.business_key for item in items})
        evidence_states = {tuple(sum(delta[k] for p, delta in enumerate(evidence_deltas(items)) if mask & (1 << p)) for k in range(len(items))) for mask in range(4096)}
        structural_rows.append({
            "seed": FIXED_SEED, "join_id": join_id, "players": 12,
            "groundings": len(items), "distinct_output_keys": distinct_keys,
            "dnf_clause_occurrences_all_G0_components": dnf_clauses,
            "variable_occurrences_all_G0_components": variable_occurrences,
            "shared_lineage_nodes_definition": "12 player leaves + one AND per grounding + one OR per distinct key",
            "shared_lineage_nodes": 12 + len(items) + distinct_keys,
            "effective_increment_types": len(set(evidence_deltas(items))),
            "reachable_evidence_states": len(evidence_states),
            "sql_all_4096_seconds": sql_seconds,
            "sql_lineage_max_coordinate_error": max_report_error,
            "g0_source_max_value_error": source_error,
        })
        source_payload[join_id] = {
            "groundings": [
                {"id": item.grounding_id, "clause": [PLAYERS[i] for i in sorted(item.clause)], "leaf": item.leaf, "category": item.category, "amount": item.amount, "business_key": item.business_key, "branch": item.branch}
                for item in items
            ],
            "G0_components": [
                {"dnf": [sorted(clause) for clause in dnf], "coefficient": str(coef), "node": node, "metric": metric}
                for dnf, coef, node, metric in components
            ],
            "G1_terminal": "35 coordinate scores added; first four coverage, fifth target-share absolute-deviation score",
            "G2_terminal": "four family scores; 0.5 arithmetic + 0.5 weighted geometric mean",
        }

    write_csv(OUT / "alliance_sql_report.csv", sql_rows)
    write_csv(OUT / "alliance_values.csv", value_rows)
    write_csv(OUT / "exact_record_shapley.csv", truth_rows)
    write_csv(OUT / "structural_metrics.csv", structural_rows)
    write_csv(OUT / "state_sufficiency_and_counterexamples.csv", state_rows)
    write_json(OUT / "source_expressions.json", source_payload)

    # Gate 2: algorithms, all checked against SQL-derived B0 truth.
    for join_id in ("J0", "J1", "J2"):
        items = items_by_join[join_id]
        full = full_by_join[join_id]
        components = lineage_components(items, full)
        for game_id in ("G0", "G1", "G2"):
            print(f"ALGORITHM_GATE {join_id}-{game_id}", flush=True)
            truth = truths[(join_id, game_id)]
            values = [row["value"] for row in value_rows if row["join_id"] == join_id and row["game_id"] == game_id]
            game = state_game(join_id, game_id, items, full, value_functions_by_join[join_id][game_id])
            methods: list[tuple[str, Callable[[], tuple[list[float], dict[str, Any]]], str]] = []
            methods.append(("B0_FULL_COALITION", lambda v=values: (exact_shapley(v), {"input_states": 4096}), "SQL_DERIVED_COALITION_VALUES"))
            if game_id == "G0":
                methods.append(("B1_ABRAMOVICH", lambda c=components: run_b1_official(c), "MANUAL_SQL_GROUNDING_TO_OFFICIAL_DNF"))
            if game_id == "G1":
                methods.append(("B2_COORDINATE_DP", lambda j=join_id, it=items, f=full: run_b2_coordinate(j, it, f), "LINEARITY_PLUS_JOIN_EVIDENCE_STATE"))
            methods.append(("B3_JOINT_STATE_DP", lambda g=game: s0_per_focus_b2(g, range(12), state_cap=CAP), "JOIN_EVIDENCE_STATE" if join_id != "J0" else "ORIGINAL_16D_LEAF_STATE"))
            if join_id == "J0":
                methods.append(("B4_LEAF_FACTOR", lambda g=game: s1_per_focus_b3(g, range(12), state_cap=CAP), "VALID_16D_LEAF_PARTITION"))
            methods.extend(
                [
                    ("B5_S4_PREFIX_SUFFIX", lambda g=game: run_s4(g), "SHARED_PREFIX_SUFFIX"),
                    ("B5_S6_REVERSE_AD", lambda g=game: run_s6(g), "MULTILINEAR_EXPECTATION_CIRCUIT"),
                ]
            )
            first_payment: dict[str, list[float]] = {}
            for method, call, input_kind in methods:
                for repeat in range(REPEATS):
                    (allocation_or_map, diagnostics), costs = timed(call)
                    if isinstance(allocation_or_map, dict):
                        allocation = [allocation_or_map[i] for i in range(12)]
                    else:
                        allocation = list(allocation_or_map)
                    error = max_abs_error(allocation, truth)
                    efficiency = abs(sum(allocation) - (values[-1] - values[0]))
                    if error > TOL or efficiency > TOL:
                        raise AssertionError(f"{join_id}-{game_id}-{method}: {error}, {efficiency}")
                    if repeat == 0:
                        first_payment[method] = allocation
                        for player, estimate, expected in zip(PLAYERS, allocation, truth, strict=True):
                            payment_rows.append({
                                "join_id": join_id, "game_id": game_id, "method": method,
                                "player": player, "shapley": estimate, "B0_truth": expected,
                                "absolute_error": abs(estimate - expected),
                            })
                    algorithm_rows.append({
                        "seed": FIXED_SEED, "join_id": join_id, "game_id": game_id,
                        "method": method, "repeat": repeat, "status": "SUCCESS_EXACT",
                        "input_kind": input_kind, "input_construction_reads_known_payments": False,
                        "max_player_error": error, "efficiency_error": efficiency,
                        **costs, **diagnostics,
                    })
            if game_id == "G0":
                # Luo independent-utility theorem applies to the same additive output units;
                # record the independently validated reduction without pretending an official JV frontend ran.
                b1 = first_payment["B1_ABRAMOVICH"]
                for player, estimate, expected in zip(PLAYERS, b1, truth, strict=True):
                    payment_rows.append({
                        "join_id": join_id, "game_id": game_id, "method": "B6_LUO_THEOREM_REDUCTION",
                        "player": player, "shapley": estimate, "B0_truth": expected,
                        "absolute_error": abs(estimate - expected),
                    })
                algorithm_rows.append({
                    "seed": FIXED_SEED, "join_id": join_id, "game_id": game_id,
                    "method": "B6_LUO_THEOREM_REDUCTION", "repeat": "NA",
                    "status": "EXACT_REDUCTION_VALIDATED_OFFICIAL_JV_FRONTEND_NOT_RUN",
                    "input_kind": "INDEPENDENT_OUTPUT_UTILITIES_WITH_SYNTHESIS_DNFS",
                    "input_construction_reads_known_payments": False,
                    "max_player_error": max_abs_error(b1, truth),
                    "efficiency_error": abs(sum(b1) - (values[-1] - values[0])),
                    "elapsed_seconds": "NOT_SEPARATELY_TIMED_REUSES_G0_COMPONENTS",
                })

    write_csv(OUT / "algorithm_raw_performance.csv", algorithm_rows)
    write_csv(OUT / "algorithm_record_shapley.csv", payment_rows)

    # Five independent generated instances per JOIN; full SQL/lineage gates plus representative G2 S6.
    replicate_rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        print(f"REPLICATE seed={seed}", flush=True)
        inst = generate_instance(seed)
        c = create_database(inst)
        for join_id in ("J0", "J1", "J2"):
            _raw, reports, sql_seconds = sql_reports(c, join_id)
            items = groundings(inst, join_id)
            max_sql_error = max(
                max(abs(report_for_mask(items, mask)[key] - reports[mask][key]) for key in reports[mask])
                for mask in range(4096)
            )
            full = reports[4095]
            fn = make_value_functions(full)["G2"]
            values = [fn(reports[mask]) for mask in range(4096)]
            truth = exact_shapley(values)
            game = state_game(join_id, "G2", items, full, fn)
            (allocation, diagnostics), costs = timed(lambda g=game: run_s6(g))
            error = max_abs_error(allocation, truth)
            if max_sql_error != 0 or error > TOL:
                raise AssertionError(f"replicate {seed}/{join_id}: sql={max_sql_error}, shapley={error}")
            replicate_rows.append({
                "seed": seed, "join_id": join_id, "game_id": "G2",
                "sql_seconds": sql_seconds, "sql_lineage_max_error": max_sql_error,
                "s6_end_to_end_seconds": costs["elapsed_seconds"], "max_player_error": error,
                "python_peak_bytes": costs["python_peak_bytes"],
                "reachable_evidence_states": diagnostics.get("maximum_frontier_states"),
                "state_transitions": diagnostics.get("state_transitions"),
                "status": "SUCCESS_EXACT",
            })
        c.close()
    write_csv(OUT / "replicate_instances.csv", replicate_rows)
    replicate_summary = []
    for join_id in ("J0", "J1", "J2"):
        subset = [row for row in replicate_rows if row["join_id"] == join_id]
        for metric in ("sql_seconds", "s6_end_to_end_seconds", "python_peak_bytes"):
            values = sorted(float(row[metric]) for row in subset)
            replicate_summary.append({
                "join_id": join_id, "game_id": "G2", "metric": metric,
                "independent_instances": len(values), "median": statistics.median(values),
                "q1": values[1], "q3": values[3], "iqr": values[3] - values[1],
                "sampling_unit": "independently generated seed instance",
            })
    write_csv(OUT / "replicate_summary.csv", replicate_summary)

    # Applicability and boundary records, including non-executed methods.
    applicability = []
    for join_id in ("J0", "J1", "J2"):
        for game_id in ("G0", "G1", "G2"):
            entries = [
                ("B0", "APPLICABLE_EXECUTED_EXACT", "4096 coalition DuckDB SQL truth"),
                ("B1_ABRAMOVICH", "APPLICABLE_EXECUTED_EXACT" if game_id == "G0" else "MATHEMATICAL_INPUT_NOT_BOOLEAN_ADDITIVE_OUTPUT", "official DNF backend; manual SQL grounding frontend"),
                ("B2_COORDINATE_DP", "APPLICABLE_EXECUTED_EXACT" if game_id == "G1" else "OUTSIDE_METHOD_SCOPE", "G1 coordinate additivity; JOIN evidence state used for J1/J2"),
                ("B3_JOINT_STATE_DP", "APPLICABLE_EXECUTED_EXACT", "supplemented JOIN evidence readiness state"),
                ("B4_LEAF_FACTOR", "APPLICABLE_EXECUTED_EXACT" if join_id == "J0" else "LEAF_PARTITION_ASSUMPTION_FAILS_CROSS_PLAYER_JOIN", "J0 uses the verified 16D leaf partition; J1/J2 cross leaf/source factors"),
                ("B5_H5R_S4_S6", "APPLICABLE_EXECUTED_EXACT", "same evidence state; all-player shared solve"),
                ("B6_LUO", "THEOREM_REDUCTION_VALIDATED_NO_OFFICIAL_FRONTEND" if game_id == "G0" else "INDEPENDENT_UTILITY_ASSUMPTION_FAILS", "global G1/G2 scores are not sums of fixed independent output utilities"),
            ]
            for method, status, reason in entries:
                applicability.append({"join_id": join_id, "game_id": game_id, "method": method, "status": status, "reason": reason})
    write_csv(OUT / "algorithm_applicability_matrix.csv", applicability)

    after = {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL}
    if before != after:
        raise AssertionError("historical files changed")
    write_json(OUT / "historical_hashes.json", {"before": before, "after": after, "unchanged": True})
    summary = {
        "status": "H3_JV_COMPLETED_AND_PAUSED",
        "fixed_units": 9,
        "full_sql_coalition_evaluations": 9 * 4096,
        "independent_instances_per_join": 5,
        "all_sql_lineage_checks_passed": True,
        "all_executed_exact_algorithms_passed_1e_9": True,
        "historical_files_unchanged": True,
        "n16_extension": "NOT_RUN_SCOPE_PAUSED_AFTER_REQUIRED_12_PLAYER_AUDIT",
        "duckdb_version": duckdb.__version__,
    }
    write_json(OUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
