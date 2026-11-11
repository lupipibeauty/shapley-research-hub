from __future__ import annotations

from collections import Counter
from typing import Sequence

from .schema import EdgeRecord, GraphData, NodeRecord, PlayerRecord


COORDINATES = (
    ("coordinate_order_valid", 0.20),
    ("coordinate_line_count", 0.25),
    ("coordinate_quantity_sum", 0.25),
    ("coordinate_supplier_count", 0.15),
    ("coordinate_nation_count", 0.15),
)


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _player_features(
    player: PlayerRecord,
    repetition: int,
    max_quantity: float,
    max_money: float,
) -> list[float]:
    quantity = float(player.attributes.get("quantity", 0.0))
    money = float(
        player.attributes.get(
            "extended_price",
            player.attributes.get(
                "total_price",
                player.attributes.get("account_balance", 0.0),
            ),
        )
    )
    amount = money / max_money if max_money > 0 else 0.0
    quantity_scaled = quantity / max_quantity if max_quantity > 0 else 0.0
    priority = float(player.attributes.get("priority_code", 0.0))
    segment = float(player.attributes.get("segment_code", 0.0))
    repetition_scaled = min(repetition, 4) / 4.0
    relation_depth = {
        "order": 0.2,
        "customer": 0.4,
        "lineitem": 0.6,
        "supplier": 0.8,
        "nation": 1.0,
    }[player.relation]
    return [
        _clamp(quantity_scaled),
        _clamp(amount),
        _clamp(repetition_scaled, 0.0, 1.0),
        _clamp(priority, 0.0, 1.0),
        _clamp(segment, 0.0, 1.0),
        0.0,
        relation_depth,
        1.0 if repetition > 1 else 0.0,
    ]


def build_provenance_value_graph(
    game_id: str,
    players: Sequence[PlayerRecord],
    relation_edges: Sequence[dict[str, str]],
    condition: dict[str, str],
    value_type: str,
) -> GraphData:
    del game_id  # Kept in the function signature to make graph construction explicit.
    if value_type not in {"additive", "threshold", "joint"}:
        raise ValueError(f"Unknown value type: {value_type}")

    by_id = {player.player_id: player for player in players}
    players_by_relation: dict[str, list[PlayerRecord]] = {}
    for player in players:
        players_by_relation.setdefault(player.relation, []).append(player)

    order = players_by_relation.get("order", [])
    if len(order) != 1:
        raise ValueError("Each game must contain exactly one order player")
    order_player = order[0]
    customer_players = players_by_relation.get("customer", [])
    if len(customer_players) != 1:
        raise ValueError("Each game must contain exactly one customer player")
    customer_player = customer_players[0]

    line_players = players_by_relation.get("lineitem", [])
    supplier_ids = {
        player.player_id for player in players_by_relation.get("supplier", [])
    }
    nation_ids = {player.player_id for player in players_by_relation.get("nation", [])}

    max_quantity = max(
        (float(item.attributes.get("quantity", 0.0)) for item in line_players),
        default=1.0,
    )
    max_money = max(
        max(
            float(
                item.attributes.get(
                    "extended_price",
                    item.attributes.get(
                        "total_price",
                        item.attributes.get("account_balance", 0.0),
                    ),
                )
            )
            for item in players
        ),
        1.0,
    )
    full_quantity = sum(
        float(player.attributes.get("quantity", 0.0)) for player in line_players
    )
    repetition = Counter()
    for edge in relation_edges:
        repetition[edge["source"]] += 1
        repetition[edge["target"]] += 1
    shared_ids = {
        player_id for player_id, count in repetition.items() if count > 1
    }

    nodes: list[NodeRecord] = []
    edges: list[EdgeRecord] = []
    player_node_ids: list[str] = []
    for player in players:
        subtype = f"player_{player.relation}"
        nodes.append(
            NodeRecord(
                node_id=player.player_id,
                node_type="player",
                subtype=subtype,
                features=_player_features(
                    player,
                    repetition=repetition[player.player_id],
                    max_quantity=max_quantity,
                    max_money=max_money,
                )
                + [],
            )
        )
        player_node_ids.append(player.player_id)

    def add_witness(
        witness_id: str,
        member_ids: Sequence[str],
        *,
        shared: bool,
    ) -> None:
        nodes.append(
            NodeRecord(
                node_id=witness_id,
                node_type="witness",
                subtype="witness_join",
                features=[
                    min(len([item for item in member_ids if item in by_id]) / 6.0, 1.0),
                    1.0 if shared else 0.0,
                    min(len(member_ids) / 6.0, 1.0),
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    1.0 if shared else 0.0,
                ],
            )
        )
        for member_id in member_ids:
            if member_id not in by_id:
                continue
            edges.append(
                EdgeRecord(
                    source=member_id,
                    target=witness_id,
                    edge_type="player_in_witness",
                )
            )

    order_witness = f"w:order:{order_player.relation_key}"
    add_witness(
        order_witness,
        [order_player.player_id, customer_player.player_id],
        shared=False,
    )

    line_witnesses: list[str] = []
    for index, line in enumerate(line_players):
        supplier_id = line.links.get("supplier_id", "")
        nation_id = line.links.get("nation_id", "")
        members = [order_player.player_id, customer_player.player_id, line.player_id]
        if supplier_id in supplier_ids:
            members.append(supplier_id)
        if nation_id in nation_ids:
            members.append(nation_id)
        witness_id = f"w:line:{index}"
        is_shared = line.player_id in shared_ids or supplier_id in shared_ids or nation_id in shared_ids
        add_witness(witness_id, members, shared=is_shared)
        line_witnesses.append(witness_id)

    coordinate_nodes: dict[str, str] = {}
    for subtype, weight in COORDINATES:
        node_id = f"coord:{subtype}"
        coordinate_nodes[subtype] = node_id
        nodes.append(
            NodeRecord(
                node_id=node_id,
                node_type="coordinate",
                subtype=subtype,
                features=[
                    weight,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    weight,
                    0.0,
                    0.0,
                ],
            )
        )

    edges.append(
        EdgeRecord(
            source=order_witness,
            target=coordinate_nodes["coordinate_order_valid"],
            edge_type="witness_supports_coordinate",
        )
    )
    for witness_id in line_witnesses:
        for subtype in (
            "coordinate_line_count",
            "coordinate_quantity_sum",
            "coordinate_supplier_count",
            "coordinate_nation_count",
        ):
            edges.append(
                EdgeRecord(
                    source=witness_id,
                    target=coordinate_nodes[subtype],
                    edge_type="witness_supports_coordinate",
                )
            )

    factor_subtype = {
        "additive": "value_additive",
        "threshold": "value_threshold",
        "joint": "value_joint",
    }[value_type]
    factor_id = f"factor:{value_type}"
    nodes.append(
        NodeRecord(
            node_id=factor_id,
            node_type="value_factor",
            subtype=factor_subtype,
            features=[
                1.0,
                0.0,
                0.0,
                min(len(line_players) / 4.0, 1.0),
                1.0 if condition["source_sharing"] == "shared" else 0.0,
                1.0,
                1.0 if condition["hierarchy"] == "cross" else 0.0,
                1.0 if value_type == "joint" else 0.0,
            ],
        )
    )
    for node_id in coordinate_nodes.values():
        edges.append(
            EdgeRecord(
                source=node_id,
                target=factor_id,
                edge_type="coordinate_to_value_factor",
            )
        )

    report_id = "report"
    nodes.append(
        NodeRecord(
            node_id=report_id,
            node_type="report",
            subtype="report",
            features=[
                1.0,
                float(order_player.attributes.get("total_price", 0.0)) / max_money,
                float(len(line_players)) / 4.0,
                0.0,
                0.0,
                1.0,
                0.0,
                1.0 if condition["hierarchy"] == "cross" else 0.0,
            ],
        )
    )
    edges.append(
        EdgeRecord(
            source=factor_id,
            target=report_id,
            edge_type="value_factor_to_report",
        )
    )

    degree = Counter()
    for edge in edges:
        degree[edge.source] += 1
        degree[edge.target] += 1
    for node in nodes:
        node.features[5] = min(degree[node.node_id] / 12.0, 1.0)

    value_descriptor = [
        1.0 if condition["source_sharing"] == "shared" else 0.0,
        1.0 if condition["hierarchy"] == "cross" else 0.0,
        1.0 if value_type == "additive" else 0.0,
        1.0 if value_type == "threshold" else 0.0,
        1.0 if value_type == "joint" else 0.0,
        len(players) / 12.0,
        len(line_players) / 4.0,
        len(supplier_ids) / 4.0,
        len(nation_ids) / 2.0,
        _clamp(full_quantity / 80.0),
        _clamp(float(order_player.attributes.get("total_price", 0.0)) / max_money),
        _clamp(
            full_quantity / max(len(line_players), 1) / 50.0,
            0.0,
            1.0,
        ),
        _clamp(float(order_player.attributes.get("priority_code", 0.0)), 0.0, 1.0),
        _clamp(float(customer_player.attributes.get("segment_code", 0.0)), 0.0, 1.0),
    ]
    return GraphData(
        nodes=nodes,
        edges=edges,
        player_node_ids=player_node_ids,
        value_descriptor=value_descriptor,
    )
