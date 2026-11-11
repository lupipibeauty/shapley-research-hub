from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import asdict
from pathlib import Path

from .data import load_games, split_games
from .metrics import evaluate_game
from .tpch import utility_from_mask


def permutation_shapley(
    players: list,
    value_type: str,
    *,
    seed: int,
    nominal_steps: int,
) -> tuple[list[float], int]:
    if nominal_steps <= 0:
        raise ValueError("nominal_steps must be positive")
    n_players = len(players)
    permutation_count = max(1, nominal_steps // n_players)
    rng = random.Random(seed)
    totals = [0.0] * n_players
    utility_calls = 0
    for _ in range(permutation_count):
        order = list(range(n_players))
        rng.shuffle(order)
        mask = 0
        previous = utility_from_mask(players, mask, value_type)
        utility_calls += 1
        for player_index in order:
            mask |= 1 << player_index
            current = utility_from_mask(players, mask, value_type)
            utility_calls += 1
            totals[player_index] += current - previous
            previous = current
    total = sum(totals)
    if total <= 1e-12:
        return [1.0 / n_players] * n_players, utility_calls
    return [item / total for item in totals], utility_calls


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic non-neural baselines")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--split", default="in_distribution")
    parser.add_argument("--budgets", default="64,256,1024,4096")
    parser.add_argument("--seed", type=int, default=20261107)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite output directory: {args.output}")
    args.output.mkdir(parents=True)
    budgets = [int(item) for item in args.budgets.split(",") if item.strip()]
    games = split_games(load_games(args.data), args.split)
    if not games:
        raise RuntimeError(f"No games in split {args.split}")

    rows: list[dict] = []
    for game in games:
        owners = [player.owner_id for player in game.players]
        base_metric = evaluate_game(game.base_share, game.shapley_share, owners)
        rows.append(
            {
                "method": "base_share",
                "budget": 0,
                "utility_calls": 0,
                "seed": args.seed,
                "game_id": game.game_id,
                "split": game.split,
                "condition": "/".join(game.condition.values()),
                **asdict(base_metric),
            }
        )
        for budget in budgets:
            prediction, calls = permutation_shapley(
                game.players,
                game.condition["value_function"],
                seed=args.seed,
                nominal_steps=budget,
            )
            metric = evaluate_game(prediction, game.shapley_share, owners)
            rows.append(
                {
                    "method": "permutation_mc",
                    "budget": budget,
                    "utility_calls": calls,
                    "seed": args.seed,
                    "game_id": game.game_id,
                    "split": game.split,
                    "condition": "/".join(game.condition.values()),
                    **asdict(metric),
                }
            )

    with (args.output / "per_game_metrics.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    groups: dict[tuple[str, int], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["method"], int(row["budget"])), []).append(row)
    summary: list[dict] = []
    for (method, budget), group in sorted(groups.items()):
        summary.append(
            {
                "method": method,
                "budget": budget,
                "games": len(group),
                **{
                    field: sum(float(row[field]) for row in group) / len(group)
                    for field in (
                        "share_l1",
                        "owner_l1",
                        "mae_share",
                        "spearman",
                        "top3_overlap",
                        "zero_pay",
                        "efficiency_error",
                    )
                },
            }
        )
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
