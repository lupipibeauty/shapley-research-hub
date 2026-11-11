from __future__ import annotations

import csv
import hashlib
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
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from aggregate_report_shapley.d1p import all_incremental_states, load_d1p_spec, state_for_mask  # noqa: E402
from aggregate_report_shapley.d1p_sql import create_d1p_database  # noqa: E402
from aggregate_report_shapley.d1p_values import D1PValueSuite  # noqa: E402
from aggregate_report_shapley.exact_shapley import exact_shapley_subset  # noqa: E402
from experiments.run_ab_n2_ab_j1_2026_10_31 import n2_grounding_sql, run_component  # noqa: E402


OUT = ROOT / "outputs" / "v4_0" / "AB_N3_L_N4_DP_2026_10_31"
N3_OUT = OUT / "AB_N3_L"
N4_OUT = OUT / "AB_N4_DP"
FIG_OUT = OUT / "figures"
LINEAR_METRICS = ("record_count", "category_a_target_count", "attribute_present_count")
RATIO_METRICS = ("category_a_target_share", "category_b_target_share")
METRIC_INDEX = {
    "record_count": 0,
    "category_a_target_count": 1,
    "attribute_present_count": 2,
}
HISTORICAL = (
    ROOT / "reports" / "Abramovich_AB_N2_AB_J1实验报告_2026-10-31.md",
    ROOT / "outputs" / "v4_0" / "AB_N2_AB_J1_2026_10_31" / "AB_N2" / "result.json",
    ROOT / "outputs" / "v4_0" / "AB_N2_AB_J1_2026_10_31" / "AB_N2" / "grounding.csv",
    ROOT / "outputs" / "v4_0" / "AB_N2_AB_J1_2026_10_31" / "AB_J1" / "result.json",
    ROOT / "outputs" / "v4_0" / "R2_3" / "exact_targets.json",
    ROOT / "config" / "d1p_design.yaml",
    ROOT / "config" / "value_spec_v3_2.yaml",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def parse_fraction(text: str) -> Fraction:
    return Fraction(text)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"空CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def score_formula(c: int, t: int, C: int, F: int) -> Fraction:
    return Fraction(t, F) - Fraction(abs(c * F - t * C), F * F)


def coordinate_types(spec, node: str, metric: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for record in spec.records:
        if node not in spec.ancestors[record.leaf_node_id]:
            result[record.record_id] = "irrelevant"
        elif metric == "category_a_target_share":
            result[record.record_id] = (
                "target" if record.category_a_id == spec.category_a_target else "non_target"
            )
        elif metric == "category_b_target_share":
            if not record.attribute_present:
                result[record.record_id] = "irrelevant"
            else:
                result[record.record_id] = (
                    "target" if record.category_b_id == spec.category_b_target else "non_target"
                )
        else:
            raise KeyError(metric)
    return result


def dp_for_representative(
    *, n: int, type_by_player: dict[str, str], representative: str, focal_type: str,
    F: int, C: int, node: str, metric: str,
) -> tuple[Fraction, dict[str, Any], list[dict[str, Any]]]:
    started = time.perf_counter()
    dp: Counter[tuple[int, int, int]] = Counter({(0, 0, 0): 1})
    transition_updates = 0
    unique_state_writes = 0
    other_types = [kind for player, kind in type_by_player.items() if player != representative]
    for kind in other_types:
        new: Counter[tuple[int, int, int]] = Counter()
        for (a, b, k), count in dp.items():
            new[(a, b, k)] += count
            transition_updates += 1
            if kind == "target":
                included = (a + 1, b, k + 1)
            elif kind == "non_target":
                included = (a, b + 1, k + 1)
            else:
                included = (a, b, k + 1)
            new[included] += count
            transition_updates += 1
        unique_state_writes += len(new)
        dp = new

    target_other = sum(kind == "target" for kind in other_types)
    non_target_other = sum(kind == "non_target" for kind in other_types)
    irrelevant_other = sum(kind == "irrelevant" for kind in other_types)
    if sum(dp.values()) != 1 << (n - 1):
        raise AssertionError("DP组合总数不等于2^(n-1)")
    shapley = Fraction()
    terminal_rows: list[dict[str, Any]] = []
    for (a, b, k), coalition_count in sorted(dp.items()):
        d = k - a - b
        expected = (
            math.comb(target_other, a)
            * math.comb(non_target_other, b)
            * math.comb(irrelevant_other, d)
            if 0 <= a <= target_other and 0 <= b <= non_target_other and 0 <= d <= irrelevant_other
            else 0
        )
        if coalition_count != expected:
            raise AssertionError("DP状态组合数量与闭式组合数不一致")
        before = score_formula(a, a + b, C, F)
        if focal_type == "target":
            after = score_formula(a + 1, a + b + 1, C, F)
        elif focal_type == "non_target":
            after = score_formula(a, a + b + 1, C, F)
        else:
            after = before
        marginal = after - before
        shapley_weight = Fraction(1, n * math.comb(n - 1, k))
        contribution = coalition_count * shapley_weight * marginal
        shapley += contribution
        terminal_rows.append(
            {
                "node": node,
                "metric": metric,
                "representative": representative,
                "focal_type": focal_type,
                "target_predecessors": a,
                "non_target_predecessors": b,
                "irrelevant_predecessors": d,
                "coalition_size_k": k,
                "coalition_combination_count": coalition_count,
                "closed_form_combination_count": expected,
                "marginal": fraction_text(marginal),
                "shapley_weight": fraction_text(shapley_weight),
                "weighted_contribution": fraction_text(contribution),
            }
        )
    detail = {
        "node": node,
        "metric": metric,
        "focal_type": focal_type,
        "representative": representative,
        "players_in_type": sum(kind == focal_type for kind in type_by_player.values()),
        "F": F,
        "C": C,
        "non_target_full": F - C,
        "irrelevant_full": n - F,
        "terminal_state_count": len(dp),
        "terminal_combination_total": sum(dp.values()),
        "transition_updates": transition_updates,
        "unique_state_writes_across_steps": unique_state_writes,
        "shapley_per_symmetric_player": fraction_text(shapley),
        "runtime_seconds": time.perf_counter() - started,
    }
    return shapley, detail, terminal_rows


def main() -> None:
    for directory in (OUT, N3_OUT, N4_OUT, FIG_OUT):
        directory.mkdir(parents=True, exist_ok=True)
    historical_before = {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL}
    tracemalloc.start()
    run_started = time.perf_counter()

    spec = load_d1p_spec(ROOT / "config" / "d1p_design.yaml")
    full_state = state_for_mask(spec.full_mask, spec)
    suite = D1PValueSuite(spec, full_state, ROOT / "config" / "value_spec_v3_2.yaml")
    connection = duckdb.connect(":memory:")
    create_d1p_database(connection, spec)

    # ---------------- AB-N3-L construction: no coalition value table exists yet. ----------------
    n3_started = time.perf_counter()
    grounding_sql = n2_grounding_sql()
    tick = time.perf_counter()
    grounding = connection.execute(grounding_sql).fetchall()
    grounding_seconds = time.perf_counter() - tick
    source_expressions: dict[tuple[str, str], list[tuple[list[set[str]], Fraction]]] = defaultdict(list)
    coordinate_rows: list[dict[str, Any]] = []
    coordinate_seen: set[tuple[str, str]] = set()
    assembly_started = time.perf_counter()
    for _player_index, record_id, node, count_c, e2_c, attr_c, _optional_record_id in grounding:
        raw_coefficients = {
            "record_count": int(count_c),
            "category_a_target_count": int(e2_c),
            "attribute_present_count": int(attr_c),
        }
        for metric, raw_coefficient in raw_coefficients.items():
            full_denominator = full_state.counts[str(node)][METRIC_INDEX[metric]]
            fixed_scale = suite.revenue * suite.coordinate_weights[(str(node), metric)] / full_denominator
            if raw_coefficient:
                source_expressions[(str(node), metric)].append(
                    ([{str(record_id)}], fixed_scale * raw_coefficient)
                )
            key = (str(node), metric)
            if key not in coordinate_seen:
                coordinate_seen.add(key)
                coordinate_rows.append(
                    {
                        "node": str(node),
                        "metric": metric,
                        "frozen_coordinate_weight": fraction_text(suite.coordinate_weights[key]),
                        "full_denominator": full_denominator,
                        "revenue": fraction_text(suite.revenue),
                        "per_unit_source_coefficient": fraction_text(fixed_scale),
                    }
                )
    source_assembly_seconds = time.perf_counter() - assembly_started
    if len(coordinate_seen) != 21:
        raise AssertionError("AB-N3-L应包含21个计数坐标")
    component_count = sum(len(items) for items in source_expressions.values())
    if component_count != 84:
        raise AssertionError(f"AB-N3-L组件数应为84，实际{component_count}")
    for row in coordinate_rows:
        row["component_count"] = len(source_expressions[(row["node"], row["metric"])])

    n3_official = {record.record_id: 0.0 for record in spec.records}
    n3_exact_source = {record.record_id: Fraction() for record in spec.records}
    official_timings = Counter()
    expression_json: dict[str, list[dict[str, Any]]] = {}
    for node in spec.nodes:
        for metric in LINEAR_METRICS:
            key = (node, metric)
            expression_json[f"{node}|{metric}"] = []
            for dnf, coefficient in source_expressions[key]:
                payment, timings = run_component(dnf, coefficient)
                official_timings.update(timings)
                player = next(iter(dnf[0]))
                n3_exact_source[player] += coefficient
                for name, value in payment.items():
                    n3_official[name] += value
                expression_json[f"{node}|{metric}"].append(
                    {"dnf": [sorted(clause) for clause in dnf], "coefficient": fraction_text(coefficient)}
                )
    n3_algorithm_seconds = time.perf_counter() - n3_started

    # ---------------- AB-N4-DP construction: only full counts and player types. ----------------
    n4_started = time.perf_counter()
    dp_coordinate_payments: dict[tuple[str, str], dict[str, Fraction]] = {}
    dp_state_summary: list[dict[str, Any]] = []
    dp_terminal_rows: list[dict[str, Any]] = []
    ratio_weighted_payment = {record.record_id: Fraction() for record in spec.records}
    total_transition_updates = 0
    for node in spec.nodes:
        for metric in RATIO_METRICS:
            types = coordinate_types(spec, node, metric)
            target_players = [player for player, kind in types.items() if kind == "target"]
            non_target_players = [player for player, kind in types.items() if kind == "non_target"]
            irrelevant_players = [player for player, kind in types.items() if kind == "irrelevant"]
            F = len(target_players) + len(non_target_players)
            C = len(target_players)
            if metric == "category_a_target_share":
                expected_F, expected_C = full_state.counts[node][0], full_state.counts[node][1]
            else:
                expected_F, expected_C = full_state.counts[node][2], full_state.counts[node][3]
            if (F, C) != (expected_F, expected_C):
                raise AssertionError("DP玩家分类与满表计数不一致")
            payments = {record.record_id: Fraction() for record in spec.records}
            for focal_type, players in (("target", target_players), ("non_target", non_target_players)):
                if not players:
                    continue
                representative = players[0]
                value, detail, terminal = dp_for_representative(
                    n=spec.player_count,
                    type_by_player=types,
                    representative=representative,
                    focal_type=focal_type,
                    F=F,
                    C=C,
                    node=node,
                    metric=metric,
                )
                total_transition_updates += int(detail["transition_updates"])
                dp_state_summary.append(detail)
                dp_terminal_rows.extend(terminal)
                for player in players:
                    payments[player] = value
            if irrelevant_players:
                dp_state_summary.append(
                    {
                        "node": node,
                        "metric": metric,
                        "focal_type": "irrelevant",
                        "representative": irrelevant_players[0],
                        "players_in_type": len(irrelevant_players),
                        "F": F,
                        "C": C,
                        "non_target_full": F - C,
                        "irrelevant_full": spec.player_count - F,
                        "terminal_state_count": 0,
                        "terminal_combination_total": 0,
                        "transition_updates": 0,
                        "unique_state_writes_across_steps": 0,
                        "shapley_per_symmetric_player": "0/1",
                        "runtime_seconds": 0.0,
                    }
                )
            if sum(payments.values(), Fraction()) != 1:
                raise AssertionError(f"比例坐标DP效率性失败: {node}/{metric}")
            dp_coordinate_payments[(node, metric)] = payments
            frozen_weight = suite.revenue * suite.coordinate_weights[(node, metric)]
            for player, value in payments.items():
                ratio_weighted_payment[player] += frozen_weight * value
    n4_dp_algorithm_seconds = time.perf_counter() - n4_started
    algorithm_construction_completed_before_truth = True
    construction_completed_timestamp = time.perf_counter()

    # ---------------- Post-hoc exact oracles only after both algorithms exist. ----------------
    oracle_started = time.perf_counter()
    states = all_incremental_states(spec)
    all_values = suite.all_values(states)
    exact_payload = json.loads(
        (ROOT / "outputs" / "v4_0" / "R2_3" / "exact_targets.json").read_text(encoding="utf-8")
    )
    exact_existing_v1 = {
        record.record_id: parse_fraction(exact_payload["record_shapley"]["V1"][index])
        for index, record in enumerate(spec.records)
    }
    truth_loaded_timestamp = time.perf_counter()

    # N3-L alliance and payment validation.
    linear_table: list[Fraction] = []
    n3_alliance_rows: list[dict[str, Any]] = []
    player_index = {record.record_id: record.player_index for record in spec.records}
    for mask, state in enumerate(states):
        direct = suite.revenue * sum(
            (
                suite.coordinate_weights[(node, metric)] * suite.coordinate_score(state, node, metric)
                for node in spec.nodes
                for metric in LINEAR_METRICS
            ),
            Fraction(),
        )
        source = sum(
            coefficient
            for player, coefficient in n3_exact_source.items()
            if mask & (1 << player_index[player])
        )
        linear_table.append(direct)
        n3_alliance_rows.append(
            {
                "mask": mask,
                "coalition_size": mask.bit_count(),
                "source_expression_value": fraction_text(source),
                "frozen_linear_coordinate_value": fraction_text(direct),
                "error": fraction_text(source - direct),
            }
        )
    if any(row["error"] != "0/1" for row in n3_alliance_rows):
        raise AssertionError("AB-N3-L联盟价值不一致")
    exact_linear = exact_shapley_subset(linear_table, spec.player_count)
    n3_shapley_rows: list[dict[str, Any]] = []
    for index, record in enumerate(spec.records):
        n3_shapley_rows.append(
            {
                "record_id": record.record_id,
                "official_source_shapley": n3_official[record.record_id],
                "exact_source_fraction": fraction_text(n3_exact_source[record.record_id]),
                "exact_4096_linear_shapley": fraction_text(exact_linear[index]),
                "official_minus_exact": n3_official[record.record_id] - float(exact_linear[index]),
            }
        )
        if n3_exact_source[record.record_id] != exact_linear[index]:
            raise AssertionError("AB-N3-L线性Shapley不一致")
        if abs(n3_official[record.record_id] - float(exact_linear[index])) > 1e-10:
            raise AssertionError("AB-N3-L官方浮点误差超限")

    # Per-ratio-coordinate value and Shapley validation.
    ratio_value_rows: list[dict[str, Any]] = []
    ratio_coordinate_shapley_rows: list[dict[str, Any]] = []
    ratio_table_total = [Fraction() for _ in states]
    ratio_exact_weighted = {record.record_id: Fraction() for record in spec.records}
    for node in spec.nodes:
        for metric in RATIO_METRICS:
            if metric == "category_a_target_share":
                F, C = full_state.counts[node][0], full_state.counts[node][1]
                c_index, t_index = 1, 0
            else:
                F, C = full_state.counts[node][2], full_state.counts[node][3]
                c_index, t_index = 3, 2
            coordinate_table: list[Fraction] = []
            for mask, state in enumerate(states):
                c = state.counts[node][c_index]
                t = state.counts[node][t_index]
                formula = score_formula(c, t, C, F)
                frozen = suite.coordinate_score(state, node, metric)
                coordinate_table.append(frozen)
                weighted = suite.revenue * suite.coordinate_weights[(node, metric)] * formula
                ratio_table_total[mask] += weighted
                ratio_value_rows.append(
                    {
                        "mask": mask,
                        "node": node,
                        "metric": metric,
                        "c": c,
                        "t": t,
                        "C": C,
                        "F": F,
                        "formula_value": fraction_text(formula),
                        "frozen_coordinate_value": fraction_text(frozen),
                        "error": fraction_text(formula - frozen),
                    }
                )
            exact_coordinate = exact_shapley_subset(coordinate_table, spec.player_count)
            dp_payments = dp_coordinate_payments[(node, metric)]
            coord_weight = suite.revenue * suite.coordinate_weights[(node, metric)]
            for index, record in enumerate(spec.records):
                dp_value = dp_payments[record.record_id]
                error = dp_value - exact_coordinate[index]
                ratio_coordinate_shapley_rows.append(
                    {
                        "node": node,
                        "metric": metric,
                        "record_id": record.record_id,
                        "player_type": coordinate_types(spec, node, metric)[record.record_id],
                        "dp_coordinate_shapley": fraction_text(dp_value),
                        "exact_4096_coordinate_shapley": fraction_text(exact_coordinate[index]),
                        "error": fraction_text(error),
                        "frozen_value_weight": fraction_text(coord_weight),
                        "weighted_dp_contribution": fraction_text(coord_weight * dp_value),
                    }
                )
                if error != 0:
                    raise AssertionError("AB-N4-DP逐坐标Shapley不一致")
                ratio_exact_weighted[record.record_id] += coord_weight * exact_coordinate[index]
    if any(row["error"] != "0/1" for row in ratio_value_rows):
        raise AssertionError("AB-N4比例恒等式联盟核验失败")

    v1_table = [Fraction(value) for value in all_values["V1"]]
    exact_v1_recomputed = exact_shapley_subset(v1_table, spec.player_count)
    whole_value_rows: list[dict[str, Any]] = []
    for mask in range(1 << spec.player_count):
        reconstructed = linear_table[mask] + ratio_table_total[mask]
        whole_value_rows.append(
            {
                "mask": mask,
                "coalition_size": mask.bit_count(),
                "linear_source_value": fraction_text(linear_table[mask]),
                "ratio_formula_value": fraction_text(ratio_table_total[mask]),
                "reconstructed_V1": fraction_text(reconstructed),
                "frozen_V1": fraction_text(v1_table[mask]),
                "error": fraction_text(reconstructed - v1_table[mask]),
            }
        )
        if reconstructed != v1_table[mask]:
            raise AssertionError("AB-N3-L+AB-N4-DP整表联盟价值不一致")

    v1_record_rows: list[dict[str, Any]] = []
    for index, record in enumerate(spec.records):
        exact_existing = exact_existing_v1[record.record_id]
        exact_recomputed = exact_v1_recomputed[index]
        linear_part = n3_exact_source[record.record_id]
        ratio_part = ratio_weighted_payment[record.record_id]
        combined = linear_part + ratio_part
        if exact_existing != exact_recomputed or ratio_part != ratio_exact_weighted[record.record_id]:
            raise AssertionError("现有真值、独立精确真值或比例DP对照不一致")
        if combined != exact_existing:
            raise AssertionError("AB-N3-L+AB-N4-DP未重建V1 Shapley")
        v1_record_rows.append(
            {
                "record_id": record.record_id,
                "A_existing_4096_exact_V1": fraction_text(exact_existing),
                "A_recomputed_4096_exact_V1": fraction_text(exact_recomputed),
                "B_official_linear_part_float": n3_official[record.record_id],
                "B_exact_linear_part": fraction_text(linear_part),
                "C_ratio_state_DP": fraction_text(ratio_part),
                "B_plus_C": fraction_text(combined),
                "combined_error": fraction_text(combined - exact_existing),
                "float_combined_error": n3_official[record.record_id] + float(ratio_part) - float(exact_existing),
            }
        )
    oracle_seconds = time.perf_counter() - oracle_started

    # Write raw artifacts.
    for row in coordinate_rows:
        row["full_coordinate_value"] = fraction_text(
            suite.revenue * suite.coordinate_weights[(row["node"], row["metric"])]
        )
    write_csv(N3_OUT / "coordinate_weights_and_components.csv", coordinate_rows)
    write_csv(N3_OUT / "alliance_value_validation.csv", n3_alliance_rows)
    write_csv(N3_OUT / "shapley_comparison.csv", n3_shapley_rows)
    write_json(N3_OUT / "source_expressions.json", expression_json)
    write_csv(N4_OUT / "dp_state_summary.csv", dp_state_summary)
    write_csv(N4_OUT / "dp_terminal_states.csv", dp_terminal_rows)
    write_csv(N4_OUT / "ratio_coordinate_value_validation.csv", ratio_value_rows)
    write_csv(N4_OUT / "coordinate_shapley_comparison.csv", ratio_coordinate_shapley_rows)
    write_csv(OUT / "v1_alliance_value_validation.csv", whole_value_rows)
    write_csv(OUT / "v1_record_shapley_comparison.csv", v1_record_rows)

    current_memory, peak_memory = tracemalloc.get_traced_memory()
    costs = {
        "AB-N3-L": {
            "sql_grounding_seconds": grounding_seconds,
            "source_expression_assembly_seconds": source_assembly_seconds,
            "official_dtree_compile_seconds": official_timings["official_dtree_compile_seconds"],
            "official_backward_solve_seconds": official_timings["official_backward_solve_seconds"],
            "official_untouched_end_to_end_seconds": official_timings["official_untouched_end_to_end_seconds"],
            "algorithm_end_to_end_seconds": n3_algorithm_seconds,
            "components": component_count,
        },
        "AB-N4-DP": {
            "dp_algorithm_seconds": n4_dp_algorithm_seconds,
            "representative_dp_runs": sum(row["focal_type"] != "irrelevant" for row in dp_state_summary),
            "total_transition_updates": total_transition_updates,
            "terminal_state_rows": len(dp_terminal_rows),
            "maximum_terminal_states_one_run": max(row["terminal_state_count"] for row in dp_state_summary),
        },
        "posthoc_oracles": {
            "all_exact_validation_seconds": oracle_seconds,
            "truth_loaded_after_algorithm_construction": truth_loaded_timestamp >= construction_completed_timestamp,
        },
        "memory": {
            "python_tracemalloc_current_bytes": current_memory,
            "python_tracemalloc_peak_bytes": peak_memory,
            "scope": "Python allocations only; process RSS unavailable without psutil",
        },
    }
    write_json(OUT / "costs.json", costs)
    write_csv(
        OUT / "timing_memory.csv",
        [
            {
                "stage": "AB-N3-L",
                "algorithm_seconds": n3_algorithm_seconds,
                "source_or_transition_count": component_count,
                "python_tracemalloc_peak_bytes_shared_run": peak_memory,
            },
            {
                "stage": "AB-N4-DP",
                "algorithm_seconds": n4_dp_algorithm_seconds,
                "source_or_transition_count": total_transition_updates,
                "python_tracemalloc_peak_bytes_shared_run": peak_memory,
            },
            {
                "stage": "POSTHOC-ORACLES",
                "algorithm_seconds": oracle_seconds,
                "source_or_transition_count": (1 << spec.player_count),
                "python_tracemalloc_peak_bytes_shared_run": peak_memory,
            },
        ],
    )
    historical_after = {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL}
    if historical_before != historical_after:
        raise AssertionError("历史文件被修改")
    manifest = {
        "status": "COMPLETED_AB_N3_L_AND_AB_N4_DP_SMALL_SCALE_ONLY",
        "AB-N3-L": {
            "status": "FULL_SAME_GAME_LINEAR_21_COORDINATES",
            "coordinates": 21,
            "components": component_count,
            "full_coalition_value": fraction_text(linear_table[-1]),
            "maximum_exact_alliance_error": "0/1",
            "maximum_official_shapley_error_tolerance": "<=1e-10",
        },
        "AB-N4-DP": {
            "status": "EXACT_RATIO_COORDINATE_DP_VALIDATED",
            "coordinates": 14,
            "full_coalition_value": fraction_text(ratio_table_total[-1]),
            "maximum_exact_coordinate_error": "0/1",
            "maximum_exact_record_error": "0/1",
            "transition_updates": total_transition_updates,
        },
        "V1_combined": {
            "full_value": fraction_text(v1_table[-1]),
            "maximum_alliance_error": "0/1",
            "maximum_record_shapley_error": "0/1",
        },
        "construction_controls": {
            "algorithm_construction_completed_before_truth": algorithm_construction_completed_before_truth,
            "truth_loaded_after_algorithm_construction": truth_loaded_timestamp >= construction_completed_timestamp,
            "construction_used_4096_values": False,
            "construction_used_exact_payments": False,
        },
        "AB-J2_executed": False,
        "AB-N3_full_35_via_official_source_executed": False,
        "AB-N5_executed": False,
        "historical_hashes_before": historical_before,
        "historical_hashes_after": historical_after,
        "costs": costs,
        "environment": {
            "python": sys.version,
            "duckdb": duckdb.__version__,
            "official_shapley_source_sha256": sha256(
                ROOT
                / "external"
                / "abramovich"
                / "source"
                / "LExaBan-LExaShap-main"
                / "Algorithms"
                / "LExaShap"
                / "ShapleyCircuit.py"
            ),
            "d1p_design_sha256": sha256(ROOT / "config" / "d1p_design.yaml"),
            "value_spec_sha256": sha256(ROOT / "config" / "value_spec_v3_2.yaml"),
        },
        "total_wall_seconds": time.perf_counter() - run_started,
    }
    write_json(OUT / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
