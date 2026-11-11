from __future__ import annotations

import csv
import ctypes
import json
import math
import statistics
import sys
import time
import tracemalloc
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Callable

import numpy as np
import yaml
from scipy.stats import hypergeom, spearmanr


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aggregate_report_shapley.d1p import (  # noqa: E402
    all_incremental_states,
    load_d1p_spec,
    state_for_mask,
)
from aggregate_report_shapley.d1p_values import D1PValueSuite  # noqa: E402
from aggregate_report_shapley.exact_shapley import (  # noqa: E402
    exact_shapley_decimal,
    exact_shapley_subset,
)


OUT = ROOT / "outputs" / "v4_0" / "R2" / "d1p"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "run_fgsv_r2_d1p.log"

VALUE_NAMES = ("V_count", "V1", "V2_lambda_0_5")
NOMINAL_BUDGETS = (500, 1000, 2000, 5000)
SEEDS = tuple(range(30))
THRESHOLD = 10


def log(message: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def text_number(value: Fraction | Decimal) -> str:
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    return format(value, "f")


def mask_from_selection(selection: np.ndarray | list[int], n: int) -> tuple[int, int]:
    array = np.asarray(selection)
    indices = np.flatnonzero(array) if array.dtype == bool else array.astype(int, copy=False)
    mask = 0
    for index in indices:
        mask |= 1 << int(index)
    return mask, len(indices)


def process_peak_rss_bytes() -> int | None:
    if sys.platform != "win32":
        return None

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    process = ctypes.windll.kernel32.GetCurrentProcess()
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        process, ctypes.byref(counters), counters.cb
    )
    return int(counters.PeakWorkingSetSize) if ok else None


def evaluate_state_float(suite: D1PValueSuite, state, value_name: str) -> float:
    if value_name == "V_count":
        return float(suite.v_count(state))
    if value_name == "V1":
        return float(suite.v1(state))
    if value_name == "V2_lambda_0_5":
        families = suite.family_scores(state)
        arithmetic = sum(float(suite.family_weights[key] * families[key]) for key in families)
        if any(value == 0 for value in families.values()):
            geometric = 0.0
        else:
            geometric = math.prod(
                float(families[key]) ** float(suite.family_weights[key]) for key in families
            )
        return float(suite.revenue) * 0.5 * (arithmetic + geometric)
    raise KeyError(value_name)


@dataclass
class CountingUtility:
    n: int
    evaluator: Callable[[int], float]
    calls: int = 0
    compute_seconds: float = 0.0

    def __post_init__(self) -> None:
        self.size_histogram: Counter[int] = Counter()

    def __call__(self, selection, *_ignored) -> float:
        mask, size = mask_from_selection(selection, self.n)
        started = time.perf_counter()
        value = self.evaluator(mask)
        self.compute_seconds += time.perf_counter() - started
        self.calls += 1
        self.size_histogram[size] += 1
        return value


def merge_histograms(items: list[Counter[int]]) -> dict[str, int]:
    total: Counter[int] = Counter()
    for item in items:
        total.update(item)
    return {str(key): total[key] for key in sorted(total)}


def even_group_budgets(total: int, groups: int) -> list[int]:
    if total % 2:
        raise ValueError("FGSV common budget must be even")
    base = 2 * (total // (2 * groups))
    result = [base] * groups
    for index in range((total - base * groups) // 2):
        result[index] += 2
    if sum(result) != total:
        raise AssertionError("group budget allocation failed")
    return result


def common_effective_budget(nominal: int, n: int) -> int:
    permutations = nominal // (n + 1)
    if permutations % 2:
        permutations -= 1
    return permutations * (n + 1)


def fgsv_budget_capped(
    utility: CountingUtility,
    n: int,
    group: list[int],
    budget: int,
    rng: np.random.RandomState,
    threshold: int = THRESHOLD,
) -> dict[str, object]:
    if budget < 2:
        raise ValueError("FGSV needs at least two utility calls")
    group_array = np.asarray(group, dtype=int)
    complement = np.setdiff1d(np.arange(n), group_array)
    s0 = len(group_array)
    linear = s0 / n * (
        utility(np.arange(n, dtype=int)) - utility(np.array([], dtype=int))
    )
    ts = np.zeros(n - 1, dtype=float)
    counts = np.zeros(n - 1, dtype=int)
    sampled_s: Counter[int] = Counter()

    while utility.calls < budget:
        remaining = budget - utility.calls
        candidates = rng.permutation(np.arange(1, n))
        selected_s = None
        selected_cost = None
        for raw_s in candidates:
            s = int(raw_s)
            s1_min = max(0, s0 + s - n)
            s1_max = min(s0, s)
            cost = s1_max - s1_min + 1 if s < threshold else 2
            if cost <= remaining:
                selected_s, selected_cost = s, cost
                break
        if selected_s is None:
            break

        s = selected_s
        s1_min = max(0, s0 + s - n)
        s1_max = min(s0, s)
        expected_s1 = round(s0 * s / n)
        sampled_s[s] += 1

        if s < threshold:
            temp = 0.0
            for s1 in range(s1_min, s1_max + 1):
                inside = rng.choice(group_array, s1, replace=False)
                outside = rng.choice(complement, s - s1, replace=False)
                coalition = np.concatenate((inside, outside))
                temp += (
                    hypergeom.pmf(s1, n, s0, s)
                    * (s1 - s * s0 / n)
                    * utility(coalition)
                )
            ts[s - 1] = counts[s - 1] / (counts[s - 1] + 1) * ts[s - 1] + temp / (
                counts[s - 1] + 1
            )
            counts[s - 1] += 1
        else:
            if expected_s1 + 1 <= s1_max and expected_s1 - 1 >= s1_min:
                central = True
                inside = rng.choice(group_array, expected_s1 + 1, replace=False)
                outside = rng.choice(complement, s - expected_s1 + 1, replace=False)
                upper = np.concatenate((inside, outside[: s - expected_s1 - 1]))
                lower = np.concatenate((inside[: expected_s1 - 1], outside))
            elif expected_s1 + 1 <= s1_max:
                central = False
                inside = rng.choice(group_array, expected_s1 + 1, replace=False)
                outside = rng.choice(complement, s - expected_s1, replace=False)
                upper = np.concatenate((inside, outside[: s - expected_s1 - 1]))
                lower = np.concatenate((inside[:expected_s1], outside))
            elif expected_s1 - 1 >= s1_min:
                central = False
                inside = rng.choice(group_array, expected_s1, replace=False)
                outside = rng.choice(complement, s - expected_s1 + 1, replace=False)
                upper = np.concatenate((inside, outside[: s - expected_s1]))
                lower = np.concatenate((inside[: expected_s1 - 1], outside))
            else:
                raise RuntimeError(f"No valid FGSV pair for s={s}, s0={s0}, n={n}")

            difference = utility(upper) - utility(lower)
            estimate = s0 / n * (1 - s0 / n) * difference / (int(central) + 1)
            ts[s - 1] = counts[s - 1] / (counts[s - 1] + 1) * ts[s - 1] + estimate / (
                counts[s - 1] + 1
            )
            counts[s - 1] += 1

        if utility.calls > budget or utility.calls - (budget - remaining) != selected_cost:
            raise AssertionError("FGSV budget accounting mismatch")

    useful_calls = utility.calls
    while utility.calls < budget:
        utility(np.array([], dtype=int))
    return {
        "estimate": float(linear + ts.sum()),
        "useful_calls": useful_calls,
        "padding_calls": budget - useful_calls,
        "sampled_s": {str(key): sampled_s[key] for key in sorted(sampled_s)},
        "size_update_counts": counts.tolist(),
    }


def permutation_group_mc(
    utility: CountingUtility,
    n: int,
    groups: dict[str, list[int]],
    budget: int,
    rng: np.random.RandomState,
) -> dict[str, object]:
    if budget % (n + 1):
        raise ValueError("complete-permutation budget must be divisible by n+1")
    permutations = budget // (n + 1)
    individual_sum = np.zeros(n, dtype=float)
    for _ in range(permutations):
        order = rng.permutation(n)
        previous = utility(np.array([], dtype=int))
        for position in range(n):
            current = utility(order[: position + 1])
            individual_sum[order[position]] += current - previous
            previous = current
    individual = individual_sum / permutations
    return {
        "estimates": {name: float(individual[indexes].sum()) for name, indexes in groups.items()},
        "individual_estimates": individual.tolist(),
        "permutations": permutations,
    }


def group_metrics(estimates: dict[str, float], truth: dict[str, float]) -> dict[str, object]:
    names = list(truth)
    exact = np.asarray([truth[name] for name in names], dtype=float)
    actual = np.asarray([estimates[name] for name in names], dtype=float)
    errors = np.abs(actual - exact)
    relative = np.divide(errors, np.abs(exact), out=np.full_like(errors, np.nan), where=exact != 0)
    correlation = spearmanr(exact, actual).statistic
    return {
        "absolute_errors": {name: float(errors[i]) for i, name in enumerate(names)},
        "relative_errors": {name: float(relative[i]) for i, name in enumerate(names)},
        "total_l1_error": float(errors.sum()),
        "spearman": None if math.isnan(float(correlation)) else float(correlation),
        "estimate_sum": float(actual.sum()),
        "budget_balance_gap": float(actual.sum() - 1000.0),
    }


def audit_value_table(values: list[float], n: int) -> dict[str, object]:
    marginal_min = math.inf
    marginal_max = -math.inf
    marginal_negative = 0
    for mask in range(1 << n):
        for player in range(n):
            bit = 1 << player
            if mask & bit:
                continue
            delta = values[mask | bit] - values[mask]
            marginal_min = min(marginal_min, delta)
            marginal_max = max(marginal_max, delta)
            marginal_negative += int(delta < -1e-12)

    interaction_min = math.inf
    interaction_max = -math.inf
    interaction_negative = interaction_positive = interaction_zero = 0
    for first in range(n):
        for second in range(first + 1, n):
            bits = (1 << first) | (1 << second)
            for mask in range(1 << n):
                if mask & bits:
                    continue
                interaction = (
                    values[mask | bits]
                    - values[mask | (1 << first)]
                    - values[mask | (1 << second)]
                    + values[mask]
                )
                interaction_min = min(interaction_min, interaction)
                interaction_max = max(interaction_max, interaction)
                if interaction < -1e-12:
                    interaction_negative += 1
                elif interaction > 1e-12:
                    interaction_positive += 1
                else:
                    interaction_zero += 1
    return {
        "marginal_edges": n * (1 << (n - 1)),
        "marginal_minimum": marginal_min,
        "marginal_maximum": marginal_max,
        "marginal_negative_count": marginal_negative,
        "pair_interactions": math.comb(n, 2) * (1 << (n - 2)),
        "interaction_minimum": interaction_min,
        "interaction_maximum": interaction_max,
        "interaction_negative_count": interaction_negative,
        "interaction_zero_count": interaction_zero,
        "interaction_positive_count": interaction_positive,
        "scope": "finite exhaustive D1-P check; not a proof of asymptotic stability",
    }


def main() -> None:
    if LOG.exists():
        LOG.unlink()
    tracemalloc.start()
    total_started = time.perf_counter()
    log("R2-1/R2-2 D1-P FGSV same-target experiment started")

    spec = load_d1p_spec(ROOT / "config" / "d1p_design.yaml")
    states = all_incremental_states(spec)
    suite = D1PValueSuite(spec, states[-1], ROOT / "config" / "value_spec_v3_2.yaml")
    all_values = suite.all_values(states)
    owner_raw = yaml.safe_load(
        (ROOT / "config" / "owner_map_fgsv_r2.yaml").read_text(encoding="utf-8")
    )
    player_index = {record.record_id: record.player_index for record in spec.records}
    owner_maps = {
        map_name: {
            group: [player_index[player] for player in players]
            for group, players in groups.items()
        }
        for map_name, groups in owner_raw["maps"].items()
    }

    float_tables = {name: [float(value) for value in all_values[name]] for name in VALUE_NAMES}
    online_equivalence = {}
    for value_name in VALUE_NAMES:
        maximum = max(
            abs(evaluate_state_float(suite, state, value_name) - float_tables[value_name][mask])
            for mask, state in enumerate(states)
        )
        online_equivalence[value_name] = maximum
        if maximum >= 1e-10:
            raise AssertionError(f"online value mismatch for {value_name}: {maximum}")

    exact_allocations = {
        "V_count": exact_shapley_subset(all_values["V_count"], spec.player_count),
        "V1": exact_shapley_subset(all_values["V1"], spec.player_count),
        "V2_lambda_0_5": exact_shapley_decimal(
            all_values["V2_lambda_0_5"], spec.player_count, precision=100
        ),
    }
    exact_groups: dict[str, dict[str, dict[str, float]]] = {}
    for value_name, allocation in exact_allocations.items():
        exact_groups[value_name] = {}
        for map_name, groups in owner_maps.items():
            exact_groups[value_name][map_name] = {
                group: float(sum((allocation[index] for index in indexes), allocation[0] * 0))
                for group, indexes in groups.items()
            }

    truth_output = {
        "players": [record.record_id for record in spec.records],
        "coalitions": 1 << spec.player_count,
        "record_shapley": {
            name: [text_number(value) for value in allocation]
            for name, allocation in exact_allocations.items()
        },
        "group_truth": exact_groups,
        "owner_maps": owner_raw["maps"],
        "online_vs_table_max_abs_error": online_equivalence,
    }
    (OUT / "exact_targets.json").write_text(
        json.dumps(truth_output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    stability = {
        name: audit_value_table(float_tables[name], spec.player_count) for name in VALUE_NAMES
    }
    (OUT / "stability_and_interactions.json").write_text(
        json.dumps(stability, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    rows: list[dict[str, object]] = []
    for mode in ("A_TABLE", "B_ONLINE_STATE"):
        for value_index, value_name in enumerate(VALUE_NAMES):
            table = float_tables[value_name]

            def evaluator_for(current_mode: str) -> Callable[[int], float]:
                if current_mode == "A_TABLE":
                    return lambda mask: table[mask]
                return lambda mask: evaluate_state_float(
                    suite, state_for_mask(mask, spec), value_name
                )

            for map_index, (map_name, groups) in enumerate(owner_maps.items()):
                truth = exact_groups[value_name][map_name]
                for nominal in NOMINAL_BUDGETS:
                    effective = common_effective_budget(nominal, spec.player_count)
                    allocations = even_group_budgets(effective, len(groups))
                    for seed in SEEDS:
                        base_seed = 1_000_000 * value_index + 10_000 * map_index + seed

                        fgsv_started = time.perf_counter()
                        fgsv_rng = np.random.RandomState(base_seed)
                        fgsv_estimates: dict[str, float] = {}
                        fgsv_details = {}
                        fgsv_utilities = []
                        for (group, indexes), group_budget in zip(groups.items(), allocations):
                            utility = CountingUtility(spec.player_count, evaluator_for(mode))
                            detail = fgsv_budget_capped(
                                utility,
                                spec.player_count,
                                indexes,
                                group_budget,
                                fgsv_rng,
                            )
                            fgsv_estimates[group] = float(detail["estimate"])
                            fgsv_details[group] = detail
                            fgsv_utilities.append(utility)
                        fgsv_seconds = time.perf_counter() - fgsv_started
                        fgsv_metrics = group_metrics(fgsv_estimates, truth)
                        rows.append(
                            {
                                "mode": mode,
                                "value": value_name,
                                "owner_map": map_name,
                                "nominal_budget": nominal,
                                "effective_budget": effective,
                                "method": "FGSV_CODE_DERIVED_BUDGET_CAPPED",
                                "seed": seed,
                                "group_estimates": json.dumps(fgsv_estimates, sort_keys=True),
                                "group_truth": json.dumps(truth, sort_keys=True),
                                **fgsv_metrics,
                                "utility_calls": sum(item.calls for item in fgsv_utilities),
                                "useful_calls": sum(
                                    int(detail["useful_calls"]) for detail in fgsv_details.values()
                                ),
                                "padding_calls": sum(
                                    int(detail["padding_calls"]) for detail in fgsv_details.values()
                                ),
                                "runtime_seconds": fgsv_seconds,
                                "utility_compute_seconds": sum(
                                    item.compute_seconds for item in fgsv_utilities
                                ),
                                "sampled_coalition_sizes": json.dumps(
                                    merge_histograms([item.size_histogram for item in fgsv_utilities]),
                                    sort_keys=True,
                                ),
                                "fgsv_group_budgets": json.dumps(dict(zip(groups, allocations))),
                                "peak_rss_bytes_cumulative": process_peak_rss_bytes(),
                            }
                        )

                        mc_utility = CountingUtility(spec.player_count, evaluator_for(mode))
                        mc_started = time.perf_counter()
                        mc = permutation_group_mc(
                            mc_utility,
                            spec.player_count,
                            groups,
                            effective,
                            np.random.RandomState(base_seed),
                        )
                        mc_seconds = time.perf_counter() - mc_started
                        mc_metrics = group_metrics(mc["estimates"], truth)
                        rows.append(
                            {
                                "mode": mode,
                                "value": value_name,
                                "owner_map": map_name,
                                "nominal_budget": nominal,
                                "effective_budget": effective,
                                "method": "UNIFORM_COMPLETE_PERMUTATION_MC",
                                "seed": seed,
                                "group_estimates": json.dumps(mc["estimates"], sort_keys=True),
                                "group_truth": json.dumps(truth, sort_keys=True),
                                **mc_metrics,
                                "utility_calls": mc_utility.calls,
                                "useful_calls": mc_utility.calls,
                                "padding_calls": 0,
                                "runtime_seconds": mc_seconds,
                                "utility_compute_seconds": mc_utility.compute_seconds,
                                "sampled_coalition_sizes": json.dumps(
                                    {str(k): v for k, v in sorted(mc_utility.size_histogram.items())},
                                    sort_keys=True,
                                ),
                                "fgsv_group_budgets": "",
                                "peak_rss_bytes_cumulative": process_peak_rss_bytes(),
                            }
                        )
                    log(f"completed {mode} {value_name} {map_name} budget={nominal}")

    fieldnames = list(rows[0])
    with (OUT / "raw_runs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    grouped: dict[tuple, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(row["mode"], row["value"], row["owner_map"], row["nominal_budget"], row["method"])].append(row)
    summaries = []
    for key, items in grouped.items():
        l1 = [float(item["total_l1_error"]) for item in items]
        gap = [float(item["budget_balance_gap"]) for item in items]
        runtime = [float(item["runtime_seconds"]) for item in items]
        calls = [int(item["utility_calls"]) for item in items]
        summaries.append(
            {
                "mode": key[0],
                "value": key[1],
                "owner_map": key[2],
                "nominal_budget": key[3],
                "method": key[4],
                "repetitions": len(items),
                "total_l1_mean": statistics.fmean(l1),
                "total_l1_std": statistics.stdev(l1),
                "total_l1_min": min(l1),
                "total_l1_max": max(l1),
                "budget_gap_mean": statistics.fmean(gap),
                "runtime_mean_seconds": statistics.fmean(runtime),
                "runtime_std_seconds": statistics.stdev(runtime),
                "utility_calls_min": min(calls),
                "utility_calls_max": max(calls),
            }
        )

    current_mem, peak_python = tracemalloc.get_traced_memory()
    result = {
        "status": "SAME_TARGET_ADAPTED",
        "official_source_modified": False,
        "methods": [
            "FGSV_CODE_DERIVED_BUDGET_CAPPED",
            "UNIFORM_COMPLETE_PERMUTATION_MC",
        ],
        "modes": {
            "A_TABLE": "read-only lookup over the verified 4096-coalition table",
            "B_ONLINE_STATE": "state_for_mask recomputed for every utility call; no coalition cache",
        },
        "nominal_budgets": list(NOMINAL_BUDGETS),
        "effective_common_budgets": {
            str(budget): common_effective_budget(budget, spec.player_count)
            for budget in NOMINAL_BUDGETS
        },
        "budget_note": (
            "Complete permutation MC requires multiples of n+1=13. The common effective budget is "
            "the largest even multiple of 13 not exceeding the nominal cap, so it can also be split "
            "into three even FGSV group budgets. FGSV padding calls are explicitly reported."
        ),
        "repetitions": len(SEEDS),
        "seeds": list(SEEDS),
        "threshold": THRESHOLD,
        "summary": summaries,
        "stability": stability,
        "online_equivalence": online_equivalence,
        "total_seconds": time.perf_counter() - total_started,
        "python_tracemalloc_peak_bytes": peak_python,
        "process_peak_rss_bytes": process_peak_rss_bytes(),
    }
    (OUT / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"completed all R2-1/R2-2 runs in {result['total_seconds']:.3f}s")


if __name__ == "__main__":
    main()
