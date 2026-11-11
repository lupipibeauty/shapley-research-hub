from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

import torch

from .data import collate_games
from .external_adapter import build_d1p_games, build_p3_games
from .metrics import evaluate_game
from .model import build_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate frozen TPC-H models on D1-P/P3 schema adapters"
    )
    parser.add_argument("--d1p-coalitions", required=True, type=Path)
    parser.add_argument("--d1p-allocations", required=True, type=Path)
    parser.add_argument("--p3-fixture", required=True, type=Path)
    parser.add_argument("--p3-truth", required=True, type=Path)
    parser.add_argument("--checkpoint", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
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
        use_zero_mask=not bool(training_args["no_zero_mask"]),
        use_simplex=not bool(training_args["no_simplex"]),
    )
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, str(training_args["seed"]), str(checkpoint["model_name"])


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite output directory: {args.output}")
    games = build_d1p_games(
        args.d1p_coalitions,
        args.d1p_allocations,
    ) + build_p3_games(
        args.p3_fixture,
        args.p3_truth,
    )
    batch = collate_games(games)
    rows: list[dict] = []
    for game in games:
        owners = [player.owner_id for player in game.players]
        rows.append(
            {
                "method": "uniform_base",
                "model_family": "base",
                "seed": "",
                "game_id": game.game_id,
                "source_database": game.source_database,
                "value_name": game.metadata["value_name"],
                "players": len(game.players),
                **asdict(evaluate_game(game.base_share, game.shapley_share, owners)),
            }
        )
    for checkpoint_path in args.checkpoint:
        model, seed, model_family = _load_model(checkpoint_path)
        with torch.no_grad():
            predictions = model(batch)
        offset = 0
        for game in games:
            count = len(game.players)
            prediction = predictions[offset : offset + count].cpu().tolist()
            offset += count
            owners = [player.owner_id for player in game.players]
            rows.append(
                {
                    "method": f"{model_family}_zero_shot",
                    "model_family": model_family,
                    "seed": seed,
                    "game_id": game.game_id,
                    "source_database": game.source_database,
                    "value_name": game.metadata["value_name"],
                    "players": len(game.players),
                    **asdict(
                        evaluate_game(
                            prediction,
                            game.shapley_share,
                            owners,
                        )
                    ),
                }
            )
            if game.condition["value_function"] == "additive":
                prediction = game.base_share
            rows.append(
                {
                    "method": f"{model_family}_safe_route_zero_shot",
                    "model_family": model_family,
                    "seed": seed,
                    "game_id": game.game_id,
                    "source_database": game.source_database,
                    "value_name": game.metadata["value_name"],
                    "players": len(game.players),
                    **asdict(
                        evaluate_game(
                            prediction,
                            game.shapley_share,
                            owners,
                        )
                    ),
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
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["method"], row["game_id"]), []).append(row)
    summary = []
    for (method, game_id), group in sorted(grouped.items()):
        summary.append(
            {
                "method": method,
                "game_id": game_id,
                "runs": len(group),
                **{
                    metric: sum(float(row[metric]) for row in group) / len(group)
                    for metric in (
                        "share_l1",
                        "owner_l1",
                        "p95_abs_share",
                        "high_value_mae",
                        "spearman",
                        "ndcg3",
                        "efficiency_error",
                    )
                },
            }
        )
    metadata = {
        "games": [game.game_id for game in games],
        "checkpoints": [str(path) for path in args.checkpoint],
        "seeds": [_load_model(path)[1] for path in args.checkpoint],
        "mapping_status": "FROZEN_SEMANTIC_ADAPTER",
        "warning": (
            "Only four external games; results are descriptive and do not "
            "support a population-level generalization claim."
        ),
        "target_semantics": {
            "d1p_v1": "exact A0 standard Shapley",
            "d1p_v2": "exact A0 standard Shapley",
            "p3_g0": "exact physical-fact Shapley",
            "p3_g1": "exact physical-fact Shapley",
        },
    }
    (args.output / "summary.json").write_text(
        json.dumps(
            {"metadata": metadata, "summary": summary},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(rows), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
