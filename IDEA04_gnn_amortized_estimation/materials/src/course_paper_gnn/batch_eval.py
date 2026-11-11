from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import torch

from .data import load_games, split_games
from .model import build_model
from .train import evaluate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate one checkpoint on all splits")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--external-data", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--method-label", required=True)
    parser.add_argument("--safe-route-additive", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checkpoint = torch.load(
        args.checkpoint,
        map_location="cpu",
        weights_only=False,
    )
    training_args = checkpoint["args"]
    model = build_model(
        checkpoint["model_name"],
        hidden_dim=int(training_args["hidden_dim"]),
        num_layers=int(training_args["num_layers"]),
        dropout=float(training_args["dropout"]),
        use_edges=not bool(training_args.get("no_edges", False)),
        use_anchor=not bool(training_args.get("no_anchor", False)),
        use_zero_mask=not bool(training_args.get("no_zero_mask", False)),
        use_simplex=not bool(training_args.get("no_simplex", False)),
    )
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    jobs = (
        ("in_distribution", args.data, "in_distribution"),
        ("ood", args.data, "ood"),
        ("sf1", args.external_data, "scale_ood"),
    )
    for tag, data_path, split in jobs:
        games = split_games(load_games(data_path), split)
        if not games:
            raise RuntimeError(f"No games for split {split} in {data_path}")
        details: list[dict] = []
        summary, rows = evaluate(
            model,
            games,
            args.batch_size,
            torch.device("cpu"),
            safe_route_additive=args.safe_route_additive,
            detail_sink=details,
        )
        for row in rows:
            row["method"] = args.method_label
            row["seed"] = int(training_args["seed"])
        for row in details:
            row["method"] = args.method_label
            row["seed"] = int(training_args["seed"])
        output = args.output_root / tag
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite: {output}")
        output.mkdir(parents=True)
        with (output / "per_game_metrics.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        with (output / "per_player_predictions.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(details[0]))
            writer.writeheader()
            writer.writerows(details)
        (output / "summary.json").write_text(
            json.dumps(
                {
                    "checkpoint": str(args.checkpoint),
                    "split": split,
                    "games": len(games),
                    "method": args.method_label,
                    **summary,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "tag": tag,
                    "split": split,
                    "games": len(games),
                    "method": args.method_label,
                    **summary,
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
