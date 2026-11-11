from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from .metrics import bootstrap_mean_ci


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Paired game-level comparison")
    parser.add_argument("--input", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reference-method", default="rpv_gnn")
    parser.add_argument("--reference-budget", type=int, default=0)
    parser.add_argument("--metric", default="share_l1")
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--permutation-samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20261110)
    return parser.parse_args()


def _holm(records: list[dict]) -> None:
    ordered = sorted(records, key=lambda row: row["p_raw"])
    running = 0.0
    count = len(ordered)
    for index, row in enumerate(ordered):
        adjusted = min(1.0, (count - index) * row["p_raw"])
        running = max(running, adjusted)
        row["p_holm"] = running
    for row in records:
        row.setdefault("p_holm", 1.0)


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite comparison directory: {args.output}")

    values: dict[tuple[str, int, str, str], list[float]] = defaultdict(list)
    for path in args.input:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                key = (
                    row.get("method") or "unknown",
                    int(row.get("budget", 0) or 0),
                    row.get("split", "unknown"),
                    row["game_id"],
                )
                values[key].append(float(row[args.metric]))

    game_values = {
        key: fmean(metric_values) for key, metric_values in values.items()
    }
    splits = sorted({key[2] for key in game_values})
    alternatives = sorted(
        {
            (method, budget)
            for method, budget, _split, _game in game_values
            if not (
                method == args.reference_method
                and budget == args.reference_budget
            )
        }
    )
    records: list[dict] = []
    for split in splits:
        family: list[dict] = []
        reference = {
            game_id: value
            for (method, budget, item_split, game_id), value in game_values.items()
            if method == args.reference_method
            and budget == args.reference_budget
            and item_split == split
        }
        for method, budget in alternatives:
            alternative = {
                game_id: value
                for (item_method, item_budget, item_split, game_id), value in game_values.items()
                if item_method == method
                and item_budget == budget
                and item_split == split
            }
            common = sorted(set(reference) & set(alternative))
            if not common:
                continue
            # Positive difference means the reference model has lower error.
            differences = [alternative[game] - reference[game] for game in common]
            observed = fmean(differences)
            low, high = bootstrap_mean_ci(
                differences,
                seed=args.seed,
                samples=args.bootstrap_samples,
            )
            rng = random.Random(args.seed)
            extreme = 0
            for _ in range(args.permutation_samples):
                flipped = [
                    value if rng.random() < 0.5 else -value for value in differences
                ]
                if abs(fmean(flipped)) >= abs(observed) - 1e-15:
                    extreme += 1
            p_value = (extreme + 1) / (args.permutation_samples + 1)
            row = {
                "split": split,
                "reference": args.reference_method,
                "reference_budget": args.reference_budget,
                "alternative": method,
                "alternative_budget": budget,
                "metric": args.metric,
                "games": len(common),
                "mean_difference": observed,
                "ci95_low": low,
                "ci95_high": high,
                "p_raw": p_value,
            }
            records.append(row)
            family.append(row)
        _holm(family)

    args.output.mkdir(parents=True)
    with (args.output / "paired_comparisons.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    (args.output / "paired_comparisons.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(records), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
