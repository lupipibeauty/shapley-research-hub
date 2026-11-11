from __future__ import annotations

import ast
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "v4_0" / "R2" / "d1p"


def main() -> None:
    rows = list(csv.DictReader((OUT / "raw_runs.csv").open(encoding="utf-8")))
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))

    assert len(rows) == 2880, len(rows)
    assert len(summary["summary"]) == 96, len(summary["summary"])
    assert all(item["repetitions"] == 30 for item in summary["summary"])

    expected_effective = {500: 494, 1000: 988, 2000: 1976, 5000: 4992}
    key_counts: Counter[tuple[str, ...]] = Counter()
    budget_failures = []
    nonfinite_failures = []
    mode_rows: defaultdict[tuple[str, ...], dict[str, dict[str, str]]] = defaultdict(dict)

    for row in rows:
        nominal = int(row["nominal_budget"])
        effective = int(row["effective_budget"])
        calls = int(row["utility_calls"])
        useful = int(row["useful_calls"])
        padding = int(row["padding_calls"])
        if not (
            effective == expected_effective[nominal]
            and calls == effective
            and useful + padding == calls
        ):
            budget_failures.append(row)
        for field in ("total_l1_error", "budget_balance_gap", "runtime_seconds"):
            value = float(row[field])
            if not (-float("inf") < value < float("inf")):
                nonfinite_failures.append((field, row))

        group_key = (
            row["mode"], row["value"], row["owner_map"], row["nominal_budget"], row["method"]
        )
        key_counts[group_key] += 1
        paired_key = (
            row["value"], row["owner_map"], row["nominal_budget"], row["method"], row["seed"]
        )
        mode_rows[paired_key][row["mode"]] = row

    assert not budget_failures, len(budget_failures)
    assert not nonfinite_failures, len(nonfinite_failures)
    assert len(key_counts) == 96
    assert set(key_counts.values()) == {30}

    max_mode_estimate_difference = 0.0
    max_mode_metric_difference = 0.0
    missing_mode_pairs = 0
    for paired in mode_rows.values():
        if set(paired) != {"A_TABLE", "B_ONLINE_STATE"}:
            missing_mode_pairs += 1
            continue
        left, right = paired["A_TABLE"], paired["B_ONLINE_STATE"]
        left_est = json.loads(left["group_estimates"])
        right_est = json.loads(right["group_estimates"])
        max_mode_estimate_difference = max(
            max_mode_estimate_difference,
            max(abs(float(left_est[k]) - float(right_est[k])) for k in left_est),
        )
        max_mode_metric_difference = max(
            max_mode_metric_difference,
            abs(float(left["total_l1_error"]) - float(right["total_l1_error"])),
            abs(float(left["budget_balance_gap"]) - float(right["budget_balance_gap"])),
        )
    assert missing_mode_pairs == 0
    assert max_mode_estimate_difference < 1e-9, max_mode_estimate_difference

    table_summary = [item for item in summary["summary"] if item["mode"] == "A_TABLE"]
    table_raw: defaultdict[tuple[str, str, int, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["mode"] == "A_TABLE":
            table_raw[
                (row["value"], row["owner_map"], int(row["nominal_budget"]), row["method"])
            ].append(row)
    compact = []
    comparisons = []
    lookup = {
        (item["value"], item["owner_map"], int(item["nominal_budget"]), item["method"]): item
        for item in table_summary
    }
    for value in ("V_count", "V1", "V2_lambda_0_5"):
        for owner_map in ("G-equal", "G-skew"):
            for nominal in (500, 1000, 2000, 5000):
                fgsv = lookup[(value, owner_map, nominal, "FGSV_CODE_DERIVED_BUDGET_CAPPED")]
                mc = lookup[(value, owner_map, nominal, "UNIFORM_COMPLETE_PERMUTATION_MC")]
                fgsv_l1 = float(fgsv["total_l1_mean"])
                mc_l1 = float(mc["total_l1_mean"])
                fgsv_raw = table_raw[(value, owner_map, nominal, "FGSV_CODE_DERIVED_BUDGET_CAPPED")]
                mc_raw = table_raw[(value, owner_map, nominal, "UNIFORM_COMPLETE_PERMUTATION_MC")]
                winner = "FGSV" if fgsv_l1 < mc_l1 else "MC" if mc_l1 < fgsv_l1 else "TIE"
                compact.append(
                    {
                        "value": value,
                        "owner_map": owner_map,
                        "nominal_budget": nominal,
                        "effective_budget": expected_effective[nominal],
                        "fgsv_l1_mean": fgsv_l1,
                        "fgsv_l1_std": float(fgsv["total_l1_std"]),
                        "mc_l1_mean": mc_l1,
                        "mc_l1_std": float(mc["total_l1_std"]),
                        "fgsv_mean_abs_efficiency_gap": statistics.fmean(
                            abs(float(row["budget_balance_gap"])) for row in fgsv_raw
                        ),
                        "mc_mean_abs_efficiency_gap": statistics.fmean(
                            abs(float(row["budget_balance_gap"])) for row in mc_raw
                        ),
                        "fgsv_spearman_mean": statistics.fmean(float(row["spearman"]) for row in fgsv_raw),
                        "mc_spearman_mean": statistics.fmean(float(row["spearman"]) for row in mc_raw),
                        "fgsv_padding_calls_mean": statistics.fmean(
                            int(row["padding_calls"]) for row in fgsv_raw
                        ),
                        "winner": winner,
                        "fgsv_over_mc_l1": fgsv_l1 / mc_l1 if mc_l1 else None,
                    }
                )
                comparisons.append(winner)

    runtime_by_mode: defaultdict[str, list[float]] = defaultdict(list)
    utility_time_by_mode: defaultdict[str, list[float]] = defaultdict(list)
    for row in rows:
        runtime_by_mode[row["mode"]].append(float(row["runtime_seconds"]))
        utility_time_by_mode[row["mode"]].append(float(row["utility_compute_seconds"]))

    value_budget_digest = []
    for value in ("V_count", "V1", "V2_lambda_0_5"):
        for nominal in (500, 1000, 2000, 5000):
            selected = [
                item
                for item in compact
                if item["value"] == value and item["nominal_budget"] == nominal
            ]
            value_budget_digest.append(
                {
                    "value": value,
                    "nominal_budget": nominal,
                    "effective_budget": expected_effective[nominal],
                    "fgsv_l1_mean_across_owner_maps": statistics.fmean(
                        item["fgsv_l1_mean"] for item in selected
                    ),
                    "mc_l1_mean_across_owner_maps": statistics.fmean(
                        item["mc_l1_mean"] for item in selected
                    ),
                    "fgsv_mean_abs_efficiency_gap_across_owner_maps": statistics.fmean(
                        item["fgsv_mean_abs_efficiency_gap"] for item in selected
                    ),
                    "mc_mean_abs_efficiency_gap_across_owner_maps": statistics.fmean(
                        item["mc_mean_abs_efficiency_gap"] for item in selected
                    ),
                }
            )

    validation = {
        "status": "PASS",
        "raw_rows": len(rows),
        "summary_cells": len(summary["summary"]),
        "repetitions_per_cell": sorted(set(key_counts.values())),
        "budget_failures": len(budget_failures),
        "nonfinite_failures": len(nonfinite_failures),
        "missing_A_B_pairs": missing_mode_pairs,
        "max_A_B_group_estimate_abs_difference": max_mode_estimate_difference,
        "max_A_B_metric_abs_difference": max_mode_metric_difference,
        "winner_cell_counts": dict(Counter(comparisons)),
        "mean_runtime_seconds_per_run": {
            mode: sum(values) / len(values) for mode, values in runtime_by_mode.items()
        },
        "mean_utility_compute_seconds_per_run": {
            mode: sum(values) / len(values) for mode, values in utility_time_by_mode.items()
        },
        "experiment_total_seconds": summary["total_seconds"],
        "python_tracemalloc_peak_bytes": summary["python_tracemalloc_peak_bytes"],
        "process_peak_rss_bytes": summary["process_peak_rss_bytes"],
        "value_budget_digest": value_budget_digest,
        "compact_accuracy_table": compact,
    }
    (OUT / "validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in validation.items() if k != "compact_accuracy_table"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
