from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .data import load_games


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a generated game dataset")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    games = load_games(args.data)
    split_counts = Counter(game.split for game in games)
    condition_counts = Counter(
        "/".join(game.condition.values()) for game in games
    )
    player_counts = Counter(len(game.players) for game in games)
    errors: list[str] = []
    zero_players = 0
    for game in games:
        if len({player.player_id for player in game.players}) != len(game.players):
            errors.append(f"{game.game_id}: duplicate player IDs")
        if len(game.graph.player_node_ids) != len(game.players):
            errors.append(f"{game.game_id}: graph/player count mismatch")
        if abs(sum(game.shapley_share) - 1.0) > 1e-8:
            errors.append(f"{game.game_id}: target shares do not sum to one")
        if abs(sum(game.base_share) - 1.0) > 1e-8:
            errors.append(f"{game.game_id}: base shares do not sum to one")
        if any(item < -1e-12 for item in game.shapley_share):
            errors.append(f"{game.game_id}: negative target share")
        zero_players += sum(item <= 1e-12 for item in game.shapley_share)
    if len({game.game_id for game in games}) != len(games):
        errors.append("Duplicate game IDs in dataset")
    report = {
        "status": "PASS" if not errors else "FAIL",
        "games": len(games),
        "players": sum(len(game.players) for game in games),
        "coalition_values": sum(1 << len(game.players) for game in games),
        "zero_players": zero_players,
        "split_counts": dict(split_counts),
        "condition_counts": dict(condition_counts),
        "player_count_distribution": {
            str(key): value for key, value in sorted(player_counts.items())
        },
        "errors": errors,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
