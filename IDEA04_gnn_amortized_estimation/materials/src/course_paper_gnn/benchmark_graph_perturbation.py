from __future__ import annotations

import argparse
import copy
import csv
import json
import random
from dataclasses import asdict
from pathlib import Path

import torch

from .data import collate_games, load_games, split_games
from .metrics import evaluate_game
from .model import build_model


PERTURBED_EDGE_TYPES = {
    "witness_supports_coordinate",
    "coordinate_to_value_factor",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate relation-graph edge-removal robustness"
    )
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--external-data", type=Path)
    parser.add_argument("--checkpoint", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--splits", default="in_distribution,ood,scale_ood")
    parser.add_argument(
        "--fractions",
        default="0,0.05,0.1,0.2,0.3",
    )
    parser.add_argument(
        "--perturb-seeds",
        default="20261120,20261121,20261122",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    return parser.parse_args()


def _load_model(path: Path) -> tuple[object, str, str]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    training_args = checkpoint["args"]
    model = build_model(
        checkpoint["model_name"],
        hidden_dim=int(training_args["hidden_dim"]),
        num_layers=int(training_args["num_layers"]),
        dropout=float(training_args["dropout"]),
        use_edges=not bool(training_args.get("no_edges", False)),
        use_anchor=not bool(training_args["no_anchor"]),
        use_zero_mask=not bool(training_args.get("no_zero_mask", False)),
        use_simplex=not bool(training_args.get("no_simplex", False)),
    )
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, str(training_args["seed"]), str(checkpoint["model_name"])


def _perturb_games(
    games: list,
    fraction: float,
    seed: int,
) -> tuple[list, int, int]:
    rng = random.Random(seed)
    perturbed = copy.deepcopy(games)
    removed = 0
    eligible = 0
    for game in perturbed:
        eligible_indices = [
            index
            for index, edge in enumerate(game.graph.edges)
            if edge.edge_type in PERTURBED_EDGE_TYPES
        ]
        eligible += len(eligible_indices)
        remove_count = int(round(fraction * len(eligible_indices)))
        removed_indices = set(rng.sample(eligible_indices, remove_count))
        kept = [
            edge
            for index, edge in enumerate(game.graph.edges)
            if index not in removed_indices
        ]
        if not kept:
            raise ValueError("Graph batch must retain at least one edge")
        game.graph.edges = kept
        removed += remove_count
    return perturbed, removed, eligible


def _evaluate(
    model: object,
    games: list,
    batch_size: int,
) -> list[dict]:
    rows: list[dict] = []
    with torch.no_grad():
        for start in range(0, len(games), batch_size):
            selected = games[start : start + batch_size]
            batch = collate_games(selected)
            prediction = model(batch)
            offset = 0
            for game in selected:
                count = len(game.players)
                predicted = prediction[offset : offset + count].cpu().tolist()
                offset += count
                metric = evaluate_game(
                    predicted,
                    game.shapley_share,
                    [player.owner_id for player in game.players],
                )
                rows.append(
                    {
                        "game_id": game.game_id,
                        "split": game.split,
                        "condition": "/".join(game.condition.values()),
                        **asdict(metric),
                    }
                )
    return rows


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite output directory: {args.output}")
    all_games = load_games(args.data)
    if args.external_data is not None:
        all_games.extend(load_games(args.external_data))
    splits = [item for item in args.splits.split(",") if item]
    fractions = [float(item) for item in args.fractions.split(",") if item]
    perturb_seeds = [int(item) for item in args.perturb_seeds.split(",") if item]
    model_specs = [_load_model(path) for path in args.checkpoint]

    rows: list[dict] = []
    for split in splits:
        games = split_games(all_games, split)
        if not games:
            raise RuntimeError(f"No games in split {split}")
        for fraction in fractions:
            seeds = [0] if fraction == 0 else perturb_seeds
            for perturb_seed in seeds:
                selected_games, removed, eligible = _perturb_games(
                    games,
                    fraction,
                    perturb_seed,
                )
                for model, model_seed, model_family in model_specs:
                    for metric_row in _evaluate(
                        model,
                        selected_games,
                        args.batch_size,
                    ):
                        rows.append(
                            {
                                "method": (
                                    f"{model_family}_perturb_"
                                    f"{int(round(fraction * 100)):02d}"
                                ),
                                "model_family": model_family,
                                "training_seed": model_seed,
                                "perturb_fraction": fraction,
                                "perturb_seed": perturb_seed,
                                "removed_edges": removed,
                                "eligible_edges": eligible,
                                **metric_row,
                            }
                        )

    args.output.mkdir(parents=True)
    with (args.output / "per_game_metrics.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "data": str(args.data),
        "external_data": (
            str(args.external_data) if args.external_data is not None else None
        ),
        "checkpoints": [str(path) for path in args.checkpoint],
        "splits": splits,
        "fractions": fractions,
        "perturb_seeds": perturb_seeds,
        "perturbed_edge_types": sorted(PERTURBED_EDGE_TYPES),
        "analysis_unit": "game within split; training seeds averaged in summarize.py",
        "removal_semantics": (
            "random removal of witness-to-coordinate and "
            "coordinate-to-value-factor edges; player and report nodes retained"
        ),
    }
    (args.output / "run_config.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(rows), **metadata}, indent=2))


if __name__ == "__main__":
    main()
