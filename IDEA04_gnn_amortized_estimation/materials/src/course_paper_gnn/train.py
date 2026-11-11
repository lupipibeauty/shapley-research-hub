from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

import torch
from torch import nn

from .data import CollatedBatch, collate_games, load_games, split_games
from .metrics import evaluate_game
from .model import build_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train RPV-GNN or Feature-MLP")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", choices=("rpv_gnn", "feature_mlp"), default="rpv_gnn")
    parser.add_argument("--seed", type=int, default=20261107)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--ranking-weight", type=float, default=0.3)
    parser.add_argument("--zero-weight", type=float, default=0.1)
    parser.add_argument("--no-edges", action="store_true")
    parser.add_argument("--no-anchor", action="store_true")
    parser.add_argument("--no-zero-mask", action="store_true")
    parser.add_argument("--no-simplex", action="store_true")
    return parser.parse_args()


def _batch_to_device(batch: CollatedBatch, device: torch.device) -> CollatedBatch:
    return CollatedBatch(
        x=batch.x.to(device),
        node_type=batch.node_type.to(device),
        subtype=batch.subtype.to(device),
        edge_index=batch.edge_index.to(device),
        edge_type=batch.edge_type.to(device),
        graph_index=batch.graph_index.to(device),
        player_index=batch.player_index.to(device),
        player_graph_index=batch.player_graph_index.to(device),
        base_share=batch.base_share.to(device),
        target_share=batch.target_share.to(device),
        value_descriptor=batch.value_descriptor.to(device),
        structural_zero=batch.structural_zero.to(device),
        owners=batch.owners,
        game_ids=batch.game_ids,
        splits=batch.splits,
        conditions=batch.conditions,
    )


def _ranking_loss(
    prediction: torch.Tensor,
    target: torch.Tensor,
    graph_index: torch.Tensor,
) -> torch.Tensor:
    losses: list[torch.Tensor] = []
    for graph_id in torch.unique(graph_index):
        mask = graph_index == graph_id
        pred = prediction[mask]
        truth = target[mask]
        target_difference = truth.unsqueeze(0) - truth.unsqueeze(1)
        prediction_difference = pred.unsqueeze(0) - pred.unsqueeze(1)
        valid = target_difference > 1e-12
        if torch.any(valid):
            losses.append(torch.nn.functional.softplus(-prediction_difference[valid]).mean())
    if not losses:
        return prediction.sum() * 0.0
    return torch.stack(losses).mean()


def _loss(
    prediction: torch.Tensor,
    batch: CollatedBatch,
    ranking_weight: float,
    zero_weight: float,
) -> tuple[torch.Tensor, dict[str, float]]:
    huber = nn.functional.huber_loss(prediction, batch.target_share, delta=0.05)
    ranking = _ranking_loss(prediction, batch.target_share, batch.player_graph_index)
    zero_mask = batch.target_share <= 1e-12
    zero_penalty = prediction[zero_mask].sum() / max(batch.value_descriptor.shape[0], 1)
    total = huber + ranking_weight * ranking + zero_weight * zero_penalty
    return total, {
        "huber": float(huber.detach().cpu()),
        "ranking": float(ranking.detach().cpu()),
        "zero": float(zero_penalty.detach().cpu()),
    }


@torch.no_grad()
def evaluate(
    model: nn.Module,
    games: Sequence,
    batch_size: int,
    device: torch.device,
    *,
    safe_route_additive: bool = False,
    detail_sink: list[dict] | None = None,
) -> tuple[dict[str, float], list[dict]]:
    model.eval()
    rows: list[dict] = []
    for start in range(0, len(games), batch_size):
        selected = games[start : start + batch_size]
        batch = _batch_to_device(collate_games(selected), device)
        prediction = model(batch)
        prediction_by_graph: list[list[float]] = []
        target_by_graph: list[list[float]] = []
        offset = 0
        for game in selected:
            count = len(game.players)
            player_prediction = prediction[offset : offset + count]
            if (
                safe_route_additive
                and game.condition["value_function"] == "additive"
            ):
                player_prediction = batch.base_share[offset : offset + count]
            prediction_by_graph.append(player_prediction.detach().cpu().tolist())
            target_by_graph.append(
                batch.target_share[offset : offset + count].detach().cpu().tolist()
            )
            offset += count
        for game, pred, truth in zip(selected, prediction_by_graph, target_by_graph):
            metric = evaluate_game(pred, truth, [item.owner_id for item in game.players])
            if detail_sink is not None:
                for player, predicted_value, target_value in zip(
                    game.players,
                    pred,
                    truth,
                ):
                    detail_sink.append(
                        {
                            "game_id": game.game_id,
                            "split": game.split,
                            "condition": "/".join(game.condition.values()),
                            "player_id": player.player_id,
                            "owner_id": player.owner_id,
                            "predicted_share": float(predicted_value),
                            "target_share": float(target_value),
                            "absolute_error": abs(
                                float(predicted_value) - float(target_value)
                            ),
                        }
                    )
            row = {
                "game_id": game.game_id,
                "split": game.split,
                "condition": "/".join(game.condition.values()),
                "method": None,
                **asdict(metric),
            }
            rows.append(row)
    if not rows:
        raise ValueError("No rows were evaluated")
    fields = (
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
    summary = {
        field: sum(float(row[field]) for row in rows) / len(rows)
        for field in fields
    }
    return summary, rows


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite run directory: {args.output}")
    args.output.mkdir(parents=True)
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    games = load_games(args.data)
    train_games = split_games(games, "train")
    validation_games = split_games(games, "validation")
    if not train_games:
        raise RuntimeError("No train games found")
    if not validation_games:
        raise RuntimeError("No validation games found; use a larger smoke dataset")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(
        args.model,
        hidden_dim=args.hidden_dim,
        num_layers=args.num_layers,
        dropout=args.dropout,
        use_edges=not args.no_edges,
        use_anchor=not args.no_anchor,
        use_zero_mask=not args.no_zero_mask,
        use_simplex=not args.no_simplex,
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=0.5,
        patience=5,
    )

    best_loss = float("inf")
    best_epoch = -1
    stale_epochs = 0
    training_started = time.perf_counter()
    history_path = args.output / "history.jsonl"
    with history_path.open("w", encoding="utf-8") as history:
        for epoch in range(args.epochs):
            epoch_started = time.perf_counter()
            model.train()
            order = list(range(len(train_games)))
            random.Random(args.seed + epoch).shuffle(order)
            epoch_losses: list[float] = []
            for start in range(0, len(order), args.batch_size):
                selected = [train_games[index] for index in order[start : start + args.batch_size]]
                batch = _batch_to_device(collate_games(selected), device)
                optimizer.zero_grad(set_to_none=True)
                prediction = model(batch)
                loss, _parts = _loss(
                    prediction,
                    batch,
                    args.ranking_weight,
                    args.zero_weight,
                )
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
                optimizer.step()
                epoch_losses.append(float(loss.detach().cpu()))

            validation_summary, _ = evaluate(
                model,
                validation_games,
                args.batch_size,
                device,
            )
            train_loss = sum(epoch_losses) / max(len(epoch_losses), 1)
            record = {
                "epoch": epoch + 1,
                "train_loss": train_loss,
                "epoch_seconds": time.perf_counter() - epoch_started,
                **{f"validation_{key}": value for key, value in validation_summary.items()},
                "learning_rate": optimizer.param_groups[0]["lr"],
            }
            history.write(json.dumps(record, ensure_ascii=False) + "\n")
            history.flush()
            validation_loss = validation_summary["share_l1"]
            scheduler.step(validation_loss)

            if validation_loss < best_loss:
                best_loss = validation_loss
                best_epoch = epoch + 1
                stale_epochs = 0
                torch.save(
                    {
                        "model_name": args.model,
                        "model_state": model.state_dict(),
                        "args": {
                            key: str(value) if isinstance(value, Path) else value
                            for key, value in vars(args).items()
                        },
                        "best_epoch": best_epoch,
                        "best_validation_share_l1": best_loss,
                    },
                    args.output / "best_model.pt",
                )
            else:
                stale_epochs += 1
            print(json.dumps(record, ensure_ascii=False))
            if stale_epochs >= args.patience:
                break

    (args.output / "run_config.json").write_text(
        json.dumps(
            {
                **vars(args),
                "output": str(args.output),
                "data": str(args.data),
                "best_epoch": best_epoch,
                "best_validation_share_l1": best_loss,
                "device": str(device),
                "training_seconds": time.perf_counter() - training_started,
            },
            indent=2,
            default=str,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
