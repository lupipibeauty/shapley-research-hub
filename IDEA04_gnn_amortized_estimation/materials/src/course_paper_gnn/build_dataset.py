from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .constants import OOD_CONDITION
from .tpch import GenerationConfig, generate_games, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build TPC-H-derived games with exact Shapley labels"
    )
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--games-per-condition", type=int, default=125)
    parser.add_argument("--seed", type=int, default=20261107)
    parser.add_argument("--revenue-pool", type=float, default=1000.0)
    parser.add_argument("--max-lineitems", type=int, default=4)
    parser.add_argument("--max-nations", type=int, default=2)
    parser.add_argument(
        "--split-mode",
        choices=("training", "external"),
        default="training",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = GenerationConfig(
        database_path=args.db,
        output_path=args.output,
        games_per_condition=args.games_per_condition,
        seed=args.seed,
        revenue_pool=args.revenue_pool,
        max_lineitems=args.max_lineitems,
        max_nations=args.max_nations,
        split_mode=args.split_mode,
    )
    games = generate_games(config)
    write_jsonl(games, args.output)
    split_counts = Counter(game.split for game in games)
    condition_counts = Counter(
        (
            game.condition["source_sharing"],
            game.condition["hierarchy"],
            game.condition["value_function"],
        )
        for game in games
    )
    summary = {
        "output": str(args.output),
        "database": str(args.db),
        "games": len(games),
        "players": sum(len(game.players) for game in games),
        "coalition_values": sum(1 << len(game.players) for game in games),
        "split_counts": dict(split_counts),
        "condition_counts": {
            "/".join(key): value for key, value in sorted(condition_counts.items())
        },
        "ood_condition": "/".join(OOD_CONDITION),
        "seed": args.seed,
    }
    summary_path = args.output.with_suffix(args.output.suffix + ".summary.json")
    if summary_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing summary: {summary_path}")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
