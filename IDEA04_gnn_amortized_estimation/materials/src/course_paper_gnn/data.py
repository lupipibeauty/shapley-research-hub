from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .constants import EDGE_TYPE_TO_ID, NODE_TYPE_TO_ID, SUBTYPE_TO_ID
from .schema import GameRecord


def load_games(path: str | Path) -> list[GameRecord]:
    games: list[GameRecord] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                games.append(GameRecord.from_dict(json.loads(line)))
            except Exception as exc:
                raise ValueError(f"Invalid game at line {line_number}: {exc}") from exc
    if not games:
        raise ValueError(f"No games found in {path}")
    ids = [game.game_id for game in games]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate game_id values in dataset")
    return games


def split_games(
    games: Iterable[GameRecord],
    split: str,
) -> list[GameRecord]:
    materialized = list(games)
    if split == "all":
        return materialized
    return [game for game in materialized if game.split == split]


@dataclass(slots=True)
class CollatedBatch:
    x: object
    node_type: object
    subtype: object
    edge_index: object
    edge_type: object
    graph_index: object
    player_index: object
    player_graph_index: object
    base_share: object
    target_share: object
    value_descriptor: object
    structural_zero: object
    owners: list[list[str]]
    game_ids: list[str]
    splits: list[str]
    conditions: list[dict[str, str]]


def collate_games(games: Sequence[GameRecord]) -> CollatedBatch:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for graph collation") from exc

    all_features: list[list[float]] = []
    all_node_types: list[int] = []
    all_subtypes: list[int] = []
    all_edges: list[tuple[int, int]] = []
    all_edge_types: list[int] = []
    all_graph_index: list[int] = []
    player_indices: list[int] = []
    player_graph_index: list[int] = []
    base_share: list[float] = []
    target_share: list[float] = []
    value_descriptors: list[list[float]] = []
    structural_zero: list[bool] = []
    owners: list[list[str]] = []

    node_offset = 0
    for graph_index, game in enumerate(games):
        id_to_local = {
            node.node_id: index for index, node in enumerate(game.graph.nodes)
        }
        adjacency: dict[str, list[str]] = defaultdict(list)
        report_ids = set()
        for node in game.graph.nodes:
            if node.node_type == "report":
                report_ids.add(node.node_id)
        for edge in game.graph.edges:
            adjacency[edge.source].append(edge.target)

        def reaches_report(start: str) -> bool:
            queue = deque([start])
            visited = {start}
            while queue:
                current = queue.popleft()
                if current in report_ids:
                    return True
                for neighbor in adjacency.get(current, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            return False

        for node in game.graph.nodes:
            all_features.append(node.features)
            all_node_types.append(NODE_TYPE_TO_ID[node.node_type])
            all_subtypes.append(SUBTYPE_TO_ID[node.subtype])
            all_graph_index.append(graph_index)
        for edge in game.graph.edges:
            all_edges.append(
                (
                    id_to_local[edge.source] + node_offset,
                    id_to_local[edge.target] + node_offset,
                )
            )
            all_edge_types.append(EDGE_TYPE_TO_ID[edge.edge_type])
        for player_index, player_node_id in enumerate(game.graph.player_node_ids):
            global_player_index = id_to_local[player_node_id] + node_offset
            player_indices.append(global_player_index)
            player_graph_index.append(graph_index)
            base_share.append(game.base_share[player_index])
            target_share.append(game.shapley_share[player_index])
            # Structural zero is determined from graph reachability only. Target
            # Shapley values are never inspected when constructing model inputs.
            structural_zero.append(not reaches_report(player_node_id))
        owners.append([player.owner_id for player in game.players])
        value_descriptors.append(game.graph.value_descriptor)
        node_offset += len(game.graph.nodes)

    if not all_edges:
        raise ValueError("A graph batch must contain at least one edge")

    x = torch.tensor(all_features, dtype=torch.float32)
    node_type = torch.tensor(all_node_types, dtype=torch.long)
    subtype = torch.tensor(all_subtypes, dtype=torch.long)
    edge_index = torch.tensor(all_edges, dtype=torch.long).t().contiguous()
    edge_type = torch.tensor(all_edge_types, dtype=torch.long)
    graph_index_tensor = torch.tensor(all_graph_index, dtype=torch.long)
    player_index_tensor = torch.tensor(player_indices, dtype=torch.long)
    player_graph_index_tensor = torch.tensor(player_graph_index, dtype=torch.long)
    return CollatedBatch(
        x=x,
        node_type=node_type,
        subtype=subtype,
        edge_index=edge_index,
        edge_type=edge_type,
        graph_index=graph_index_tensor,
        player_index=player_index_tensor,
        player_graph_index=player_graph_index_tensor,
        base_share=torch.tensor(base_share, dtype=torch.float32),
        target_share=torch.tensor(target_share, dtype=torch.float32),
        value_descriptor=torch.tensor(value_descriptors, dtype=torch.float32),
        structural_zero=torch.tensor(structural_zero, dtype=torch.bool),
        owners=owners,
        game_ids=[game.game_id for game in games],
        splits=[game.split for game in games],
        conditions=[dict(game.condition) for game in games],
    )
