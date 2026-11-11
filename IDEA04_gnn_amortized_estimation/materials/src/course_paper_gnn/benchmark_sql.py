from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import time
from pathlib import Path

import duckdb

from .audit_sql import _mask_list, _prepare_context, _select_games, _sql_utility
from .data import load_games, split_games


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark context-local SQL utility evaluations"
    )
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--split", default="in_distribution")
    parser.add_argument("--games", type=int, default=10)
    parser.add_argument("--budgets", default="64,256")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20261114)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    games = _select_games(
        split_games(load_games(args.data), args.split),
        args.games,
        args.seed,
    )
    budgets = [int(item) for item in args.budgets.split(",")]
    connection = duckdb.connect(str(args.db), read_only=True)
    rows: list[dict] = []
    try:
        for game in games:
            started = time.perf_counter()
            _prepare_context(connection, game)
            prepare_seconds = time.perf_counter() - started
            for budget in budgets:
                masks = _mask_list(
                    len(game.players),
                    str(budget),
                    args.seed + int(game.metadata["order_key"]),
                )
                started = time.perf_counter()
                for mask in masks:
                    connection.execute("DELETE FROM audit_active")
                    active_ids = [
                        (player.player_id,)
                        for player in game.players
                        if mask & (1 << player.player_index)
                    ]
                    if active_ids:
                        connection.executemany(
                            "INSERT INTO audit_active VALUES (?)",
                            active_ids,
                        )
                    _sql_utility(
                        connection,
                        game.condition["value_function"],
                    )
                elapsed = time.perf_counter() - started
                rows.append(
                    {
                        "game_id": game.game_id,
                        "split": game.split,
                        "condition": "/".join(game.condition.values()),
                        "players": len(game.players),
                        "budget": budget,
                        "context_prepare_ms": prepare_seconds * 1000.0,
                        "sql_seconds": elapsed,
                        "sql_ms_per_evaluation": elapsed * 1000.0 / len(masks),
                    }
                )
    finally:
        connection.close()

    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "per_game.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    groups: dict[tuple[int, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["budget"], row["split"]), []).append(row)
    summary = []
    for (budget, split), group in sorted(groups.items()):
        values = sorted(float(row["sql_ms_per_evaluation"]) for row in group)
        summary.append(
            {
                "budget": budget,
                "split": split,
                "games": len(group),
                "median_ms_per_sql_evaluation": statistics.median(values),
                "p95_ms_per_sql_evaluation": values[
                    min(len(values) - 1, round(0.95 * (len(values) - 1)))
                ],
                "median_context_prepare_ms": statistics.median(
                    float(row["context_prepare_ms"]) for row in group
                ),
            }
        )
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
