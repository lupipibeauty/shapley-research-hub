from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from .metrics import spearman


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze seed-ensemble uncertainty from per-player predictions"
    )
    parser.add_argument("--input", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite uncertainty output: {args.output}")

    grouped: dict[
        tuple[str, str, str, str],
        dict[str, list[float]],
    ] = defaultdict(lambda: {"predicted": [], "target": [], "error": []})
    for path in args.input:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                key = (
                    row["method"],
                    row["split"],
                    row["game_id"],
                    row["player_id"],
                )
                grouped[key]["predicted"].append(float(row["predicted_share"]))
                grouped[key]["target"].append(float(row["target_share"]))
                grouped[key]["error"].append(float(row["absolute_error"]))

    rows: list[dict] = []
    for (method, split, game_id, player_id), values in grouped.items():
        if len(values["predicted"]) < 2:
            continue
        target_values = values["target"]
        if max(target_values) - min(target_values) > 1e-12:
            raise ValueError(f"Target changed across seeds for {game_id}/{player_id}")
        target = statistics.mean(target_values)
        prediction = statistics.mean(values["predicted"])
        seed_sd = statistics.stdev(values["predicted"])
        absolute_error = abs(prediction - target)
        lower = prediction - 1.96 * seed_sd
        upper = prediction + 1.96 * seed_sd
        rows.append(
            {
                "method": method,
                "split": split,
                "game_id": game_id,
                "player_id": player_id,
                "target_share": target,
                "mean_prediction": prediction,
                "seed_sd": seed_sd,
                "absolute_error": absolute_error,
                "interval_low": lower,
                "interval_high": upper,
                "covered": int(lower <= target <= upper),
            }
        )

    summary: list[dict] = []
    grouped_summary: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped_summary[(row["method"], row["split"])].append(row)
    for (method, split), group in sorted(grouped_summary.items()):
        uncertainty = [float(row["seed_sd"]) for row in group]
        errors = [float(row["absolute_error"]) for row in group]
        sorted_indices = sorted(
            range(len(group)),
            key=lambda index: uncertainty[index],
        )
        quartile = max(1, len(group) // 4)
        low_group = [group[index] for index in sorted_indices[:quartile]]
        high_group = [group[index] for index in sorted_indices[-quartile:]]
        summary.append(
            {
                "method": method,
                "split": split,
                "players": len(group),
                "mean_seed_sd": statistics.mean(uncertainty),
                "median_seed_sd": statistics.median(uncertainty),
                "uncertainty_error_spearman": spearman(uncertainty, errors),
                "interval_coverage_95": statistics.mean(
                    float(row["covered"]) for row in group
                ),
                "low_uncertainty_quartile_mae": statistics.mean(
                    float(row["absolute_error"]) for row in low_group
                ),
                "high_uncertainty_quartile_mae": statistics.mean(
                    float(row["absolute_error"]) for row in high_group
                ),
            }
        )

    args.output.mkdir(parents=True)
    with (args.output / "per_player_uncertainty.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
