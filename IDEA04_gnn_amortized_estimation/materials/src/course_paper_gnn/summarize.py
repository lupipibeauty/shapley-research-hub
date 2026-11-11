from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from .metrics import bootstrap_mean_ci


METRICS = (
    "share_l1",
    "owner_l1",
    "mae_share",
    "p95_abs_share",
    "max_abs_share",
    "high_value_mae",
    "spearman",
    "top3_overlap",
    "ndcg3",
    "zero_pay",
    "efficiency_error",
)

LOWER_IS_BETTER = {
    "share_l1",
    "owner_l1",
    "mae_share",
    "p95_abs_share",
    "max_abs_share",
    "high_value_mae",
    "zero_pay",
    "efficiency_error",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize per-game evaluation CSVs")
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        help="METHOD=PATH_TO_PER_GAME_CSV; may be repeated",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20261110)
    return parser.parse_args()


def _percentile(sorted_values: list[float], probability: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    location = probability * (len(sorted_values) - 1)
    lower = int(math.floor(location))
    upper = int(math.ceil(location))
    if lower == upper:
        return sorted_values[lower]
    fraction = location - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def _bootstrap_macro_ci(
    condition_values: list[list[float]],
    *,
    seed: int,
    samples: int,
) -> tuple[float, float]:
    import numpy as np

    rng = np.random.default_rng(seed)
    sampled_means = []
    for values in condition_values:
        array = np.asarray(values, dtype=float)
        indices = rng.integers(0, len(array), size=(samples, len(array)))
        sampled_means.append(array[indices].mean(axis=1))
    macro = np.mean(np.stack(sampled_means, axis=0), axis=0)
    lower, upper = np.quantile(macro, [0.025, 0.975])
    return float(lower), float(upper)


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite summary directory: {args.output}")

    output_rows: list[dict] = []
    raw_by_game: dict[tuple[str, int, str, str, str, str], list[float]] = defaultdict(
        list
    )
    for specification in args.input:
        if "=" not in specification:
            raise ValueError(f"Expected METHOD=PATH, got {specification!r}")
        fallback_method, path_text = specification.split("=", 1)
        path = Path(path_text)
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                method = row.get("method") or fallback_method
                budget = int(row.get("budget", 0) or 0)
                split = row.get("split", "unknown")
                condition = row.get("condition", "unknown")
                for metric in METRICS:
                    if metric not in row:
                        continue
                    raw_by_game[
                        (method, budget, split, condition, row["game_id"], metric)
                    ].append(
                        float(row[metric])
                    )

    # Combine seeds within a game before estimating uncertainty over games.
    game_level: dict[tuple[str, int, str, str, str], list[float]] = defaultdict(list)
    overall_level: dict[tuple[str, int, str, str], list[float]] = defaultdict(list)
    for (
        method,
        budget,
        split,
        condition,
        _game_id,
        metric,
    ), values in raw_by_game.items():
        game_mean = statistics.mean(values)
        game_level[(method, budget, split, condition, metric)].append(game_mean)
        overall_level[(method, budget, split, metric)].append(game_mean)

    combined_groups = [
        (method, budget, split, condition, metric, values)
        for (method, budget, split, condition, metric), values in game_level.items()
    ] + [
        (method, budget, split, "overall", metric, values)
        for (method, budget, split, metric), values in overall_level.items()
    ]

    by_condition: dict[
        tuple[str, int, str, str], dict[str, list[float]]
    ] = defaultdict(dict)
    for (
        method,
        budget,
        split,
        condition,
        metric,
    ), values in game_level.items():
        by_condition[(method, budget, split, metric)][condition] = values
    for (method, budget, split, metric), condition_groups in sorted(
        by_condition.items()
    ):
        condition_means = [
            statistics.mean(values) for values in condition_groups.values()
        ]
        macro_mean = statistics.mean(condition_means)
        lower, upper = _bootstrap_macro_ci(
            list(condition_groups.values()),
            seed=args.bootstrap_seed,
            samples=args.bootstrap_samples,
        )
        combined_groups.append(
            (
                method,
                budget,
                split,
                "macro",
                metric,
                [macro_mean],
            )
        )
        # Preserve macro CI separately because a one-value pseudo-sample has
        # no meaningful game-level bootstrap interval.
        output_rows.append(
            {
                "method": method,
                "budget": budget,
                "split": split,
                "condition": "macro",
                "metric": metric,
                "games": sum(len(values) for values in condition_groups.values()),
                "mean": macro_mean,
                "sd": statistics.stdev(condition_means)
                if len(condition_means) > 1
                else 0.0,
                "median": statistics.median(condition_means),
                "q1": _percentile(sorted(condition_means), 0.25),
                "q3": _percentile(sorted(condition_means), 0.75),
                "ci95_low": lower,
                "ci95_high": upper,
            }
        )

    for method, budget, split, condition, metric, values in sorted(
        combined_groups,
        key=lambda item: (item[0], item[1], item[2], item[3], item[4]),
    ):
        if condition == "macro":
            continue
        ordered = sorted(values)
        mean = statistics.mean(values)
        sd = statistics.stdev(values) if len(values) > 1 else 0.0
        lower, upper = bootstrap_mean_ci(
            values,
            seed=args.bootstrap_seed,
            samples=args.bootstrap_samples,
        )
        output_rows.append(
            {
                "method": method,
                "budget": budget,
                "split": split,
                "condition": condition,
                "metric": metric,
                "games": len(values),
                "mean": mean,
                "sd": sd,
                "median": statistics.median(values),
                "q1": _percentile(ordered, 0.25),
                "q3": _percentile(ordered, 0.75),
                "ci95_low": lower,
                "ci95_high": upper,
            }
        )

    worst_rows: list[dict] = []
    for (method, budget, split, metric), condition_groups in sorted(
        by_condition.items()
    ):
        if not condition_groups:
            continue
        means = {
            condition: statistics.mean(values)
            for condition, values in condition_groups.items()
        }
        selector = max if metric in LOWER_IS_BETTER else min
        worst_condition, worst_value = selector(
            means.items(), key=lambda item: item[1]
        )
        worst_rows.append(
            {
                "method": method,
                "budget": budget,
                "split": split,
                "metric": metric,
                "worst_condition": worst_condition,
                "worst_value": worst_value,
            }
        )

    args.output.mkdir(parents=True)
    with (args.output / "summary_metrics.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    (args.output / "summary_metrics.json").write_text(
        json.dumps(output_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with (args.output / "worst_conditions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(worst_rows[0]))
        writer.writeheader()
        writer.writerows(worst_rows)
    print(json.dumps({"rows": len(output_rows), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
