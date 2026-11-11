from __future__ import annotations

import csv
import gc
import hashlib
import itertools
import json
import math
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import duckdb


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(OFFICIAL)]

from aggregate_report_shapley.exact_shapley import exact_shapley_subset  # noqa: E402
from experiments.run_ab_n2_ab_j1_2026_10_31 import (  # noqa: E402
    DNFCircuit,
    run_component,
)


OUT = ROOT / "outputs" / "v4_0" / "AB_J2_2026_10_31"
SQL_OUT = OUT / "sql"
FIG_OUT = OUT / "figures"
PLAYERS = ("p1", "p2", "p3", "p4", "p5", "p6")
PLAYER_INDEX = {player: index for index, player in enumerate(PLAYERS)}
GAMES = ("Q1_COUNT_STAR_BAG", "Q2_COUNT_DISTINCT_KEY", "Q3_HAVING_COUNT_GE_2")
STRICT_TOLERANCE = 1e-12

HISTORICAL = (
    ROOT / "reports" / "Abramovich原生SQL最小适配验证_2026-10-31.md",
    ROOT / "reports" / "Abramovich_AB_N2_AB_J1实验报告_2026-10-31.md",
    ROOT / "reports" / "Abramovich_AB_N3_L_AB_N4_DP实验报告_2026-10-31.md",
    ROOT / "experiments" / "run_ab_n2_ab_j1_2026_10_31.py",
    ROOT / "experiments" / "run_ab_n3_l_n4_dp_2026_10_31.py",
    ROOT / "outputs" / "v4_0" / "AB_NATIVE_SQL" / "ab_n1_minimal_validation.json",
    ROOT / "outputs" / "v4_0" / "AB_N2_AB_J1_2026_10_31" / "manifest.json",
    ROOT / "outputs" / "v4_0" / "AB_N2_AB_J1_2026_10_31" / "AB_J1" / "result.json",
    ROOT / "outputs" / "v4_0" / "AB_N3_L_N4_DP_2026_10_31" / "manifest.json",
    ROOT / "outputs" / "v4_0" / "AB_N3_L_N4_DP_2026_10_31" / "AB_J2_design.json",
    ROOT / "docs" / "AB_J2_控制实验设计_2026-10-31.md",
    ROOT / "config" / "d1p_design.yaml",
    ROOT / "config" / "value_spec_v3_2.yaml",
    OFFICIAL / "README.md",
    OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyCircuit.py",
    OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyEngine.py",
    OFFICIAL / "Algorithms" / "LExaShap" / "Helper_functions.py",
    OFFICIAL / "Advancing_Fact_Attribution_for_Query_Answering.pdf",
)


DDL_SQL = """
CREATE TABLE JLeft(
  record_id VARCHAR NOT NULL,
  player_index INTEGER NOT NULL,
  join_key VARCHAR NOT NULL,
  distinct_key VARCHAR NOT NULL
);
CREATE TABLE JRight(
  record_id VARCHAR NOT NULL,
  player_index INTEGER NOT NULL,
  join_key VARCHAR NOT NULL
);
""".strip()

GROUNDING_SQL = """
SELECT l.distinct_key,
       l.record_id AS left_player,
       r.record_id AS right_player
FROM JLeft l
JOIN JRight r USING (join_key)
ORDER BY l.distinct_key, l.record_id, r.record_id
""".strip()

SELECTED_CTE = """
WITH selected_grounding AS (
  SELECT l.distinct_key,
         l.record_id AS left_player,
         r.record_id AS right_player
  FROM JLeft l
  JOIN JRight r USING (join_key)
  WHERE ((CAST(? AS UBIGINT) >> l.player_index) & 1) = 1
    AND ((CAST(? AS UBIGINT) >> r.player_index) & 1) = 1
)
""".strip()

Q1_SQL = SELECTED_CTE + "\nSELECT COUNT(*) AS bag_grounding_count FROM selected_grounding"
Q2_SQL = SELECTED_CTE + "\nSELECT COUNT(DISTINCT distinct_key) AS distinct_key_count FROM selected_grounding"
Q3_SQL = SELECTED_CTE + """

SELECT COUNT(*) AS passed_key_count
FROM (
  SELECT distinct_key
  FROM selected_grounding
  GROUP BY distinct_key
  HAVING COUNT(*) >= 2
) passed_keys
"""
GROUP_AUDIT_SQL = SELECTED_CTE + """

SELECT distinct_key, COUNT(*) AS grounding_count
FROM selected_grounding
GROUP BY distinct_key
ORDER BY distinct_key
"""


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


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def process_rss_bytes() -> int | None:
    try:
        import psutil

        return int(psutil.Process().memory_info().rss)
    except (ImportError, OSError):
        return None


def memory_start() -> tuple[int | None, int]:
    gc.collect()
    tracemalloc.reset_peak()
    return process_rss_bytes(), tracemalloc.get_traced_memory()[0]


def memory_end(start: tuple[int | None, int]) -> dict[str, int | None]:
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


def dnf_value(dnf: list[frozenset[str]], selected: set[str]) -> int:
    return int(any(clause <= selected for clause in dnf))


def canonical_bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def compile_having_threshold(
    grounding_by_key: dict[str, list[dict[str, Any]]], threshold: int
) -> tuple[dict[str, list[frozenset[str]]], list[dict[str, Any]]]:
    compiled: dict[str, list[frozenset[str]]] = {}
    witness_rows: list[dict[str, Any]] = []
    for distinct_key, items in sorted(grounding_by_key.items()):
        candidates: set[frozenset[str]] = set()
        for combination in itertools.combinations(items, threshold):
            candidates.add(frozenset().union(*(item["clause"] for item in combination)))
        minimal = sorted(
            (candidate for candidate in candidates if not any(other < candidate for other in candidates)),
            key=lambda clause: (len(clause), sorted(clause)),
        )
        compiled[distinct_key] = minimal
        if not minimal:
            witness_rows.append(
                {
                    "distinct_key": distinct_key,
                    "witness_id": "",
                    "variables": "",
                    "variable_count": 0,
                    "satisfied_grounding_ids": "",
                    "satisfied_grounding_count": 0,
                    "every_one_variable_deletion_fails": True,
                    "status": "NO_WITNESS_MAX_GROUNDINGS_BELOW_THRESHOLD",
                }
            )
            continue
        for index, clause in enumerate(minimal, start=1):
            satisfied = [item["grounding_id"] for item in items if item["clause"] <= clause]
            deletion_minimal = all(
                sum(item["clause"] <= (set(clause) - {variable}) for item in items) < threshold
                for variable in clause
            )
            if len(satisfied) < threshold or not deletion_minimal:
                raise AssertionError("HAVING最小满足证据编译失败")
            witness_rows.append(
                {
                    "distinct_key": distinct_key,
                    "witness_id": f"{distinct_key}_w{index}",
                    "variables": json.dumps(sorted(clause), ensure_ascii=False),
                    "variable_count": len(clause),
                    "satisfied_grounding_ids": json.dumps(satisfied),
                    "satisfied_grounding_count": len(satisfied),
                    "every_one_variable_deletion_fails": deletion_minimal,
                    "status": "MINIMAL_SATISFYING_EVIDENCE",
                }
            )
    return compiled, witness_rows


def expression_value(
    components: list[tuple[list[frozenset[str]], Fraction]], selected: set[str]
) -> Fraction:
    return sum((coefficient * dnf_value(dnf, selected) for dnf, coefficient in components), Fraction())


def expression_payload(
    components: list[tuple[list[frozenset[str]], Fraction]], compiler: str
) -> dict[str, Any]:
    return {
        "compiler": compiler,
        "components": [
            {
                "dnf": [sorted(clause) for clause in dnf],
                "coefficient": fraction_text(coefficient),
            }
            for dnf, coefficient in components
        ],
    }


def expression_stats(game: str, payload: dict[str, Any]) -> dict[str, Any]:
    components = payload["components"]
    clauses = [clause for component in components for clause in component["dnf"]]
    return {
        "game": game,
        "component_count": len(components),
        "dnf_clause_count": len(clauses),
        "variable_occurrences": sum(len(clause) for clause in clauses),
        "unique_player_variables": len({variable for clause in clauses for variable in clause}),
        "serialized_canonical_json_bytes": canonical_bytes(payload),
        "compiler": payload["compiler"],
    }


def main() -> None:
    for directory in (OUT, SQL_OUT, FIG_OUT):
        directory.mkdir(parents=True, exist_ok=True)
    historical_before = {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL}
    run_started = time.perf_counter()
    tracemalloc.start()
    mem_started = memory_start()

    design = json.loads(
        (ROOT / "outputs" / "v4_0" / "AB_N3_L_N4_DP_2026_10_31" / "AB_J2_design.json").read_text(
            encoding="utf-8"
        )
    )
    expected_full = {
        "Q1_COUNT_STAR_BAG": int(design["queries"]["J2-Q1-bag-count"]["full_coalition_value_expected"]),
        "Q2_COUNT_DISTINCT_KEY": int(
            design["queries"]["J2-Q2-count-distinct"]["full_coalition_value_expected"]
        ),
        "Q3_HAVING_COUNT_GE_2": int(
            design["queries"]["J2-Q3-having-threshold"]["full_coalition_value_expected"]
        ),
    }

    connection = duckdb.connect(":memory:")
    setup_started = time.perf_counter()
    connection.execute(DDL_SQL)
    left_rows = [("p1", 0, "a", "K1"), ("p2", 1, "a", "K1"), ("p3", 2, "b", "K2")]
    right_rows = [("p4", 3, "a"), ("p5", 4, "a"), ("p6", 5, "b")]
    connection.executemany("INSERT INTO JLeft VALUES (?, ?, ?, ?)", left_rows)
    connection.executemany("INSERT INTO JRight VALUES (?, ?, ?)", right_rows)
    relation_setup_seconds = time.perf_counter() - setup_started

    input_rows = [
        {
            "relation": "JLeft",
            "record_id": record_id,
            "player_index": player_index,
            "join_key": join_key,
            "distinct_key_raw": distinct_key,
            "distinct_key_is_null": False,
        }
        for record_id, player_index, join_key, distinct_key in left_rows
    ] + [
        {
            "relation": "JRight",
            "record_id": record_id,
            "player_index": player_index,
            "join_key": join_key,
            "distinct_key_raw": None,
            "distinct_key_is_null": True,
        }
        for record_id, player_index, join_key in right_rows
    ]
    if {row["record_id"] for row in input_rows} != set(PLAYERS) or len(input_rows) != 6:
        raise AssertionError("AB-J2基础记录与6个玩家不一一对应")

    grounding_started = time.perf_counter()
    raw_grounding = connection.execute(GROUNDING_SQL).fetchall()
    grounding_seconds = time.perf_counter() - grounding_started
    grounding_rows: list[dict[str, Any]] = []
    grounding_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    player_occurrences = Counter({player: 0 for player in PLAYERS})
    for index, (distinct_key, left_player, right_player) in enumerate(raw_grounding, start=1):
        clause = frozenset((str(left_player), str(right_player)))
        if not clause <= set(PLAYERS) or len(clause) != 2:
            raise AssertionError("grounding未保持基础记录玩家身份")
        item = {"grounding_id": f"g{index}", "distinct_key": str(distinct_key), "clause": clause}
        grounding_by_key[str(distinct_key)].append(item)
        for player in clause:
            player_occurrences[player] += 1
        grounding_rows.append(
            {
                "grounding_id": item["grounding_id"],
                "distinct_key": str(distinct_key),
                "left_player": str(left_player),
                "right_player": str(right_player),
                "source_clause": json.dumps(sorted(clause)),
                "grounding_is_independent_player": False,
            }
        )
    if len(raw_grounding) != 5 or {key: len(items) for key, items in grounding_by_key.items()} != {"K1": 4, "K2": 1}:
        raise AssertionError("实际SQL grounding不符合冻结AB-J2结构")

    occurrence_rows = [
        {
            "player": player,
            "base_relation_rows": 1,
            "grounding_occurrences": player_occurrences[player],
            "player_variable_count": 1,
        }
        for player in PLAYERS
    ]

    # Compile source expressions from actual grounding before reading any coalition SQL result.
    tick = time.perf_counter()
    q1_components = [([item["clause"]], Fraction(1)) for items in grounding_by_key.values() for item in items]
    q1_compile_seconds = time.perf_counter() - tick

    tick = time.perf_counter()
    q2_components = [
        ([item["clause"] for item in items], Fraction(1))
        for _key, items in sorted(grounding_by_key.items())
    ]
    q2_compile_seconds = time.perf_counter() - tick

    tick = time.perf_counter()
    having_by_key, witness_rows = compile_having_threshold(grounding_by_key, threshold=2)
    q3_components = [
        (dnf, Fraction(1)) for _key, dnf in sorted(having_by_key.items()) if dnf
    ]
    q3_compile_seconds = time.perf_counter() - tick
    if {key: len(dnf) for key, dnf in having_by_key.items()} != {"K1": 4, "K2": 0}:
        raise AssertionError("HAVING最小DNF结构与冻结控制设计不一致")

    components_by_game = {
        "Q1_COUNT_STAR_BAG": q1_components,
        "Q2_COUNT_DISTINCT_KEY": q2_components,
        "Q3_HAVING_COUNT_GE_2": q3_components,
    }
    payloads = {
        "Q1_COUNT_STAR_BAG": expression_payload(q1_components, "DIRECT_ARITHMETIC_SUM_OF_SQL_GROUNDINGS"),
        "Q2_COUNT_DISTINCT_KEY": expression_payload(
            q2_components, "MANUAL_GROUP_BY_DISTINCT_KEY_THEN_BOOLEAN_OR"
        ),
        "Q3_HAVING_COUNT_GE_2": expression_payload(
            q3_components, "MANUAL_THRESHOLD_WITNESS_UNION_AND_SUBSUMPTION_MINIMIZATION"
        ),
    }
    payloads["Q3_HAVING_COUNT_GE_2"]["false_keys_omitted_as_zero_components"] = [
        key for key, dnf in sorted(having_by_key.items()) if not dnf
    ]
    expression_stats_rows = [expression_stats(game, payloads[game]) for game in GAMES]

    # Official engine: input is reduced DNF, not raw SQL.
    official_payments = {game: {player: 0.0 for player in PLAYERS} for game in GAMES}
    official_timings = {
        game: {
            "official_untouched_end_to_end_seconds": 0.0,
            "official_dtree_compile_seconds": 0.0,
            "official_backward_solve_seconds": 0.0,
        }
        for game in GAMES
    }
    official_started = time.perf_counter()
    for game, components in components_by_game.items():
        for dnf, coefficient in components:
            payment, timing = run_component([set(clause) for clause in dnf], coefficient)
            for key, value in timing.items():
                official_timings[game][key] += value
            for player, value in payment.items():
                official_payments[game][player] += value
    official_all_games_seconds = time.perf_counter() - official_started

    false_dnf_probe: dict[str, Any]
    try:
        DNFCircuit([])
        false_dnf_probe = {"accepted": True, "exception_type": None, "message": None}
    except Exception as exc:  # official interface boundary probe
        false_dnf_probe = {
            "accepted": False,
            "exception_type": type(exc).__name__,
            "message": str(exc),
        }

    construction_completed_before_oracle = True

    # Execute all 64 coalitions through actual DuckDB SQL.
    alliance_rows: list[dict[str, Any]] = []
    group_audit_rows: list[dict[str, Any]] = []
    tables = {game: [] for game in GAMES}
    sql_seconds = Counter()
    sql_calls = Counter()
    for mask in range(1 << len(PLAYERS)):
        selected = {player for player in PLAYERS if mask & (1 << PLAYER_INDEX[player])}
        raw_values: dict[str, Any] = {}
        for game, query in (
            ("Q1_COUNT_STAR_BAG", Q1_SQL),
            ("Q2_COUNT_DISTINCT_KEY", Q2_SQL),
            ("Q3_HAVING_COUNT_GE_2", Q3_SQL),
        ):
            tick = time.perf_counter()
            raw_values[game] = connection.execute(query, [mask, mask]).fetchone()[0]
            sql_seconds[game] += time.perf_counter() - tick
            sql_calls[game] += 1
        tick = time.perf_counter()
        present_groups = {
            str(key): int(count)
            for key, count in connection.execute(GROUP_AUDIT_SQL, [mask, mask]).fetchall()
        }
        sql_seconds["GROUP_AUDIT"] += time.perf_counter() - tick
        sql_calls["GROUP_AUDIT"] += 1

        normalized = {game: 0 if value is None else int(value) for game, value in raw_values.items()}
        expressions = {
            game: expression_value(components_by_game[game], selected) for game in GAMES
        }
        for game in GAMES:
            tables[game].append(Fraction(normalized[game]))
        alliance_rows.append(
            {
                "mask": mask,
                "coalition_size": mask.bit_count(),
                "coalition_players": json.dumps(sorted(selected)),
                "q1_sql_raw": raw_values["Q1_COUNT_STAR_BAG"],
                "q1_sql_is_null": raw_values["Q1_COUNT_STAR_BAG"] is None,
                "q1_normalized": normalized["Q1_COUNT_STAR_BAG"],
                "q1_source_expression": fraction_text(expressions["Q1_COUNT_STAR_BAG"]),
                "q1_error": fraction_text(expressions["Q1_COUNT_STAR_BAG"] - normalized["Q1_COUNT_STAR_BAG"]),
                "q2_sql_raw": raw_values["Q2_COUNT_DISTINCT_KEY"],
                "q2_sql_is_null": raw_values["Q2_COUNT_DISTINCT_KEY"] is None,
                "q2_normalized": normalized["Q2_COUNT_DISTINCT_KEY"],
                "q2_source_expression": fraction_text(expressions["Q2_COUNT_DISTINCT_KEY"]),
                "q2_error": fraction_text(expressions["Q2_COUNT_DISTINCT_KEY"] - normalized["Q2_COUNT_DISTINCT_KEY"]),
                "q3_sql_raw": raw_values["Q3_HAVING_COUNT_GE_2"],
                "q3_sql_is_null": raw_values["Q3_HAVING_COUNT_GE_2"] is None,
                "q3_normalized": normalized["Q3_HAVING_COUNT_GE_2"],
                "q3_source_expression": fraction_text(expressions["Q3_HAVING_COUNT_GE_2"]),
                "q3_error": fraction_text(expressions["Q3_HAVING_COUNT_GE_2"] - normalized["Q3_HAVING_COUNT_GE_2"]),
            }
        )
        for key in ("K1", "K2"):
            raw_count = present_groups.get(key)
            group_audit_rows.append(
                {
                    "mask": mask,
                    "coalition_players": json.dumps(sorted(selected)),
                    "distinct_key": key,
                    "raw_group_row_present": raw_count is not None,
                    "raw_group_grounding_count": raw_count,
                    "normalized_missing_group_count": 0 if raw_count is None else raw_count,
                    "having_count_ge_2": int(raw_count is not None and raw_count >= 2),
                }
            )

    for game in GAMES:
        if len(tables[game]) != 64:
            raise AssertionError("没有对全部64个联盟运行SQL")
    if any(
        row[error_column] != "0/1"
        for row in alliance_rows
        for error_column in ("q1_error", "q2_error", "q3_error")
    ):
        raise AssertionError("SQL联盟值与来源表达不一致")
    observed_full = {game: int(tables[game][-1]) for game in GAMES}
    if observed_full != expected_full:
        raise AssertionError(f"实际SQL满联盟结果与冻结预期不同: {observed_full}")

    # Independent exact Shapley and official comparison.
    exact_started = time.perf_counter()
    exact = {game: exact_shapley_subset(tables[game], len(PLAYERS)) for game in GAMES}
    exact_seconds = time.perf_counter() - exact_started
    shapley_rows: list[dict[str, Any]] = []
    correctness_rows: list[dict[str, Any]] = []
    for game in GAMES:
        exact_sum = sum(exact[game], Fraction())
        efficiency_target = tables[game][-1] - tables[game][0]
        max_official_error = 0.0
        for index, player in enumerate(PLAYERS):
            error = official_payments[game][player] - float(exact[game][index])
            max_official_error = max(max_official_error, abs(error))
            shapley_rows.append(
                {
                    "game": game,
                    "player": player,
                    "exact_record_shapley": fraction_text(exact[game][index]),
                    "exact_record_shapley_float": float(exact[game][index]),
                    "official_reduced_DNF_shapley": official_payments[game][player],
                    "official_error": error,
                }
            )
        max_alliance_error = max(
            abs(Fraction(row[{"Q1_COUNT_STAR_BAG": "q1_error", "Q2_COUNT_DISTINCT_KEY": "q2_error", "Q3_HAVING_COUNT_GE_2": "q3_error"}[game]]))
            for row in alliance_rows
        )
        raw_nulls = sum(
            bool(row[{"Q1_COUNT_STAR_BAG": "q1_sql_is_null", "Q2_COUNT_DISTINCT_KEY": "q2_sql_is_null", "Q3_HAVING_COUNT_GE_2": "q3_sql_is_null"}[game]])
            for row in alliance_rows
        )
        correctness_rows.append(
            {
                "game": game,
                "coalitions_executed_in_duckdb": 64,
                "observed_empty_value": fraction_text(tables[game][0]),
                "observed_full_value": fraction_text(tables[game][-1]),
                "frozen_expected_full_value": expected_full[game],
                "maximum_alliance_value_error": fraction_text(max_alliance_error),
                "exact_shapley_sum": fraction_text(exact_sum),
                "efficiency_target_vN_minus_v0": fraction_text(efficiency_target),
                "efficiency_error": fraction_text(exact_sum - efficiency_target),
                "maximum_official_error": max_official_error,
                "strict_tolerance": STRICT_TOLERANCE,
                "raw_sql_null_count": raw_nulls,
                "passed": max_alliance_error == 0 and exact_sum == efficiency_target and max_official_error <= STRICT_TOLERANCE,
            }
        )
    if not all(row["passed"] for row in correctness_rows):
        raise AssertionError("AB-J2正确性关卡失败")

    distribution_rows: list[dict[str, Any]] = []
    descriptive_rows: list[dict[str, Any]] = []
    for game in GAMES:
        frequency = Counter(int(value) for value in tables[game])
        mean = sum(tables[game], Fraction()) / len(tables[game])
        variance = sum(((value - mean) ** 2 for value in tables[game]), Fraction()) / len(tables[game])
        for value in range(max(frequency) + 1):
            distribution_rows.append(
                {"game": game, "coalition_value": value, "coalition_count": frequency[value], "total_coalitions": 64}
            )
        descriptive_rows.append(
            {
                "game": game,
                "finite_population_size": 64,
                "minimum": min(tables[game]),
                "maximum": max(tables[game]),
                "uniform_coalition_mean": fraction_text(mean),
                "uniform_coalition_population_variance": fraction_text(variance),
                "inferential_test": "NOT_APPLICABLE_COMPLETE_ENUMERATION",
                "confidence_interval": "NOT_APPLICABLE_NO_SAMPLING",
            }
        )

    source_compile_seconds = {
        "Q1_COUNT_STAR_BAG": q1_compile_seconds,
        "Q2_COUNT_DISTINCT_KEY": q2_compile_seconds,
        "Q3_HAVING_COUNT_GE_2": q3_compile_seconds,
    }
    cost_rows: list[dict[str, Any]] = []
    stats_by_game = {row["game"]: row for row in expression_stats_rows}
    for game in GAMES:
        cost_rows.append(
            {
                "game": game,
                "input_relation_rows": 6,
                "join_groundings": 5,
                "distinct_keys": 2,
                "dnf_components": stats_by_game[game]["component_count"],
                "dnf_clauses": stats_by_game[game]["dnf_clause_count"],
                "variable_occurrences": stats_by_game[game]["variable_occurrences"],
                "serialized_expression_bytes": stats_by_game[game]["serialized_canonical_json_bytes"],
                "source_compile_seconds": source_compile_seconds[game],
                "official_dtree_compile_seconds": official_timings[game]["official_dtree_compile_seconds"],
                "official_shapley_solve_seconds": official_timings[game]["official_backward_solve_seconds"],
                "official_untouched_end_to_end_seconds": official_timings[game]["official_untouched_end_to_end_seconds"],
                "duckdb_64_alliance_seconds": sql_seconds[game],
                "duckdb_sql_calls": sql_calls[game],
            }
        )

    applicability_rows = [
        {
            "query": "Q1 COUNT(*)",
            "join_semantics": "5个grounding按bag算术求和",
            "mathematical_status": "DIRECT_SUM_OF_BOOLEAN_GROUNDINGS",
            "official_reduced_input": "DIRECTLY_SUPPORTED_AS_LIST_OF_DNFS_AND_COEFFICIENTS",
            "official_native_sql_compiler": "NOT_PROVIDED; PROJECT_MINIMAL_GROUNDING_COMPILER_USED",
            "this_experiment": "PASS_EXACT",
            "generalization_boundary": "grounding数量可能随JOIN扇出增长",
        },
        {
            "query": "Q2 COUNT(DISTINCT key)",
            "join_semantics": "同key内grounding做Boolean OR，不同key指标相加",
            "mathematical_status": "EXACT_KEYWISE_BOOLEAN_REDUCTION",
            "official_reduced_input": "BOOLEAN_DNF_ENGINE_ACCEPTS_MANUALLY_REDUCED_INPUT",
            "official_native_sql_compiler": "NO_DECLARED_COUNT_DISTINCT_INTERFACE",
            "this_experiment": "PASS_AFTER_MANUAL_REDUCTION",
            "generalization_boundary": "Standke结果要求查询结构条件；本实验不证明一般可解",
        },
        {
            "query": "Q3 GROUP BY key HAVING COUNT(*)>=2",
            "join_semantics": "每个key先计grounding并判阈值，再统计通过key",
            "mathematical_status": "EXACT_MONOTONE_THRESHOLD_DNF_FOR_FIXED_SMALL_GAME",
            "official_reduced_input": "BOOLEAN_DNF_ENGINE_ACCEPTS_NONEMPTY_MANUALLY_COMPILED_WITNESSES",
            "official_native_sql_compiler": "NO_DECLARED_HAVING_THRESHOLD_INTERFACE",
            "this_experiment": "PASS_AFTER_MANUAL_THRESHOLD_COMPILATION",
            "generalization_boundary": "候选证据组合数可达C(m,threshold)，固定2x2结果不代表可扩展",
        },
    ]

    # Persist SQL, raw evidence, and reproducibility data.
    sql_files = {
        "create_relations.sql": DDL_SQL,
        "grounding.sql": GROUNDING_SQL,
        "q1_count_star.sql": Q1_SQL,
        "q2_count_distinct.sql": Q2_SQL,
        "q3_group_having.sql": Q3_SQL,
        "group_missing_audit.sql": GROUP_AUDIT_SQL,
    }
    for filename, sql in sql_files.items():
        (SQL_OUT / filename).write_text(sql + "\n", encoding="utf-8")
    write_csv(OUT / "input_relations.csv", input_rows)
    write_csv(OUT / "grounding.csv", grounding_rows)
    write_csv(OUT / "player_grounding_occurrences.csv", occurrence_rows)
    write_csv(OUT / "having_minimal_witnesses.csv", witness_rows)
    write_json(OUT / "source_expressions.json", payloads)
    write_csv(OUT / "source_expression_stats.csv", expression_stats_rows)
    write_csv(OUT / "alliance_truth.csv", alliance_rows)
    write_csv(OUT / "alliance_group_missing_null_audit.csv", group_audit_rows)
    write_csv(OUT / "record_shapley.csv", shapley_rows)
    write_csv(OUT / "correctness_summary.csv", correctness_rows)
    write_csv(OUT / "coalition_value_distribution.csv", distribution_rows)
    write_csv(OUT / "descriptive_statistics.csv", descriptive_rows)
    write_csv(OUT / "costs.csv", cost_rows)
    write_csv(OUT / "join_algorithm_applicability_matrix.csv", applicability_rows)

    historical_after = {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL}
    if historical_before != historical_after:
        raise AssertionError("历史数据、官方源码或历史结果发生变化")
    memory = memory_end(mem_started)
    manifest = {
        "stage": "AB-J2",
        "status": "COMPLETED_CORRECTNESS_AND_APPLICABILITY_AUDIT",
        "scope": "INDEPENDENT_6_PLAYER_CONTROL_GAME_ONLY",
        "d1p_modified": False,
        "players": list(PLAYERS),
        "input_relation_rows": 6,
        "groundings": 5,
        "distinct_keys": 2,
        "groundings_are_players": False,
        "actual_full_sql_values": observed_full,
        "frozen_expected_full_values_checked_posthoc": expected_full,
        "alliance_sql_executions": {game: sql_calls[game] for game in GAMES},
        "alliance_count": 64,
        "maximum_alliance_value_error": "0/1",
        "maximum_official_error": max(row["maximum_official_error"] for row in correctness_rows),
        "efficiency_errors": {row["game"]: row["efficiency_error"] for row in correctness_rows},
        "missing_group_rows": sum(not row["raw_group_row_present"] for row in group_audit_rows),
        "raw_outer_aggregate_nulls": sum(
            row[column]
            for row in alliance_rows
            for column in ("q1_sql_is_null", "q2_sql_is_null", "q3_sql_is_null")
        ),
        "false_dnf_official_probe": false_dnf_probe,
        "construction_completed_before_oracle": construction_completed_before_oracle,
        "official_source_modified": False,
        "historical_hashes_before": historical_before,
        "historical_hashes_after": historical_after,
        "timings_seconds": {
            "relation_setup": relation_setup_seconds,
            "grounding_sql": grounding_seconds,
            "source_compilation": source_compile_seconds,
            "official_all_games_harness_wall": official_all_games_seconds,
            "duckdb_by_game": {game: sql_seconds[game] for game in GAMES},
            "duckdb_group_missing_audit": sql_seconds["GROUP_AUDIT"],
            "exact_shapley_oracle": exact_seconds,
            "whole_run": time.perf_counter() - run_started,
        },
        "memory": memory,
        "environment": {
            "python": sys.version,
            "duckdb": duckdb.__version__,
            "official_shapley_source_sha256": sha256(
                OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyCircuit.py"
            ),
            "d1p_design_sha256": sha256(ROOT / "config" / "d1p_design.yaml"),
            "value_spec_sha256": sha256(ROOT / "config" / "value_spec_v3_2.yaml"),
        },
        "statistical_scope": {
            "sampling": "NONE_COMPLETE_ENUMERATION_OF_64_COALITIONS",
            "inferential_tests": "NOT_APPLICABLE",
            "confidence_intervals": "NOT_APPLICABLE",
            "timing_repetitions": 1,
            "timing_interpretation": "DESCRIPTIVE_REPRODUCTION_RECORD_ONLY",
        },
        "not_executed": ["D1-P modification", "V2 joint experiment", "large-scale expansion"],
    }
    write_json(OUT / "historical_hashes.json", {"before": historical_before, "after": historical_after})
    write_json(OUT / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
