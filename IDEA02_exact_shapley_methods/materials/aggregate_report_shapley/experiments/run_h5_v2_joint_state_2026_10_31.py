from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import platform
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from contextlib import contextmanager
from decimal import Decimal, getcontext, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import duckdb


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aggregate_report_shapley.d1p import (  # noqa: E402
    D1PState,
    all_incremental_states,
    load_d1p_spec,
    state_for_mask,
)
from aggregate_report_shapley.d1p_sql import (  # noqa: E402
    create_d1p_database,
    query_all_sql_p,
)
from aggregate_report_shapley.d1p_values import D1PValueSuite  # noqa: E402
from aggregate_report_shapley.exact_shapley import exact_shapley_decimal  # noqa: E402


OUT = ROOT / "outputs" / "v4_0" / "H5_V2_JOINT_STATE_2026_10_31"
CONFIG = ROOT / "config" / "d1p_design.yaml"
VALUE_CONFIG = ROOT / "config" / "value_spec_v3_2.yaml"
HISTORICAL_TRUTH = ROOT / "outputs" / "v4_0" / "R2_3" / "exact_targets.json"
LEAVES = ("A1", "A2", "B1", "B2")
FAMILY_ORDER = ("P", "E", "J", "M")
COUNTER_INDEX_BY_FAMILY = {
    "P": (0,),
    "E": (0, 1),
    "J": (2,),
    "M": (2, 3),
}
PRECISION = 110
TOLERANCE = Decimal("1e-75")

HISTORICAL = (
    CONFIG,
    VALUE_CONFIG,
    ROOT / "src" / "aggregate_report_shapley" / "d1p.py",
    ROOT / "src" / "aggregate_report_shapley" / "d1p_sql.py",
    ROOT / "src" / "aggregate_report_shapley" / "d1p_values.py",
    ROOT / "docs" / "H0_模型与实验设计审计.md",
    ROOT / "outputs" / "v4_0" / "H0" / "structural_gap_matrix.csv",
    ROOT / "reports" / "Abramovich_AB_N3_L_AB_N4_DP实验报告_2026-10-31.md",
    ROOT / "outputs" / "v4_0" / "AB_N3_L_N4_DP_2026_10_31" / "v1_record_shapley_comparison.csv",
    HISTORICAL_TRUTH,
)


LeafState = tuple[int, ...]
ValueFunction = Callable[[LeafState], Decimal]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_hashes() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): sha256(path) for path in HISTORICAL}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"拒绝写入空 CSV: {path}")
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


def dec(value: Fraction | Decimal | int) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Fraction):
        return Decimal(value.numerator) / Decimal(value.denominator)
    return Decimal(value)


def dtext(value: Decimal) -> str:
    return format(value, "f")


def add_state(left: LeafState, right: LeafState) -> LeafState:
    return tuple(a + b for a, b in zip(left, right, strict=True))


def zero_state() -> LeafState:
    return (0,) * 16


def record_delta(record, spec) -> LeafState:
    values = [0] * 16
    offset = LEAVES.index(record.leaf_node_id) * 4
    values[offset : offset + 4] = [
        1,
        int(record.category_a_id == spec.category_a_target),
        int(record.attribute_present),
        int(record.attribute_present and record.category_b_id == spec.category_b_target),
    ]
    return tuple(values)


def leaf_state_from_report(state: D1PState) -> LeafState:
    return tuple(value for leaf in LEAVES for value in state.counts[leaf])


def report_state_from_leaf(state: LeafState, spec) -> D1PState:
    result = D1PState.empty(spec.nodes)
    for leaf_index, leaf in enumerate(LEAVES):
        local = list(state[4 * leaf_index : 4 * leaf_index + 4])
        for node in spec.ancestors[leaf]:
            for counter, value in enumerate(local):
                result.counts[node][counter] += value
    return result


def selected_counter_indexes(families: Sequence[str]) -> tuple[int, ...]:
    local = sorted({index for family in families for index in COUNTER_INDEX_BY_FAMILY[family]})
    return tuple(4 * leaf + counter for leaf in range(4) for counter in local)


def project_state(state: LeafState, indexes: Sequence[int]) -> LeafState:
    selected = set(indexes)
    return tuple(value if index in selected else 0 for index, value in enumerate(state))


def family_game_evaluator(
    *, suite: D1PValueSuite, spec, families: Sequence[str], mode: str
) -> ValueFunction:
    indexes = selected_counter_indexes(families)
    cache: dict[LeafState, Decimal] = {}

    def evaluate(raw_state: LeafState) -> Decimal:
        state = project_state(raw_state, indexes)
        if state in cache:
            return cache[state]
        scores = suite.family_scores(report_state_from_leaf(state, spec))
        chosen = [scores[family] for family in families]
        with localcontext() as context:
            context.prec = PRECISION
            if mode == "additive":
                value = sum((dec(item) for item in chosen), Decimal(0)) / Decimal(len(chosen))
            elif mode == "geometric":
                if any(item == 0 for item in chosen):
                    value = Decimal(0)
                else:
                    product = math.prod((dec(item) for item in chosen), start=Decimal(1))
                    if len(chosen) == 1:
                        value = product
                    elif len(chosen) == 2:
                        value = product.sqrt()
                    elif len(chosen) == 4:
                        value = product.sqrt().sqrt()
                    else:
                        value = context.power(product, Decimal(1) / Decimal(len(chosen)))
            else:
                raise KeyError(mode)
            cache[state] = +value
            return cache[state]

    evaluate.cache = cache  # type: ignore[attr-defined]
    evaluate.indexes = indexes  # type: ignore[attr-defined]
    return evaluate


def frozen_v2_evaluator(*, fa: ValueFunction, fg: ValueFunction, revenue: Fraction, lam: Fraction) -> ValueFunction:
    revenue_d = dec(revenue)
    lam_d = dec(lam)

    def evaluate(state: LeafState) -> Decimal:
        with localcontext() as context:
            context.prec = PRECISION
            return +(revenue_d * ((Decimal(1) - lam_d) * fa(state) + lam_d * fg(state)))

    return evaluate


@contextmanager
def measured() -> Iterable[dict[str, Any]]:
    tracemalloc.start()
    started = time.perf_counter()
    payload: dict[str, Any] = {}
    try:
        yield payload
    finally:
        payload["wall_seconds"] = time.perf_counter() - started
        payload["peak_tracemalloc_bytes"] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()


def shapley_from_values(values: Sequence[Decimal], n: int) -> list[Decimal]:
    return exact_shapley_decimal(values, n, precision=PRECISION)


def method_b0(
    states: Sequence[LeafState], evaluator: ValueFunction, n: int
) -> tuple[list[Decimal], list[Decimal], dict[str, Any]]:
    with measured() as cost:
        tick = time.perf_counter()
        values = [evaluator(state) for state in states]
        cost["state_build_seconds"] = 0.0
        cost["value_evaluation_seconds"] = time.perf_counter() - tick
        tick = time.perf_counter()
        allocation = shapley_from_values(values, n)
        cost["exact_solve_seconds"] = time.perf_counter() - tick
        cost.update(
            theoretical_state_upper=1 << n,
            actual_visited_states=len(states),
            state_transitions=n * (1 << (n - 1)),
            cache_entries=len(states),
        )
    return values, allocation, cost


def raw_types(deltas: Sequence[LeafState]) -> list[tuple[LeafState, list[int]]]:
    groups: dict[LeafState, list[int]] = defaultdict(list)
    for player, delta in enumerate(deltas):
        groups[delta].append(player)
    return sorted(groups.items(), key=lambda item: min(item[1]))


def state_from_type_counts(types, counts: Sequence[int]) -> LeafState:
    result = [0] * 16
    for (delta, _players), count in zip(types, counts, strict=True):
        for index, value in enumerate(delta):
            result[index] += count * value
    return tuple(result)


def method_b1(
    *, deltas: Sequence[LeafState], evaluator: ValueFunction, n: int
) -> tuple[list[Decimal], dict[str, Any], list[dict[str, Any]]]:
    types = raw_types(deltas)
    cache: dict[tuple[int, ...], Decimal] = {}
    with measured() as cost:
        tick = time.perf_counter()
        ranges = [range(len(players) + 1) for _delta, players in types]
        for counts in itertools.product(*ranges):
            cache[counts] = evaluator(state_from_type_counts(types, counts))
        cost["state_build_seconds"] = time.perf_counter() - tick
        allocations = [Decimal(0)] * n
        transition_count = 0
        tick = time.perf_counter()
        for type_index, (_delta, players) in enumerate(types):
            capacities = [len(group) for _other_delta, group in types]
            capacities[type_index] -= 1
            for counts in itertools.product(*(range(size + 1) for size in capacities)):
                k = sum(counts)
                multiplicity = math.prod(
                    math.comb(capacity, count)
                    for capacity, count in zip(capacities, counts, strict=True)
                )
                after = list(counts)
                after[type_index] += 1
                marginal = cache[tuple(after)] - cache[counts]
                weight = Decimal(1) / Decimal(n * math.comb(n - 1, k))
                contribution = Decimal(multiplicity) * weight * marginal
                for player in players:
                    allocations[player] += contribution
                transition_count += 1
        cost["exact_solve_seconds"] = time.perf_counter() - tick
        cost["value_evaluation_seconds"] = cost["state_build_seconds"]
        cost.update(
            raw_type_count=len(types),
            type_sizes="|".join(str(len(players)) for _delta, players in types),
            theoretical_state_upper=math.prod(len(players) + 1 for _delta, players in types),
            actual_visited_states=len(cache),
            state_transitions=transition_count,
            cache_entries=len(cache),
        )
    type_rows = [
        {
            "type_id": f"T{index + 1}",
            "players": "|".join(f"p{player + 1}" for player in players),
            "type_size": len(players),
            "leaf_increment": json.dumps(delta, ensure_ascii=False),
        }
        for index, (delta, players) in enumerate(types)
    ]
    return allocations, cost, type_rows


def method_b2(
    *, deltas: Sequence[LeafState], evaluator: ValueFunction, n: int, indexes: Sequence[int]
) -> tuple[list[Decimal], dict[str, Any]]:
    projected_deltas = [project_state(delta, indexes) for delta in deltas]
    allocations: list[Decimal] = []
    transitions = 0
    intermediate_states = 0
    terminal_states = 0
    maximum_frontier = 0
    value_cache: dict[LeafState, Decimal] = {}

    def value(state: LeafState) -> Decimal:
        if state not in value_cache:
            value_cache[state] = evaluator(state)
        return value_cache[state]

    with measured() as cost:
        build_seconds = 0.0
        solve_seconds = 0.0
        for focal in range(n):
            tick = time.perf_counter()
            dp: Counter[LeafState] = Counter({zero_state(): 1})
            for player, delta in enumerate(projected_deltas):
                if player == focal:
                    continue
                new: Counter[LeafState] = Counter()
                for state, multiplicity in dp.items():
                    new[state] += multiplicity
                    new[add_state(state, delta)] += multiplicity
                    transitions += 2
                dp = new
                intermediate_states += len(dp)
                maximum_frontier = max(maximum_frontier, len(dp))
            build_seconds += time.perf_counter() - tick
            terminal_states += len(dp)
            tick = time.perf_counter()
            phi = Decimal(0)
            focal_delta = projected_deltas[focal]
            for state, multiplicity in dp.items():
                k = sum(state[4 * leaf] for leaf in range(4))
                marginal = value(add_state(state, focal_delta)) - value(state)
                phi += Decimal(multiplicity) * marginal / Decimal(n * math.comb(n - 1, k))
            allocations.append(+phi)
            solve_seconds += time.perf_counter() - tick
        cost.update(
            state_build_seconds=build_seconds,
            value_evaluation_seconds=solve_seconds,
            exact_solve_seconds=solve_seconds,
            theoretical_state_upper=1 << n,
            actual_visited_states=terminal_states,
            unique_value_states=len(value_cache),
            intermediate_state_visits=intermediate_states,
            maximum_frontier_states=maximum_frontier,
            state_transitions=transitions,
            cache_entries=len(value_cache),
        )
    return allocations, cost


def local_factor(records: Sequence[LeafState], leaf: int, indexes: Sequence[int]) -> tuple[Counter[tuple[int, int, int, int]], int]:
    active_local = {index % 4 for index in indexes if index // 4 == leaf}
    factor: Counter[tuple[int, int, int, int]] = Counter({(0, 0, 0, 0): 1})
    transitions = 0
    for delta in records:
        local_delta = tuple(delta[4 * leaf + counter] if counter in active_local else 0 for counter in range(4))
        if not any(local_delta):
            continue
        new: Counter[tuple[int, int, int, int]] = Counter()
        for state, multiplicity in factor.items():
            new[state] += multiplicity
            new[tuple(a + b for a, b in zip(state, local_delta, strict=True))] += multiplicity
            transitions += 2
        factor = new
    return factor, transitions


def method_b3(
    *, deltas: Sequence[LeafState], evaluator: ValueFunction, n: int, indexes: Sequence[int]
) -> tuple[list[Decimal], dict[str, Any], list[dict[str, Any]]]:
    projected_deltas = [project_state(delta, indexes) for delta in deltas]
    allocations: list[Decimal] = []
    transitions = 0
    intermediate_states = 0
    maximum_frontier = 0
    terminal_states = 0
    local_factor_rows: list[dict[str, Any]] = []
    value_cache: dict[LeafState, Decimal] = {}

    def value(state: LeafState) -> Decimal:
        if state not in value_cache:
            value_cache[state] = evaluator(state)
        return value_cache[state]

    with measured() as cost:
        build_seconds = 0.0
        solve_seconds = 0.0
        for focal in range(n):
            others = [delta for player, delta in enumerate(projected_deltas) if player != focal]
            tick = time.perf_counter()
            factors: list[tuple[int, Counter[tuple[int, int, int, int]]]] = []
            for leaf in range(4):
                leaf_records = [delta for delta in others if any(delta[4 * leaf : 4 * leaf + 4])]
                factor, local_transitions = local_factor(leaf_records, leaf, indexes)
                factors.append((leaf, factor))
                transitions += local_transitions
                local_factor_rows.append(
                    {
                        "focal_player": f"p{focal + 1}",
                        "leaf": LEAVES[leaf],
                        "record_factors": len(leaf_records),
                        "local_terminal_states": len(factor),
                        "local_combination_total": sum(factor.values()),
                        "local_transition_writes": local_transitions,
                    }
                )
            factors.sort(key=lambda item: len(item[1]))
            frontier: Counter[LeafState] = Counter({zero_state(): 1})
            for leaf, factor in factors:
                new: Counter[LeafState] = Counter()
                for global_state, global_count in frontier.items():
                    for local_state, local_count in factor.items():
                        combined = list(global_state)
                        combined[4 * leaf : 4 * leaf + 4] = local_state
                        new[tuple(combined)] += global_count * local_count
                        transitions += 1
                frontier = new
                intermediate_states += len(frontier)
                maximum_frontier = max(maximum_frontier, len(frontier))
            build_seconds += time.perf_counter() - tick
            terminal_states += len(frontier)
            if sum(frontier.values()) != 1 << (n - 1):
                raise AssertionError("B3 因子乘积的联盟组合数错误")
            tick = time.perf_counter()
            focal_delta = projected_deltas[focal]
            phi = Decimal(0)
            for state, multiplicity in frontier.items():
                k = sum(state[4 * leaf] for leaf in range(4))
                marginal = value(add_state(state, focal_delta)) - value(state)
                phi += Decimal(multiplicity) * marginal / Decimal(n * math.comb(n - 1, k))
            allocations.append(+phi)
            solve_seconds += time.perf_counter() - tick
        cost.update(
            state_build_seconds=build_seconds,
            value_evaluation_seconds=solve_seconds,
            exact_solve_seconds=solve_seconds,
            theoretical_state_upper=1 << n,
            actual_visited_states=terminal_states,
            unique_value_states=len(value_cache),
            intermediate_state_visits=intermediate_states,
            maximum_frontier_states=maximum_frontier,
            state_transitions=transitions,
            cache_entries=len(value_cache),
        )
    return allocations, cost, local_factor_rows


def max_abs_error(left: Sequence[Decimal], right: Sequence[Decimal]) -> Decimal:
    return max((abs(a - b) for a, b in zip(left, right, strict=True)), default=Decimal(0))


def efficiency_error(allocation: Sequence[Decimal], full_value: Decimal, empty_value: Decimal = Decimal(0)) -> Decimal:
    return abs(sum(allocation, Decimal(0)) - (full_value - empty_value))


def state_box_bound(full_leaf_state: LeafState, indexes: Sequence[int]) -> int:
    return math.prod(full_leaf_state[index] + 1 for index in indexes)


def factorized_attainable_count(deltas: Sequence[LeafState], indexes: Sequence[int]) -> int:
    total = 1
    for leaf in range(4):
        states = {zero_state()}
        for delta in deltas:
            if not any(delta[4 * leaf : 4 * leaf + 4]):
                continue
            projected = project_state(delta, indexes)
            states |= {add_state(state, projected) for state in list(states)}
        local = {tuple(state[4 * leaf : 4 * leaf + 4]) for state in states}
        total *= len(local)
    return total


def main() -> None:
    getcontext().prec = PRECISION
    OUT.mkdir(parents=True, exist_ok=True)
    before_hashes = historical_hashes()
    total_started = time.perf_counter()

    spec = load_d1p_spec(CONFIG)
    n = spec.player_count
    full_report_state = state_for_mask(spec.full_mask, spec)
    suite = D1PValueSuite(spec, full_report_state, VALUE_CONFIG)
    report_states = all_incremental_states(spec)
    leaf_states = [leaf_state_from_report(state) for state in report_states]
    deltas = [record_delta(record, spec) for record in spec.records]
    full_leaf_state = leaf_states[-1]

    # SQL is an independent source-statistics check, not an input to B1-B3.
    sql_connection = duckdb.connect(":memory:")
    tick = time.perf_counter()
    create_d1p_database(sql_connection, spec)
    sql_setup_seconds = time.perf_counter() - tick
    tick = time.perf_counter()
    sql_states = query_all_sql_p(sql_connection, spec)
    sql_query_seconds = time.perf_counter() - tick
    sql_connection.close()
    sql_mismatches = sum(
        sql_state.canonical(spec.nodes) != report_state.canonical(spec.nodes)
        for sql_state, report_state in zip(sql_states, report_states, strict=True)
    )
    if sql_mismatches:
        raise AssertionError(f"SQL 与增量统计状态不一致: {sql_mismatches}")

    fa = family_game_evaluator(suite=suite, spec=spec, families=FAMILY_ORDER, mode="additive")
    fg = family_game_evaluator(suite=suite, spec=spec, families=FAMILY_ORDER, mode="geometric")
    v2 = frozen_v2_evaluator(fa=fa, fg=fg, revenue=suite.revenue, lam=Fraction(1, 2))

    identity_rows: list[dict[str, Any]] = []
    maximum_v1_fa_error = Decimal(0)
    maximum_v1_fa_fraction_error = Fraction(0)
    maximum_v2_formula_error = Decimal(0)
    for mask, (leaf_state, report_state) in enumerate(zip(leaf_states, report_states, strict=True)):
        v1 = dec(suite.v1(report_state))
        family_fractions = suite.family_scores(report_state)
        fa_fraction = sum(
            (suite.family_weights[family] * family_fractions[family] for family in FAMILY_ORDER),
            Fraction(0),
        )
        v1_fraction_error = abs(suite.v1(report_state) - suite.revenue * fa_fraction)
        maximum_v1_fa_fraction_error = max(maximum_v1_fa_fraction_error, v1_fraction_error)
        reconstructed_v1 = dec(suite.revenue * fa_fraction)
        suite_v2 = suite.v2_decimal(report_state, Fraction(1, 2), precision=PRECISION)
        reconstructed_v2 = v2(leaf_state)
        v1_error = abs(v1 - reconstructed_v1)
        v2_error = abs(suite_v2 - reconstructed_v2)
        maximum_v1_fa_error = max(maximum_v1_fa_error, v1_error)
        maximum_v2_formula_error = max(maximum_v2_formula_error, v2_error)
        identity_rows.append(
            {
                "mask": mask,
                "coalition_size": mask.bit_count(),
                "V1_frozen": dtext(v1),
                "R_times_FA": dtext(reconstructed_v1),
                "V1_identity_abs_error": dtext(v1_error),
                "V2_frozen": dtext(suite_v2),
                "V2_reconstructed": dtext(reconstructed_v2),
                "V2_formula_abs_error": dtext(v2_error),
            }
        )
    if maximum_v1_fa_fraction_error != 0 or maximum_v2_formula_error > TOLERANCE:
        raise AssertionError(
            f"V1/V2 冻结公式恒等式核验失败: "
            f"V1_fraction={maximum_v1_fa_fraction_error}, V2={maximum_v2_formula_error}"
        )

    method_cost_rows: list[dict[str, Any]] = []
    method_allocations: dict[str, list[Decimal]] = {}

    b0_values, b0_allocation, b0_cost = method_b0(leaf_states, v2, n)
    method_allocations["B0_FULL_COALITION_ENUMERATION"] = b0_allocation
    method_cost_rows.append({"method": "B0_FULL_COALITION_ENUMERATION", "target": "frozen_V2", **b0_cost})

    b1_allocation, b1_cost, type_rows = method_b1(deltas=deltas, evaluator=v2, n=n)
    method_allocations["B1_JOINT_RAW_TYPE_COUNTS"] = b1_allocation
    method_cost_rows.append({"method": "B1_JOINT_RAW_TYPE_COUNTS", "target": "frozen_V2", **b1_cost})

    fg_indexes = selected_counter_indexes(FAMILY_ORDER)
    b2_fg, b2_cost = method_b2(deltas=deltas, evaluator=fg, n=n, indexes=fg_indexes)
    v1_truth = exact_shapley_decimal([dec(suite.v1(state)) for state in report_states], n, precision=PRECISION)
    b2_allocation = [
        Decimal("0.5") * v1_part + dec(suite.revenue) * Decimal("0.5") * fg_part
        for v1_part, fg_part in zip(v1_truth, b2_fg, strict=True)
    ]
    method_allocations["B2_SUFFICIENT_STATE_DP"] = b2_allocation
    method_cost_rows.append({"method": "B2_SUFFICIENT_STATE_DP", "target": "FG_then_linear_V1_reuse", **b2_cost})

    b3_fg, b3_cost, local_factor_rows = method_b3(
        deltas=deltas, evaluator=fg, n=n, indexes=fg_indexes
    )
    b3_allocation = [
        Decimal("0.5") * v1_part + dec(suite.revenue) * Decimal("0.5") * fg_part
        for v1_part, fg_part in zip(v1_truth, b3_fg, strict=True)
    ]
    method_allocations["B3_LEAF_FACTOR_GENERATING_FUNCTION"] = b3_allocation
    method_cost_rows.append(
        {"method": "B3_LEAF_FACTOR_GENERATING_FUNCTION", "target": "FG_then_linear_V1_reuse", **b3_cost}
    )

    historical = json.loads(HISTORICAL_TRUTH.read_text(encoding="utf-8"))
    historical_v2 = [Decimal(value) for value in historical["record_shapley"]["V2_lambda_0_5"]]
    truth_error = max_abs_error(b0_allocation, historical_v2)
    if truth_error > Decimal("1e-70"):
        raise AssertionError(f"本轮 B0 与历史 V2 真值不一致: {truth_error}")

    shapley_rows: list[dict[str, Any]] = []
    for method, allocation in method_allocations.items():
        for player, value in enumerate(allocation):
            shapley_rows.append(
                {
                    "method": method,
                    "player": f"p{player + 1}",
                    "shapley": dtext(value),
                    "B0_truth": dtext(b0_allocation[player]),
                    "absolute_error": dtext(abs(value - b0_allocation[player])),
                }
            )
    validation_rows: list[dict[str, Any]] = []
    for method, allocation in method_allocations.items():
        validation_rows.append(
            {
                "method": method,
                "max_player_abs_error_vs_B0": dtext(max_abs_error(allocation, b0_allocation)),
                "efficiency_abs_error": dtext(efficiency_error(allocation, b0_values[-1], b0_values[0])),
                "sum_shapley": dtext(sum(allocation, Decimal(0))),
                "grand_coalition_minus_empty": dtext(b0_values[-1] - b0_values[0]),
                "passes_tolerance_1e-70": max_abs_error(allocation, b0_allocation) <= Decimal("1e-70"),
            }
        )

    # Controlled games: same records, references and family definitions; only the named score is derived.
    family_growth_rows: list[dict[str, Any]] = []
    family_shapley_rows: list[dict[str, Any]] = []
    for family_count in range(1, 5):
        families = FAMILY_ORDER[:family_count]
        indexes = selected_counter_indexes(families)
        projected_states = [project_state(state, indexes) for state in leaf_states]
        for mode in ("additive", "geometric"):
            game_id = f"H5_{'FA' if mode == 'additive' else 'FG'}_{family_count}_{''.join(families)}"
            evaluator = family_game_evaluator(suite=suite, spec=spec, families=families, mode=mode)
            direct_values, direct_phi, direct_cost = method_b0(projected_states, evaluator, n)
            dp_phi, dp_cost = method_b2(deltas=deltas, evaluator=evaluator, n=n, indexes=indexes)
            error = max_abs_error(dp_phi, direct_phi)
            if error > Decimal("1e-70"):
                raise AssertionError(f"派生游戏 {game_id} 的 DP 不精确: {error}")
            distinct_values = len(set(direct_values))
            family_growth_rows.append(
                {
                    "game_id": game_id,
                    "family_count": family_count,
                    "families": "|".join(families),
                    "score_mode": mode,
                    "selected_leaf_counter_dimensions": len(indexes),
                    "binary_subset_upper_bound": 1 << n,
                    "coordinate_box_upper_bound": state_box_bound(full_leaf_state, indexes),
                    "factorized_attainable_state_count": factorized_attainable_count(deltas, indexes),
                    "observed_distinct_projected_states": len(set(projected_states)),
                    "observed_distinct_game_values": distinct_values,
                    "B0_wall_seconds": direct_cost["wall_seconds"],
                    "B2_wall_seconds": dp_cost["wall_seconds"],
                    "B2_terminal_state_visits_all_focals": dp_cost["actual_visited_states"],
                    "B2_intermediate_state_visits": dp_cost["intermediate_state_visits"],
                    "B2_transition_writes": dp_cost["state_transitions"],
                    "B2_maximum_frontier_states": dp_cost["maximum_frontier_states"],
                    "B2_unique_value_states": dp_cost["unique_value_states"],
                    "max_player_abs_error_B2_vs_B0": dtext(error),
                    "efficiency_abs_error_B2": dtext(efficiency_error(dp_phi, direct_values[-1], direct_values[0])),
                    "timing_interpretation": "single_run_descriptive_only",
                }
            )
            for player, (truth, estimate) in enumerate(zip(direct_phi, dp_phi, strict=True)):
                family_shapley_rows.append(
                    {
                        "game_id": game_id,
                        "player": f"p{player + 1}",
                        "B0_shapley": dtext(truth),
                        "B2_shapley": dtext(estimate),
                        "absolute_error": dtext(abs(truth - estimate)),
                    }
                )

    # Concrete minimal counterexamples for state designs that are not transition-sufficient.
    counterexample_rows: list[dict[str, Any]] = []
    pe_fg = family_game_evaluator(suite=suite, spec=spec, families=("P", "E"), mode="geometric")
    p_indexes = selected_counter_indexes(("P",))
    p_groups: dict[LeafState, list[int]] = defaultdict(list)
    for mask, state in enumerate(leaf_states):
        p_groups[project_state(state, p_indexes)].append(mask)
    found = False
    for masks in p_groups.values():
        for left, right in itertools.combinations(masks, 2):
            if pe_fg(leaf_states[left]) != pe_fg(leaf_states[right]):
                counterexample_rows.append(
                    {
                        "counterexample_id": "CE1_P_STATE_NOT_SUFFICIENT_FOR_PE_GEOMETRIC",
                        "left_mask": left,
                        "right_mask": right,
                        "left_players": "|".join(spec.records[i].record_id for i in range(n) if left & (1 << i)) or "EMPTY",
                        "right_players": "|".join(spec.records[i].record_id for i in range(n) if right & (1 << i)) or "EMPTY",
                        "shared_reduced_state": json.dumps(project_state(leaf_states[left], p_indexes)),
                        "left_value": dtext(pe_fg(leaf_states[left])),
                        "right_value": dtext(pe_fg(leaf_states[right])),
                        "failure_meaning": "P-only counts cannot determine the P/E geometric game",
                    }
                )
                found = True
                break
        if found:
            break

    family_vectors = [
        tuple(suite.family_scores(state)[family] for family in FAMILY_ORDER)
        for state in report_states
    ]
    vector_groups: dict[tuple[Fraction, ...], list[int]] = defaultdict(list)
    for mask, vector in enumerate(family_vectors):
        vector_groups[vector].append(mask)
    found = False
    for masks in vector_groups.values():
        if len(masks) < 2:
            continue
        for left, right in itertools.combinations(masks, 2):
            for player in range(n):
                bit = 1 << player
                if (left | right) & bit:
                    continue
                left_after = family_vectors[left | bit]
                right_after = family_vectors[right | bit]
                if left_after != right_after:
                    counterexample_rows.append(
                        {
                            "counterexample_id": "CE2_FAMILY_SCORE_VECTOR_NOT_TRANSITION_SUFFICIENT",
                            "left_mask": left,
                            "right_mask": right,
                            "left_players": "|".join(spec.records[i].record_id for i in range(n) if left & (1 << i)) or "EMPTY",
                            "right_players": "|".join(spec.records[i].record_id for i in range(n) if right & (1 << i)) or "EMPTY",
                            "shared_reduced_state": "|".join(str(item) for item in family_vectors[left]),
                            "added_player": f"p{player + 1}",
                            "left_value": "|".join(str(item) for item in left_after),
                            "right_value": "|".join(str(item) for item in right_after),
                            "failure_meaning": "current family-score vector determines current FG but is not closed under record addition",
                        }
                    )
                    found = True
                    break
            if found:
                break
        if found:
            break
    if len(counterexample_rows) != 2:
        raise AssertionError("未能构造预定的两个状态不充分最小反例")

    method_cost_rows.insert(
        0,
        {
            "method": "SQL_P_ORACLE",
            "target": "all_4096_base_statistics",
            "state_build_seconds": sql_setup_seconds,
            "value_evaluation_seconds": sql_query_seconds,
            "exact_solve_seconds": 0.0,
            "wall_seconds": sql_setup_seconds + sql_query_seconds,
            "peak_tracemalloc_bytes": "NOT_MEASURED_DUCKDB_NATIVE_MEMORY",
            "theoretical_state_upper": 1 << n,
            "actual_visited_states": len(sql_states),
            "state_transitions": "NOT_APPLICABLE",
            "cache_entries": len(sql_states),
        },
    )

    failure_rows = [
        {
            "candidate": "A_raw_record_type_counts",
            "status": "EXACT_BUT_NO_COMPRESSION_ON_D1P",
            "reason_class": "data_instance_has_12_unique_raw_types",
            "observed_evidence": f"raw_type_count={b1_cost['raw_type_count']}; state_grid={b1_cost['actual_visited_states']}",
            "minimal_counterexample_or_boundary": "12 singleton types make the type-count grid exactly 2^12",
        },
        {
            "candidate": "B_shared_leaf_base_statistics",
            "status": "SUFFICIENT_AND_EXECUTABLE",
            "reason_class": "verified_sufficient_state",
            "observed_evidence": f"all-coalition report states reconstructed; B2 error={max_abs_error(b2_allocation, b0_allocation)}",
            "minimal_counterexample_or_boundary": "would fail if score depends on record identity beyond the four leaf counters",
        },
        {
            "candidate": "C_family_local_states",
            "status": "SUFFICIENT_PER_DERIVED_GAME_NOT_SEPARABLE_FOR_FG",
            "reason_class": "nonadditive_global_score_requires_joint_family_state",
            "observed_evidence": "individual family values are insufficient to add Shapley results for the geometric product",
            "minimal_counterexample_or_boundary": "two coalitions with same P score but different E score have different sqrt(P*E)",
        },
        {
            "candidate": "D_leaf_factor_variable_elimination",
            "status": "EXACT_EXECUTABLE_CLASSIC_REDUCTION",
            "reason_class": "disjoint_leaf_factors_then_global_score",
            "observed_evidence": f"B3 error={max_abs_error(b3_allocation, b0_allocation)}",
            "minimal_counterexample_or_boundary": "cross-leaf record/JOIN factors would destroy the current disjoint-leaf product",
        },
        {
            "candidate": "E_generic_polynomial_time_claim",
            "status": "NOT_ESTABLISHED",
            "reason_class": "state_space_may_grow_with_joint_counter_ranges_and_factor_width",
            "observed_evidence": "fixed n=12 single-instance run only",
            "minimal_counterexample_or_boundary": "add independent counters or cross-leaf factors and measure reachable joint states",
        },
    ]

    literature_rows = [
        {
            "source": "Livshits et al. (ICDT 2020 / TODS 2021)",
            "result": "Theorem 11; Corollary 15",
            "assumptions": "self-join-free hierarchical Boolean CQ; additive SUM reduction",
            "mapping_to_H5": "coalition-size counting and recursive combination motivate the DP, but frozen V2 is a global nonlinear score over four report families",
            "classification": "CLASSIC_COUNTING_IDEA_AFTER_REDUCTION; theorem_not_directly_same_target",
        },
        {
            "source": "Standke & Kimelfeld (2025 preprint)",
            "result": "generic hierarchical AggCQ DP; Theorem 4.1 for selected aggregates",
            "assumptions": "self-join-free/all-hierarchical query and locally representable aggregate/value conditions",
            "mapping_to_H5": "B2 tracks sufficient aggregate statistics, but the whole-report geometric score is not one of the directly certified standard local aggregate cases",
            "classification": "CLASSIC_SUFFICIENT_STATISTIC_DP_SPECIALIZATION; no direct theorem guarantee claimed",
        },
        {
            "source": "Abramovich et al. (PVLDB 2025)",
            "result": "Theorem 3.6 d-tree all-variable Shapley computation",
            "assumptions": "compiled Boolean provenance/d-tree value circuit",
            "mapping_to_H5": "single-variable/count provenance is reusable for linear components; a global geometric product over family scores is outside the tested official interface",
            "classification": "LINEAR_COMPONENT_DIRECT; global_V2_requires_external_state_reduction",
        },
        {
            "source": "classical generating-function / variable-elimination viewpoint",
            "result": "coefficient convolution of independent factors",
            "assumptions": "finite sufficient state and factorizable player increments",
            "mapping_to_H5": "B3 multiplies four leaf factors and then evaluates exact Shapley marginals",
            "classification": "CLASSIC_METHOD_APPLIED; not_new_algorithm",
        },
    ]

    write_csv(OUT / "v2_formula_identity_4096.csv", identity_rows)
    write_csv(OUT / "record_shapley_comparison.csv", shapley_rows)
    write_csv(OUT / "correctness_validation.csv", validation_rows)
    write_csv(OUT / "algorithm_costs.csv", method_cost_rows)
    write_csv(OUT / "raw_record_types.csv", type_rows)
    write_csv(OUT / "b3_leaf_factor_states.csv", local_factor_rows)
    write_csv(OUT / "family_state_growth.csv", family_growth_rows)
    write_csv(OUT / "family_game_record_shapley.csv", family_shapley_rows)
    write_csv(OUT / "failure_reasons_and_boundaries.csv", failure_rows)
    write_csv(OUT / "minimal_counterexamples.csv", counterexample_rows)
    write_csv(OUT / "literature_method_mapping.csv", literature_rows)

    after_hashes = historical_hashes()
    if before_hashes != after_hashes:
        raise AssertionError("历史文件哈希发生变化")
    write_json(
        OUT / "historical_hashes.json",
        {"before": before_hashes, "after": after_hashes, "unchanged": before_hashes == after_hashes},
    )
    summary = {
        "status": "H5_V2_JOINT_STATE_COMPLETED_AND_PAUSED",
        "players": n,
        "nodes": len(spec.nodes),
        "report_coordinates": len(spec.nodes) * 5,
        "families": list(FAMILY_ORDER),
        "coalitions": 1 << n,
        "revenue": str(suite.revenue),
        "lambda": "1/2",
        "sql_state_mismatches": sql_mismatches,
        "max_V1_equals_R_FA_error": dtext(maximum_v1_fa_error),
        "max_V1_equals_R_FA_exact_fraction_error": str(maximum_v1_fa_fraction_error),
        "max_V2_formula_reconstruction_error": dtext(maximum_v2_formula_error),
        "B0_vs_historical_truth_max_abs_error": dtext(truth_error),
        "method_max_errors_vs_B0": {
            method: dtext(max_abs_error(allocation, b0_allocation))
            for method, allocation in method_allocations.items()
        },
        "B1_raw_type_count": b1_cost["raw_type_count"],
        "full_leaf_state_dimensions": 16,
        "observed_full_sufficient_states": len(set(leaf_states)),
        "full_state_coordinate_box_upper_bound": state_box_bound(full_leaf_state, fg_indexes),
        "factorized_attainable_full_state_count": factorized_attainable_count(deltas, fg_indexes),
        "historical_files_unchanged": True,
        "total_wall_seconds": time.perf_counter() - total_started,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "duckdb": duckdb.__version__,
        },
        "statistical_note": "deterministic exhaustive computation; single-run timings are descriptive and no confidence intervals are applicable",
    }
    write_json(OUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
