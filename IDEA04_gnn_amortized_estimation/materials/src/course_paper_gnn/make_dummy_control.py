from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from .constants import NUMERIC_FEATURE_DIM
from .data import load_games
from .schema import GameRecord, NodeRecord, PlayerRecord
from .tpch import write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create disconnected dummy-player controls")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261112)
    return parser.parse_args()


def select_stratified(games: list[GameRecord], count: int, seed: int) -> list[GameRecord]:
    rng = random.Random(seed)
    grouped: dict[str, list[GameRecord]] = defaultdict(list)
    for game in games:
        grouped["/".join(game.condition.values())].append(game)
    for values in grouped.values():
        rng.shuffle(values)
    selected: list[GameRecord] = []
    depth = 0
    while len(selected) < min(count, len(games)):
        added = False
        for key in sorted(grouped):
            if depth < len(grouped[key]):
                selected.append(grouped[key][depth])
                added = True
                if len(selected) >= count:
                    break
        if not added:
            break
        depth += 1
    return selected


def main() -> None:
    args = parse_args()
    games = select_stratified(load_games(args.data), args.games, args.seed)
    rng = random.Random(args.seed)
    output_games: list[GameRecord] = []
    for game_counter, game in enumerate(games):
        dummy_count = 1 + game_counter % 3
        players = list(game.players)
        nodes = list(game.graph.nodes)
        player_node_ids = list(game.graph.player_node_ids)
        base_share = list(game.base_share)
        target_share = list(game.shapley_share)
        dummy_ids: list[str] = []
        for offset in range(dummy_count):
            player_index = len(players)
            player_id = f"dummy:{game.game_id}:{offset}"
            dummy_ids.append(player_id)
            players.append(
                PlayerRecord(
                    player_id=player_id,
                    player_index=player_index,
                    relation="nation",
                    relation_key=f"dummy-{offset}",
                    owner_id=f"dummy-owner:{game.game_id}:{offset}",
                    attributes={"region_key": float(offset)},
                )
            )
            nodes.append(
                NodeRecord(
                    node_id=player_id,
                    node_type="player",
                    subtype="player_nation",
                    features=[0.0] * NUMERIC_FEATURE_DIM,
                )
            )
            player_node_ids.append(player_id)
            base_share.append(0.0)
            target_share.append(0.0)

        output_games.append(
            GameRecord(
                game_id=game.game_id + "_dummy",
                source_database=game.source_database,
                split=game.split,
                condition=dict(game.condition),
                players=players,
                relation_edges=list(game.relation_edges),
                graph=type(game.graph)(
                    nodes=nodes,
                    edges=list(game.graph.edges),
                    player_node_ids=player_node_ids,
                    value_descriptor=list(game.graph.value_descriptor),
                ),
                base_share=base_share,
                shapley_share=target_share,
                revenue_pool=game.revenue_pool,
                metadata={
                    **game.metadata,
                    "dummy_player_ids": dummy_ids,
                    "dummy_player_count": dummy_count,
                },
            )
        )

    write_jsonl(output_games, args.output)
    summary = {
        "source": str(args.data),
        "output": str(args.output),
        "games": len(output_games),
        "dummy_players": sum(
            int(game.metadata["dummy_player_count"]) for game in output_games
        ),
        "seed": args.seed,
    }
    args.output.with_suffix(args.output.suffix + ".summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
