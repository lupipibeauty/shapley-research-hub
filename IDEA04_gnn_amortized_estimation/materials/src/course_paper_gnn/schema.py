from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .constants import NUMERIC_FEATURE_DIM, VALUE_DESCRIPTOR_DIM


@dataclass(slots=True)
class PlayerRecord:
    player_id: str
    player_index: int
    relation: str
    relation_key: str
    owner_id: str
    attributes: dict[str, float | str | int]
    links: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PlayerRecord":
        return cls(
            player_id=str(value["player_id"]),
            player_index=int(value["player_index"]),
            relation=str(value["relation"]),
            relation_key=str(value["relation_key"]),
            owner_id=str(value["owner_id"]),
            attributes=dict(value.get("attributes", {})),
            links={str(key): str(item) for key, item in value.get("links", {}).items()},
        )


@dataclass(slots=True)
class NodeRecord:
    node_id: str
    node_type: str
    subtype: str
    features: list[float]

    def __post_init__(self) -> None:
        if len(self.features) != NUMERIC_FEATURE_DIM:
            raise ValueError(
                f"Expected {NUMERIC_FEATURE_DIM} node features for {self.node_id}, "
                f"got {len(self.features)}"
            )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "NodeRecord":
        return cls(
            node_id=str(value["node_id"]),
            node_type=str(value["node_type"]),
            subtype=str(value["subtype"]),
            features=[float(item) for item in value["features"]],
        )


@dataclass(slots=True)
class EdgeRecord:
    source: str
    target: str
    edge_type: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EdgeRecord":
        return cls(
            source=str(value["source"]),
            target=str(value["target"]),
            edge_type=str(value["edge_type"]),
        )


@dataclass(slots=True)
class GraphData:
    nodes: list[NodeRecord]
    edges: list[EdgeRecord]
    player_node_ids: list[str]
    value_descriptor: list[float]

    def __post_init__(self) -> None:
        if len(self.player_node_ids) == 0:
            raise ValueError("A graph must contain at least one player")
        if len(self.value_descriptor) != VALUE_DESCRIPTOR_DIM:
            raise ValueError(
                f"Expected {VALUE_DESCRIPTOR_DIM} value descriptor features, "
                f"got {len(self.value_descriptor)}"
            )
        node_ids = {node.node_id for node in self.nodes}
        if len(node_ids) != len(self.nodes):
            raise ValueError("Duplicate node IDs")
        for player_id in self.player_node_ids:
            if player_id not in node_ids:
                raise ValueError(f"Unknown player node {player_id}")
        for edge in self.edges:
            if edge.source not in node_ids or edge.target not in node_ids:
                raise ValueError(f"Edge references unknown endpoints: {edge}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
            "player_node_ids": list(self.player_node_ids),
            "value_descriptor": list(self.value_descriptor),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GraphData":
        return cls(
            nodes=[NodeRecord.from_dict(item) for item in value["nodes"]],
            edges=[EdgeRecord.from_dict(item) for item in value["edges"]],
            player_node_ids=[str(item) for item in value["player_node_ids"]],
            value_descriptor=[float(item) for item in value["value_descriptor"]],
        )


@dataclass(slots=True)
class GameRecord:
    game_id: str
    source_database: str
    split: str
    condition: dict[str, str]
    players: list[PlayerRecord]
    relation_edges: list[dict[str, str]]
    graph: GraphData
    base_share: list[float]
    shapley_share: list[float]
    revenue_pool: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        player_count = len(self.players)
        if player_count == 0:
            raise ValueError("A game must contain at least one player")
        if len(self.graph.player_node_ids) != player_count:
            raise ValueError("Graph and player table sizes differ")
        if len(self.base_share) != player_count:
            raise ValueError("base_share size mismatch")
        if len(self.shapley_share) != player_count:
            raise ValueError("shapley_share size mismatch")
        if any(item < -1e-12 for item in self.shapley_share):
            raise ValueError("Negative target shares are not supported")
        if abs(sum(self.shapley_share) - 1.0) > 1e-8:
            raise ValueError("Target shares must sum to one")
        if abs(sum(self.base_share) - 1.0) > 1e-8:
            raise ValueError("Base shares must sum to one")

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "source_database": self.source_database,
            "split": self.split,
            "condition": dict(self.condition),
            "players": [asdict(player) for player in self.players],
            "relation_edges": list(self.relation_edges),
            "graph": self.graph.to_dict(),
            "base_share": list(self.base_share),
            "shapley_share": list(self.shapley_share),
            "revenue_pool": float(self.revenue_pool),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GameRecord":
        return cls(
            game_id=str(value["game_id"]),
            source_database=str(value["source_database"]),
            split=str(value["split"]),
            condition={str(key): str(item) for key, item in value["condition"].items()},
            players=[PlayerRecord.from_dict(item) for item in value["players"]],
            relation_edges=list(value.get("relation_edges", [])),
            graph=GraphData.from_dict(value["graph"]),
            base_share=[float(item) for item in value["base_share"]],
            shapley_share=[float(item) for item in value["shapley_share"]],
            revenue_pool=float(value.get("revenue_pool", 1000.0)),
            metadata=dict(value.get("metadata", {})),
        )
