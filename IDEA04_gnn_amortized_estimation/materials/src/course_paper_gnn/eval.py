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
    parser = argparse.ArgumentParser(description="Evaluate a trained contribution model")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--split", default="in_distribution")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--method-label", default=None)
    parser.add_argument("--safe-route-additive", action="store_true")
    parser.add_argument("--disable-zero-mask", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation directory: {args.output}")
    args.output.mkdir(parents=True)
    # The checkpoint is produced locally by train.py. Explicitly opt out of
    # weights-only loading so the run configuration can be restored as well.
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
        use_anchor=not bool(training_args["no_anchor"]),
        use_zero_mask=(
            not bool(training_args["no_zero_mask"])
            and not args.disable_zero_mask
        ),
        use_simplex=not bool(training_args["no_simplex"]),
    )
    model.load_state_dict(checkpoint["model_state"])
    games = split_games(load_games(args.data), args.split)
    if not games:
        raise RuntimeError(f"No games in split {args.split}")
    summary, rows = evaluate(
        model,
        games,
        args.batch_size,
        torch.device("cpu"),
        safe_route_additive=args.safe_route_additive,
    )
    model_name = checkpoint["model_name"]
    inferred_method = model_name
    if model_name == "rpv_gnn":
        suffixes = []
        if bool(training_args.get("no_edges", False)):
            suffixes.append("no_edges")
        if bool(training_args.get("no_anchor", False)):
            suffixes.append("no_anchor")
        if bool(training_args.get("no_zero_mask", False)):
            suffixes.append("no_zero_mask")
        if bool(training_args.get("no_simplex", False)):
            suffixes.append("no_simplex")
        if suffixes:
            inferred_method = "rpv_gnn_" + "_".join(suffixes)
    if args.safe_route_additive:
        inferred_method = f"{inferred_method}_safe_route"
    if args.disable_zero_mask:
        inferred_method = f"{inferred_method}_zero_mask_disabled"
    method_label = args.method_label or inferred_method
    for row in rows:
        row["method"] = method_label
        row["seed"] = int(training_args["seed"])
    with (args.output / "per_game_metrics.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "summary.json").write_text(
        json.dumps(
            {
                "checkpoint": str(args.checkpoint),
                "split": args.split,
                "games": len(games),
                **summary,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
