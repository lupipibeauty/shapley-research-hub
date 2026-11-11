from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path

from .baselines import permutation_shapley
from .data import collate_games, load_games, split_games


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark model or MC inference")
    parser.add_argument("--mode", choices=("model", "mc"), required=True)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--split", default="in_distribution")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--batch-sizes", default="1,8,32")
    parser.add_argument("--budgets", default="64,256,1024")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20261113)
    return parser.parse_args()


def _p95(values: list[float]) -> float:
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return ordered[index]


def _model_benchmark(args: argparse.Namespace, games: list, output: Path) -> None:
    import torch

    from .model import build_model

    if args.checkpoint is None:
        raise ValueError("--checkpoint is required for model mode")
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
        use_zero_mask=not bool(training_args["no_zero_mask"]),
        use_simplex=not bool(training_args["no_simplex"]),
    )
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    device = torch.device("cpu")
    batch_sizes = [int(item) for item in args.batch_sizes.split(",")]
    rows: list[dict] = []
    for batch_size in batch_sizes:
        batches = [
            games[start : start + batch_size]
            for start in range(0, len(games), batch_size)
        ]
        model(_batch_to_device(collate_games(batches[0]), device))
        for repeat in range(args.repeats):
            total_collate = 0.0
            total_forward = 0.0
            total_games = 0
            for selected in batches:
                started = time.perf_counter()
                batch = _batch_to_device(collate_games(selected), device)
                collated = time.perf_counter()
                with torch.no_grad():
                    _ = model(batch)
                finished = time.perf_counter()
                total_collate += collated - started
                total_forward += finished - collated
                total_games += len(selected)
            total = total_collate + total_forward
            rows.append(
                {
                    "repeat": repeat,
                    "batch_size": batch_size,
                    "games": total_games,
                    "collate_seconds": total_collate,
                    "forward_seconds": total_forward,
                    "total_seconds": total,
                    "games_per_second": total_games / total,
                    "milliseconds_per_game": 1000.0 * total / total_games,
                }
            )
    _write_rows(rows, output)


def _batch_to_device(batch: object, device: object) -> object:
    from .data import CollatedBatch

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


def _mc_benchmark(args: argparse.Namespace, games: list, output: Path) -> None:
    budgets = [int(item) for item in args.budgets.split(",")]
    rows: list[dict] = []
    for game in games:
        for budget in budgets:
            started = time.perf_counter()
            permutation_shapley(
                game.players,
                game.condition["value_function"],
                seed=args.seed,
                nominal_steps=budget,
            )
            elapsed = time.perf_counter() - started
            rows.append(
                {
                    "game_id": game.game_id,
                    "split": game.split,
                    "budget": budget,
                    "seconds": elapsed,
                    "milliseconds_per_game": elapsed * 1000.0,
                }
            )
    _write_rows(rows, output)


def _write_rows(rows: list[dict], output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite benchmark output: {output}")
    output.mkdir(parents=True)
    with (output / "per_run.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    group_keys = [
        key
        for key in ("batch_size", "budget")
        if key in rows[0] and key in {name for row in rows for name in row}
    ]
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = tuple(row[name] for name in group_keys)
        groups.setdefault(key, []).append(row)
    summaries: list[dict] = []
    for key, group in sorted(groups.items()):
        milliseconds = [float(row["milliseconds_per_game"]) for row in group]
        summary = dict(zip(group_keys, key))
        summary.update(
            {
                "n": len(milliseconds),
                "mean_ms_per_game": statistics.mean(milliseconds),
                "median_ms_per_game": statistics.median(milliseconds),
                "p95_ms_per_game": _p95(milliseconds),
            }
        )
        summaries.append(summary)
    (output / "summary.json").write_text(
        json.dumps(summaries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summaries, indent=2, ensure_ascii=False))


def main() -> None:
    args = parse_args()
    games = split_games(load_games(args.data), args.split)
    if not games:
        raise RuntimeError(f"No games in split {args.split}")
    if args.mode == "model":
        _model_benchmark(args, games, args.output)
    else:
        _mc_benchmark(args, games, args.output)


if __name__ == "__main__":
    main()
