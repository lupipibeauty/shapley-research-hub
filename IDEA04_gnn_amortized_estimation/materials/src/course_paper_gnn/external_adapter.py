from __future__ import annotations

import csv
import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from .schema import EdgeRecord, GameRecord, GraphData, NodeRecord, PlayerRecord


D1P_RECORDS = (
    ("p1", "A1", "E1", True, "manufacturing"),
    ("p2", "A1", "E2", True, "service"),
    ("p3", "A2", "E1", True, "manufacturing"),
    ("p4", "A2", "E2", False, None),
    ("p5", "B1", "E1", True, "manufacturing"),
    ("p6", "B1", "E1", True, "service"),
    ("p7", "B1", "E2", True, "manufacturing"),
    ("p8", "B1", "E2", False, None),
    ("p9", "B2", "E1", True, "manufacturing"),
    ("p10", "B2", "E1", True, "service"),
    ("p11", "B2", "E2", True, "manufacturing"),
    ("p12", "B2", "E2", True, "service"),
)
D1P_PARENTS = {"A1": "A", "A2": "A", "B1": "B", "B2": "B"}
D1P_REPORT_NODES = ("COUNTRY", "A", "B", "A1", "A2", "B1", "B2")
D1P_COORD_SUBTYPES = (
    "coordinate_order_valid",
    "coordinate_line_count",
    "coordinate_quantity_sum",
    "coordinate_supplier_count",
    "coordinate_nation_count",
)


def _parse_number(value: str) -> float:
    text = value.strip()
    return float(Fraction(text)) if "/" in text else float(text)


def _node(
    node_id: str,
    node_type: str,
    subtype: str,
    features: list[float],
) -> NodeRecord:
    return NodeRecord(
        node_id=node_id,
        node_type=node_type,
        subtype=subtype,
        features=features,
    )


def _add_common_report_graph(
    *,
    nodes: list[NodeRecord],
    edges: list[EdgeRecord],
    witness_ids: list[str],
    coordinate_ids: list[str],
    factor_subtype: str,
    report_subtype: str,
    factor_features: list[float],
    report_features: list[float],
) -> None:
    factor_id = "factor:value"
    report_id = "report"
    nodes.append(
        _node(
            factor_id,
            "value_factor",
            factor_subtype,
            factor_features,
        )
    )
    nodes.append(_node(report_id, "report", report_subtype, report_features))
    for witness_id in witness_ids:
        for coordinate_id in coordinate_ids:
            edges.append(
                EdgeRecord(
                    source=witness_id,
                    target=coordinate_id,
                    edge_type="witness_supports_coordinate",
                )
            )
    for coordinate_id in coordinate_ids:
        edges.append(
            EdgeRecord(
                source=coordinate_id,
                target=factor_id,
                edge_type="coordinate_to_value_factor",
            )
        )
    edges.append(
        EdgeRecord(
            source=factor_id,
            target=report_id,
            edge_type="value_factor_to_report",
        )
    )


def _d1p_external_values(
    coalition_path: Path,
    allocation_path: Path,
    value_name: str,
) -> tuple[list[float], list[float]]:
    with coalition_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    value_column = {"V1": 3, "V2": 4}[value_name]
    values = [_parse_number(row[value_column]) for row in rows[1:]]

    target_by_player: dict[str, float] = {}
    with allocation_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in list(csv.reader(handle))[1:]:
            if row[0] == value_name and row[1].startswith("A0_"):
                target_by_player[row[2]] = _parse_number(row[3])
    if len(target_by_player) != 12:
        raise RuntimeError(
            f"Expected 12 exact D1-P allocations, got {len(target_by_player)}"
        )
    ordered = [
        target_by_player[f"t{index}"] for index in range(1, 13)
    ]
    total = sum(ordered)
    return values, [item / total for item in ordered]


def build_d1p_games(coalition_path: Path, allocation_path: Path) -> list[GameRecord]:
    games: list[GameRecord] = []
    for value_name in ("V1", "V2"):
        values, target = _d1p_external_values(
            coalition_path,
            allocation_path,
            value_name,
        )
        players = [
            PlayerRecord(
                player_id=player_id,
                player_index=index,
                relation="record_bundle",
                relation_key=player_id,
                owner_id=player_id,
                attributes={
                    "source": source,
                    "category_a": category_a,
                    "attribute_present": int(attribute_present),
                    "category_b": category_b or "",
                },
            )
            for index, (
                player_id,
                source,
                category_a,
                attribute_present,
                category_b,
            ) in enumerate(D1P_RECORDS)
        ]
        nodes: list[NodeRecord] = []
        edges: list[EdgeRecord] = []
        player_node_ids: list[str] = []
        witness_ids: list[str] = []
        source_code = {"A1": 0.0, "A2": 0.25, "B1": 0.75, "B2": 1.0}
        for player in players:
            source = str(player.attributes["source"])
            target_a = float(player.attributes["category_a"] == "E2")
            present = float(player.attributes["attribute_present"])
            target_b = float(player.attributes["category_b"] == "manufacturing")
            nodes.append(
                _node(
                    player.player_id,
                    "player",
                    "player_lineitem",
                    [
                        source_code[source],
                        target_a,
                        present,
                        target_b,
                        1.0,
                        present * target_b,
                        1.0,
                        1.0,
                    ],
                )
            )
            player_node_ids.append(player.player_id)
            witness_id = f"w:record:{player.player_id}"
            witness_ids.append(witness_id)
            nodes.append(
                _node(
                    witness_id,
                    "witness",
                    "witness_join",
                    [1.0, present, target_a, target_b, 0.0, 0.75, 1.0, 1.0],
                )
            )
            edges.append(
                EdgeRecord(
                    source=player.player_id,
                    target=witness_id,
                    edge_type="player_in_witness",
                )
            )

        coordinate_ids: list[str] = []
        for index, report_node in enumerate(D1P_REPORT_NODES):
            coordinate_id = f"coord:{report_node}"
            coordinate_ids.append(coordinate_id)
            nodes.append(
                _node(
                    coordinate_id,
                    "coordinate",
                    D1P_COORD_SUBTYPES[index % len(D1P_COORD_SUBTYPES)],
                    [
                        index / max(1, len(D1P_REPORT_NODES) - 1),
                        1.0,
                        0.0,
                        0.0,
                        0.0,
                        0.5,
                        0.0,
                        1.0,
                    ],
                )
            )

        # Each record witness reaches its leaf, parent, and root report nodes.
        for player, witness_id in zip(players, witness_ids):
            leaf = str(player.attributes["source"])
            for report_node in (leaf, D1P_PARENTS[leaf], "COUNTRY"):
                edges.append(
                    EdgeRecord(
                        source=witness_id,
                        target=f"coord:{report_node}",
                        edge_type="witness_supports_coordinate",
                    )
                )
        # The helper adds the remaining report connectivity.
        for coordinate_id in coordinate_ids:
            edges.append(
                EdgeRecord(
                    source=coordinate_id,
                    target="factor:value",
                    edge_type="coordinate_to_value_factor",
                )
            )
        nodes.append(
            _node(
                "factor:value",
                "value_factor",
                "value_joint",
                [1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 1.0],
            )
        )
        nodes.append(
            _node(
                "report",
                "report",
                "report",
                [1.0, 1.0, 0.75, 1.0, 0.0, 1.0, 0.0, 1.0],
            )
        )
        edges.append(
            EdgeRecord(
                source="factor:value",
                target="report",
                edge_type="value_factor_to_report",
            )
        )
        graph = GraphData(
            nodes=nodes,
            edges=edges,
            player_node_ids=player_node_ids,
            value_descriptor=[
                1.0,
                0.0,
                0.0,
                0.0,
                1.0,
                1.0,
                0.5,
                0.5,
                0.5,
                0.7,
                0.5,
                0.5,
                0.5,
                0.5,
            ],
        )
        games.append(
            GameRecord(
                game_id=f"d1p_{value_name.lower()}",
                source_database="D1-P",
                split="external_zero_shot",
                condition={
                    "source_sharing": "shared",
                    "hierarchy": "tree",
                    "value_function": "joint",
                },
                players=players,
                relation_edges=[],
                graph=graph,
                base_share=[1.0 / len(players)] * len(players),
                shapley_share=target,
                revenue_pool=100.0,
                metadata={
                    "adapter": "d1p_record_bundle_to_rpv_v1",
                    "value_name": value_name,
                    "coalition_values": len(values),
                    "target_source": "A0_standard_exact_shapley",
                },
            )
        )
    return games


def _read_p3_targets(path: Path) -> dict[str, list[float]]:
    result: dict[str, dict[int, float]] = defaultdict(dict)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            result[row["game_id"]][int(row["player_index"])] = float(
                row["shapley_decimal"]
            )
    normalized: dict[str, list[float]] = {}
    for game_id, values in result.items():
        ordered = [values[index] for index in sorted(values)]
        total = sum(ordered)
        normalized[game_id] = [item / total for item in ordered]
    return normalized


def build_p3_games(
    fixture_path: Path,
    truth_path: Path,
) -> list[GameRecord]:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    truth = _read_p3_targets(truth_path)
    records: list[dict[str, Any]] = []
    records.extend(
        {**record, "relation": "entity"} for record in fixture["entities"]
    )
    records.extend(
        {**record, "relation": "link"} for record in fixture["links"]
    )
    records.extend(
        {**record, "relation": "attribute"} for record in fixture["attributes"]
    )
    records.sort(key=lambda item: int(item["player_index"]))
    owner_map = fixture["owner_maps"]["OwnerMap-B"]
    players = [
        PlayerRecord(
            player_id=str(record["player_id"]),
            player_index=int(record["player_index"]),
            relation=str(record["relation"]),
            relation_key=str(record["record_id"]),
            owner_id=str(owner_map[str(record["player_id"])]),
            attributes={
                "group_id": str(record.get("group_id", "")),
                "source_id": str(record.get("source_id", "")),
                "valid": int(bool(record.get("valid", True))),
                "value": float(record.get("value", 0.0) or 0.0),
                "entity_id": str(record.get("entity_id", "")),
                "attribute_id": str(record.get("attribute_id", "")),
            },
        )
        for record in records
    ]

    attribute_player = {
        str(record["attribute_id"]): str(record["player_id"])
        for record in fixture["attributes"]
    }
    edges_by_entity: dict[str, list[str]] = defaultdict(list)
    for record in fixture["links"]:
        edges_by_entity[str(record["entity_id"])].append(str(record["player_id"]))
        edges_by_entity[str(record["entity_id"])].append(
            attribute_player[str(record["attribute_id"])]
        )

    games: list[GameRecord] = []
    for game_id in ("G0", "G1"):
        nodes: list[NodeRecord] = []
        edges: list[EdgeRecord] = []
        player_node_ids: list[str] = []
        witness_ids: list[str] = []
        player_subtype = {
            "entity": "player_order",
            "link": "player_lineitem",
            "attribute": "player_supplier",
        }
        for player in players:
            relation = player.relation
            validity = float(player.attributes["valid"])
            group_b = float(player.attributes["group_id"] == "B")
            nodes.append(
                _node(
                    player.player_id,
                    "player",
                    player_subtype[relation],
                    [
                        1.0 if relation == "entity" else 0.0,
                        1.0 if relation == "link" else 0.0,
                        1.0 if relation == "attribute" else 0.0,
                        validity,
                        group_b,
                        float(player.attributes["value"]),
                        1.0,
                        1.0,
                    ],
                )
            )
            player_node_ids.append(player.player_id)

        for entity_id in sorted(edges_by_entity):
            witness_id = f"w:entity:{entity_id}"
            witness_ids.append(witness_id)
            members = [
                player.player_id
                for player in players
                if player.player_id == f"E{entity_id[1:]}"
            ] + edges_by_entity[entity_id]
            group_id = next(
                player.attributes["group_id"]
                for player in players
                if player.relation == "entity"
                and player.attributes["entity_id"] == entity_id
            )
            nodes.append(
                _node(
                    witness_id,
                    "witness",
                    "witness_join",
                    [
                        min(len(members) / 6.0, 1.0),
                        1.0,
                        min(len(edges_by_entity[entity_id]) / 3.0, 1.0),
                        0.0,
                        float(group_id == "B"),
                        1.0,
                        1.0,
                        1.0,
                    ],
                )
            )
            for member_id in members:
                edges.append(
                    EdgeRecord(
                        source=member_id,
                        target=witness_id,
                        edge_type="player_in_witness",
                    )
                )

        coordinate_ids = ["coord:group_A", "coord:group_B"]
        for index, coordinate_id in enumerate(coordinate_ids):
            nodes.append(
                _node(
                    coordinate_id,
                    "coordinate",
                    "coordinate_line_count" if index else "coordinate_order_valid",
                    [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 1.0],
                )
            )
        for witness_id in witness_ids:
            component = witness_id.rsplit(":", 1)[1]
            group_id = next(
                player.attributes["group_id"]
                for player in players
                if player.relation == "entity"
                and player.attributes["entity_id"] == component
            )
            edges.append(
                EdgeRecord(
                    source=witness_id,
                    target=f"coord:group_{group_id}",
                    edge_type="witness_supports_coordinate",
                )
            )
        for coordinate_id in coordinate_ids:
            edges.append(
                EdgeRecord(
                    source=coordinate_id,
                    target="factor:value",
                    edge_type="coordinate_to_value_factor",
                )
            )
        nodes.append(
            _node(
                "factor:value",
                "value_factor",
                "value_additive" if game_id == "G0" else "value_threshold",
                [1.0, 0.0, float(game_id == "G0"), float(game_id == "G1"), 0.0, 1.0, 0.0, 1.0],
            )
        )
        nodes.append(
            _node(
                "report",
                "report",
                "report",
                [1.0, 0.5, 0.5, 1.0, 0.5, 1.0, 0.0, 1.0],
            )
        )
        edges.append(
            EdgeRecord(
                source="factor:value",
                target="report",
                edge_type="value_factor_to_report",
            )
        )
        graph = GraphData(
            nodes=nodes,
            edges=edges,
            player_node_ids=player_node_ids,
            value_descriptor=[
                1.0,
                0.0,
                float(game_id == "G0"),
                float(game_id == "G1"),
                0.0,
                0.5,
                0.5,
                0.5,
                0.5,
                0.5,
                0.5,
                0.5,
                0.5,
                0.5,
            ],
        )
        target = truth[game_id]
        games.append(
            GameRecord(
                game_id=f"p3_{game_id.lower()}",
                source_database="P3-0",
                split="external_zero_shot",
                condition={
                    "source_sharing": "shared",
                    "hierarchy": "cross",
                    "value_function": "additive" if game_id == "G0" else "threshold",
                },
                players=players,
                relation_edges=[],
                graph=graph,
                base_share=[1.0 / len(players)] * len(players),
                shapley_share=target,
                revenue_pool=1000.0,
                metadata={
                    "adapter": "p3_physical_fact_to_rpv_v1",
                    "value_name": game_id,
                    "coalition_values": 8192,
                    "target_source": "record_shapley.csv exact",
                },
            )
        )
    return games
