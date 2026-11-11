from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import scipy
import yaml
from scipy.stats import t


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from aggregate_report_shapley.d1p import all_incremental_states, load_d1p_spec, state_for_mask
from aggregate_report_shapley.d1p_values import D1PValueSuite
from aggregate_report_shapley.exact_shapley import exact_shapley_decimal, exact_shapley_subset
from aggregate_report_shapley.fgsv_paper_formula import paper_formula_fgsv_budget_capped
from experiments.run_fgsv_r2_d1p import (
    CountingUtility,
    common_effective_budget,
    evaluate_state_float,
    even_group_budgets,
    fgsv_budget_capped,
    permutation_group_mc,
)


OUT = ROOT / "outputs" / "v4_0" / "R2_3"
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "run.log"
VALUE_NAMES = ("V_count", "V1", "V2_lambda_0_5")
NOMINAL_BUDGETS = (500, 1000, 2000, 5000)
SEEDS = tuple(range(30))
THRESHOLD = 10
METHOD_A = "A_OFFICIAL_CODE_DERIVED"
METHOD_B = "B_PAPER_FORMULA_CONSISTENT"
METHOD_C = "C_COMPLETE_PERMUTATION_MC"


def log(message: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"No rows to write: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def exact_targets(all_values, n: int, owner_maps: dict[str, dict[str, list[int]]]):
    allocations = {
        "V_count": exact_shapley_subset(all_values["V_count"], n),
        "V1": exact_shapley_subset(all_values["V1"], n),
        "V2_lambda_0_5": exact_shapley_decimal(
            all_values["V2_lambda_0_5"], n, precision=100
        ),
    }
    groups: dict[str, dict[str, dict[str, float]]] = {}
    for value_name, allocation in allocations.items():
        groups[value_name] = {}
        for map_name, mapping in owner_maps.items():
            groups[value_name][map_name] = {
                owner: float(sum((allocation[index] for index in indexes), allocation[0] * 0))
                for owner, indexes in mapping.items()
            }
    return allocations, groups


def run_group_estimator(
    *,
    estimator: Callable,
    evaluator: Callable[[int], float],
    n: int,
    groups: dict[str, list[int]],
    allocations: list[int],
    seed: int,
) -> tuple[dict[str, float], dict[str, dict[str, object]], float, float, int]:
    rng = np.random.RandomState(seed)
    estimates: dict[str, float] = {}
    details: dict[str, dict[str, object]] = {}
    total_started = time.perf_counter()
    total_compute = 0.0
    total_calls = 0
    for (owner, indexes), group_budget in zip(groups.items(), allocations):
        utility = CountingUtility(n, evaluator)
        group_started = time.perf_counter()
        detail = estimator(utility, n, indexes, group_budget, rng, THRESHOLD)
        group_wall = time.perf_counter() - group_started
        estimates[owner] = float(detail["estimate"])
        details[owner] = {
            **detail,
            "wall_seconds": group_wall,
            "utility_compute_seconds": utility.compute_seconds,
            "utility_calls": utility.calls,
            "utility_seconds_per_call": utility.compute_seconds / utility.calls,
            "wall_seconds_per_call": group_wall / utility.calls,
        }
        total_compute += utility.compute_seconds
        total_calls += utility.calls
    return estimates, details, time.perf_counter() - total_started, total_compute, total_calls


def summarize_owner_errors(owner_frame: pd.DataFrame) -> list[dict[str, object]]:
    keys = ["method", "value", "owner_map", "nominal_budget", "effective_budget", "owner"]
    rows: list[dict[str, object]] = []
    for key, frame in owner_frame.groupby(keys, sort=True):
        signed = frame["signed_error"].to_numpy(dtype=float)
        absolute = np.abs(signed)
        n = len(signed)
        critical = float(t.ppf(0.975, n - 1))
        bias = float(signed.mean())
        sample_sd = float(signed.std(ddof=1))
        population_variance = float(signed.var(ddof=0))
        rmse = float(np.sqrt(np.mean(signed**2)))
        mae = float(absolute.mean())
        bias_half = critical * sample_sd / math.sqrt(n)
        abs_sd = float(absolute.std(ddof=1))
        mae_half = critical * abs_sd / math.sqrt(n)
        rows.append(
            {
                **dict(zip(keys, key)),
                "repetitions": n,
                "truth": float(frame["truth"].iloc[0]),
                "estimate_mean": float(frame["estimate"].mean()),
                "systematic_bias_mean_signed_error": bias,
                "bias_ci95_low": bias - bias_half,
                "bias_ci95_high": bias + bias_half,
                "random_error_sd_across_seeds": sample_sd,
                "random_variance_population": population_variance,
                "mean_absolute_error": mae,
                "mae_ci95_low": max(0.0, mae - mae_half),
                "mae_ci95_high": mae + mae_half,
                "rmse": rmse,
                "bias_squared": bias**2,
                "mse": rmse**2,
                "mse_decomposition_residual": rmse**2 - bias**2 - population_variance,
                "single_owner_calls_mean": float(frame["single_owner_utility_calls"].mean()),
                "single_owner_runtime_mean_seconds": float(
                    frame["single_owner_runtime_seconds"].mean()
                ),
                "all_owner_calls_mean": float(frame["all_owner_utility_calls"].mean()),
                "all_owner_runtime_mean_seconds": float(
                    frame["all_owner_runtime_seconds"].mean()
                ),
                "utility_seconds_per_call_mean": float(
                    frame["utility_seconds_per_call"].mean()
                ),
                "wall_seconds_per_call_mean": float(frame["wall_seconds_per_call"].mean()),
                "single_owner_cost_semantics": str(
                    frame["single_owner_cost_semantics"].iloc[0]
                ),
            }
        )
    return rows


def paired_formula_comparisons(owner_frame: pd.DataFrame) -> list[dict[str, object]]:
    index = [
        "value",
        "owner_map",
        "nominal_budget",
        "effective_budget",
        "seed",
        "owner",
    ]
    pivot = owner_frame.pivot(index=index, columns="method", values="absolute_error").reset_index()
    pivot["B_minus_A_absolute_error"] = pivot[METHOD_B] - pivot[METHOD_A]
    pivot["B_minus_C_absolute_error"] = pivot[METHOD_B] - pivot[METHOD_C]
    rows: list[dict[str, object]] = []
    group_keys = ["value", "owner_map", "nominal_budget", "effective_budget", "owner"]
    for key, frame in pivot.groupby(group_keys, sort=True):
        row = dict(zip(group_keys, key))
        for column in ("B_minus_A_absolute_error", "B_minus_C_absolute_error"):
            values = frame[column].to_numpy(dtype=float)
            critical = float(t.ppf(0.975, len(values) - 1))
            mean = float(values.mean())
            half = critical * float(values.std(ddof=1)) / math.sqrt(len(values))
            row[f"{column}_mean"] = mean
            row[f"{column}_ci95_low"] = mean - half
            row[f"{column}_ci95_high"] = mean + half
        row["formula_lower_error_than_A_fraction"] = float(
            (frame["B_minus_A_absolute_error"] < 0).mean()
        )
        row["formula_lower_error_than_C_fraction"] = float(
            (frame["B_minus_C_absolute_error"] < 0).mean()
        )
        rows.append(row)
    return rows


def main() -> None:
    if LOG.exists():
        LOG.unlink()
    started = time.perf_counter()
    log("FGSV R2-3 started; historical R2 outputs are read-only")

    official_source = ROOT / "external" / "fgsv" / "source" / "Faithful_GSV-main" / "exp1_benchmark" / "estimators.py"
    official_archive = ROOT / "external" / "fgsv" / "archive" / "Faithful_GSV-main.zip"
    paper = Path(r"C:\Users\86156\Downloads\faithful group shapley value.pdf")
    historical = [
        ROOT / "outputs" / "v4_0" / "R2" / "d1p" / "raw_runs.csv",
        ROOT / "outputs" / "v4_0" / "R2" / "d1p" / "summary.json",
        ROOT / "outputs" / "v4_0" / "R2" / "minimal_counterexample.json",
    ]
    before_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in historical}

    preprocessing_started = time.perf_counter()
    spec = load_d1p_spec(ROOT / "config" / "d1p_design.yaml")
    states = all_incremental_states(spec)
    suite = D1PValueSuite(spec, states[-1], ROOT / "config" / "value_spec_v3_2.yaml")
    all_values = suite.all_values(states)
    preprocessing_seconds = time.perf_counter() - preprocessing_started
    owner_raw = yaml.safe_load(
        (ROOT / "config" / "owner_map_fgsv_r2.yaml").read_text(encoding="utf-8")
    )
    player_index = {record.record_id: record.player_index for record in spec.records}
    owner_maps = {
        map_name: {
            owner: [player_index[player] for player in players]
            for owner, players in mapping.items()
        }
        for map_name, mapping in owner_raw["maps"].items()
    }
    float_tables = {name: [float(value) for value in all_values[name]] for name in VALUE_NAMES}

    equivalence: dict[str, dict[str, float]] = {}
    for value_name in VALUE_NAMES:
        online_started = time.perf_counter()
        online_values = [
            evaluate_state_float(suite, state_for_mask(mask, spec), value_name)
            for mask in range(1 << spec.player_count)
        ]
        online_seconds = time.perf_counter() - online_started
        maximum = max(
            abs(online_values[mask] - float_tables[value_name][mask])
            for mask in range(1 << spec.player_count)
        )
        if maximum >= 1e-10:
            raise AssertionError(f"Online/table mismatch for {value_name}: {maximum}")
        equivalence[value_name] = {
            "max_abs_error": maximum,
            "calls": 1 << spec.player_count,
            "cumulative_seconds": online_seconds,
            "seconds_per_call": online_seconds / (1 << spec.player_count),
        }

    exact_started = time.perf_counter()
    allocations_exact, truth_groups = exact_targets(
        all_values, spec.player_count, owner_maps
    )
    exact_seconds = time.perf_counter() - exact_started
    exact_payload = {
        "players": [record.record_id for record in spec.records],
        "player_count": spec.player_count,
        "report_coordinate_count": 35,
        "coalition_count": 1 << spec.player_count,
        "owner_maps": owner_raw["maps"],
        "record_shapley": {
            value: [str(item) for item in allocation]
            for value, allocation in allocations_exact.items()
        },
        "owner_truth": truth_groups,
        "exact_computation_seconds": exact_seconds,
    }
    (OUT / "exact_targets.json").write_text(
        json.dumps(exact_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    run_rows: list[dict[str, object]] = []
    owner_rows: list[dict[str, object]] = []
    for value_index, value_name in enumerate(VALUE_NAMES):
        table = float_tables[value_name]
        evaluator = lambda mask, values=table: values[mask]
        for map_index, (map_name, groups) in enumerate(owner_maps.items()):
            truth = truth_groups[value_name][map_name]
            for nominal in NOMINAL_BUDGETS:
                effective = common_effective_budget(nominal, spec.player_count)
                group_budgets = even_group_budgets(effective, len(groups))
                for seed in SEEDS:
                    base_seed = 1_000_000 * value_index + 10_000 * map_index + seed
                    method_results: list[tuple[str, dict[str, float], dict, float, float, int]] = []

                    estimates_a, details_a, wall_a, compute_a, calls_a = run_group_estimator(
                        estimator=fgsv_budget_capped,
                        evaluator=evaluator,
                        n=spec.player_count,
                        groups=groups,
                        allocations=group_budgets,
                        seed=base_seed,
                    )
                    method_results.append(
                        (METHOD_A, estimates_a, details_a, wall_a, compute_a, calls_a)
                    )

                    estimates_b, details_b, wall_b, compute_b, calls_b = run_group_estimator(
                        estimator=paper_formula_fgsv_budget_capped,
                        evaluator=evaluator,
                        n=spec.player_count,
                        groups=groups,
                        allocations=group_budgets,
                        seed=base_seed,
                    )
                    method_results.append(
                        (METHOD_B, estimates_b, details_b, wall_b, compute_b, calls_b)
                    )

                    mc_utility = CountingUtility(spec.player_count, evaluator)
                    mc_started = time.perf_counter()
                    mc = permutation_group_mc(
                        mc_utility,
                        spec.player_count,
                        groups,
                        effective,
                        np.random.RandomState(base_seed),
                    )
                    mc_wall = time.perf_counter() - mc_started
                    method_results.append(
                        (
                            METHOD_C,
                            mc["estimates"],
                            {},
                            mc_wall,
                            mc_utility.compute_seconds,
                            mc_utility.calls,
                        )
                    )

                    for method, estimates, details, wall, compute, calls in method_results:
                        signed_errors = {
                            owner: estimates[owner] - truth[owner] for owner in groups
                        }
                        run_rows.append(
                            {
                                "method": method,
                                "value": value_name,
                                "owner_map": map_name,
                                "nominal_budget": nominal,
                                "effective_budget": effective,
                                "seed": seed,
                                "owner_estimates_json": json_text(estimates),
                                "owner_truth_json": json_text(truth),
                                "total_l1_error": sum(abs(error) for error in signed_errors.values()),
                                "estimate_sum": sum(estimates.values()),
                                "efficiency_gap": sum(estimates.values()) - 1000.0,
                                "utility_calls": calls,
                                "runtime_seconds": wall,
                                "utility_compute_seconds": compute,
                                "solver_overhead_seconds": wall - compute,
                                "utility_seconds_per_call": compute / calls,
                                "wall_seconds_per_call": wall / calls,
                                "group_budgets_json": json_text(dict(zip(groups, group_budgets)))
                                if method != METHOD_C
                                else "",
                                "details_json": json_text(details) if details else "",
                            }
                        )
                        for owner in groups:
                            if method == METHOD_C:
                                single_calls = calls
                                single_wall = wall
                                owner_compute = compute
                                semantics = (
                                    "current complete-permutation path computes the full record path; "
                                    "requesting one owner alone has the same observed cost as all owners"
                                )
                                useful = calls
                                padding = 0
                            else:
                                detail = details[owner]
                                single_calls = int(detail["utility_calls"])
                                single_wall = float(detail["wall_seconds"])
                                owner_compute = float(detail["utility_compute_seconds"])
                                semantics = "dedicated independent owner-group estimator run"
                                useful = int(detail["useful_calls"])
                                padding = int(detail["padding_calls"])
                            estimate = estimates[owner]
                            signed_error = estimate - truth[owner]
                            owner_rows.append(
                                {
                                    "method": method,
                                    "value": value_name,
                                    "owner_map": map_name,
                                    "nominal_budget": nominal,
                                    "effective_budget": effective,
                                    "seed": seed,
                                    "owner": owner,
                                    "owner_record_count": len(groups[owner]),
                                    "truth": truth[owner],
                                    "estimate": estimate,
                                    "signed_error": signed_error,
                                    "absolute_error": abs(signed_error),
                                    "single_owner_utility_calls": single_calls,
                                    "single_owner_useful_calls": useful,
                                    "single_owner_padding_calls": padding,
                                    "single_owner_runtime_seconds": single_wall,
                                    "single_owner_utility_compute_seconds": owner_compute,
                                    "single_owner_solver_overhead_seconds": single_wall - owner_compute,
                                    "utility_seconds_per_call": owner_compute / single_calls,
                                    "wall_seconds_per_call": single_wall / single_calls,
                                    "all_owner_utility_calls": calls,
                                    "all_owner_runtime_seconds": wall,
                                    "single_owner_cost_semantics": semantics,
                                }
                            )
                log(f"completed {value_name} {map_name} nominal_budget={nominal}")

    write_csv(OUT / "raw_runs.csv", run_rows)
    write_csv(OUT / "raw_owner_errors.csv", owner_rows)
    owner_frame = pd.DataFrame(owner_rows)
    owner_summary = summarize_owner_errors(owner_frame)
    write_csv(OUT / "owner_error_summary.csv", owner_summary)
    paired = paired_formula_comparisons(owner_frame)
    write_csv(OUT / "paired_method_comparisons.csv", paired)

    all_cost_rows: list[dict[str, object]] = []
    run_frame = pd.DataFrame(run_rows)
    for key, frame in run_frame.groupby(
        ["method", "value", "owner_map", "nominal_budget", "effective_budget"], sort=True
    ):
        all_cost_rows.append(
            {
                **dict(
                    zip(
                        ["method", "value", "owner_map", "nominal_budget", "effective_budget"],
                        key,
                    )
                ),
                "scope": "all_owners",
                "repetitions": len(frame),
                "utility_calls_mean": float(frame["utility_calls"].mean()),
                "runtime_mean_seconds": float(frame["runtime_seconds"].mean()),
                "runtime_sd_seconds": float(frame["runtime_seconds"].std(ddof=1)),
                "utility_compute_mean_seconds": float(frame["utility_compute_seconds"].mean()),
                "solver_overhead_mean_seconds": float(frame["solver_overhead_seconds"].mean()),
                "utility_seconds_per_call_mean": float(frame["utility_seconds_per_call"].mean()),
                "wall_seconds_per_call_mean": float(frame["wall_seconds_per_call"].mean()),
            }
        )
    write_csv(OUT / "all_owner_cost_summary.csv", all_cost_rows)

    after_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in historical}
    if before_hashes != after_hashes:
        raise AssertionError("Historical R2 files changed during R2-3")
    expected_runs = len(VALUE_NAMES) * len(owner_maps) * len(NOMINAL_BUDGETS) * len(SEEDS) * 3
    expected_owner_rows = expected_runs * 3
    if len(run_rows) != expected_runs or len(owner_rows) != expected_owner_rows:
        raise AssertionError(
            f"Unexpected row counts: runs={len(run_rows)}, owners={len(owner_rows)}"
        )
    if not np.isfinite(owner_frame[["truth", "estimate", "signed_error"]].to_numpy()).all():
        raise AssertionError("Non-finite owner result")
    if any(row["utility_calls"] != row["effective_budget"] for row in run_rows):
        raise AssertionError("Common utility-call budget was not respected")

    audit = {
        "status": "COMPLETED_R2_3_ONLY",
        "official_source_modified": False,
        "historical_r2_modified": False,
        "official_source_sha256": sha256(official_source),
        "official_archive_sha256": sha256(official_archive),
        "paper_sha256": sha256(paper),
        "historical_r2_hashes_before": before_hashes,
        "historical_r2_hashes_after": after_hashes,
        "formula_implementation_sha256": sha256(
            ROOT / "src" / "aggregate_report_shapley" / "fgsv_paper_formula.py"
        ),
        "runner_sha256": sha256(Path(__file__)),
        "model": {
            "records": spec.player_count,
            "report_coordinates": 35,
            "coalitions": 1 << spec.player_count,
            "values": list(VALUE_NAMES),
            "owner_maps": owner_raw["maps"],
        },
        "methods": [METHOD_A, METHOD_B, METHOD_C, "D_EXACT_SHAPLEY_TRUTH"],
        "formula_interpretation": {
            "equation_8": "includes n/[s(n-s)] after algebraic rewrite",
            "equation_9": "includes n/(n-1)",
            "equation_11_issue": (
                "printed |S|=s plus one added element targets size s+1, inconsistent with Eq.9"
            ),
            "equation_11_repair": (
                "use base |S|=s-1, then add one in-group or out-group element so both targets have size s"
            ),
            "large_branch_index": "floor(s*s0/n), not Python round",
        },
        "budgets": {
            str(nominal): common_effective_budget(nominal, spec.player_count)
            for nominal in NOMINAL_BUDGETS
        },
        "seeds": list(SEEDS),
        "threshold": THRESHOLD,
        "accuracy_mode": "verified read-only 4096-coalition lookup table",
        "table_preprocessing_seconds": preprocessing_seconds,
        "online_evaluator_full_table_benchmark": equivalence,
        "exact_truth_seconds": exact_seconds,
        "raw_run_rows": len(run_rows),
        "raw_owner_rows": len(owner_rows),
        "total_r2_3_seconds": time.perf_counter() - started,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
    }
    (OUT / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"R2-3 completed in {audit['total_r2_3_seconds']:.3f}s; stopping before scale-up")


if __name__ == "__main__":
    main()
