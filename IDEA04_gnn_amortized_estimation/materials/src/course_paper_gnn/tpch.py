from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import duckdb
import pandas as pd

from .constants import CONDITION_ORDER, OOD_CONDITION
from .graph import build_provenance_value_graph
from .schema import GameRecord, PlayerRecord


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    database_path: Path
    output_path: Path
    games_per_condition: int
    seed: int
    revenue_pool: float = 1000.0
    max_lineitems: int = 4
    max_nations: int = 2
    split_mode: str = "training"


def _candidate_query() -> str:
    return """
    WITH line_aggr AS (
        SELECT
            l.l_orderkey,
            COUNT(*) AS n_lines,
            COUNT(DISTINCT l.l_suppkey) AS n_suppliers,
            COUNT(DISTINCT s.s_nationkey) AS n_nations,
            SUM(l.l_quantity)::DOUBLE AS quantity_sum,
            SUM(l.l_extendedprice)::DOUBLE AS price_sum
        FROM lineitem AS l
        JOIN supplier AS s ON l.l_suppkey = s.s_suppkey
        GROUP BY l.l_orderkey
        HAVING COUNT(*) BETWEEN 3 AND 6
    )
    SELECT
        o.o_orderkey,
        o.o_custkey,
        o.o_totalprice::DOUBLE AS o_totalprice,
        o.o_orderpriority,
        c.c_acctbal::DOUBLE AS c_acctbal,
        c.c_mktsegment,
        a.n_lines,
        a.n_suppliers,
        a.n_nations,
        a.quantity_sum,
        a.price_sum
    FROM orders AS o
    JOIN customer AS c ON o.o_custkey = c.c_custkey
    JOIN line_aggr AS a ON o.o_orderkey = a.l_orderkey
    """


def load_candidates(database_path: str | Path) -> pd.DataFrame:
    con = duckdb.connect(str(database_path), read_only=True)
    try:
        frame = con.execute(_candidate_query()).fetchdf()
    finally:
        con.close()
    if frame.empty:
        raise RuntimeError("No TPC-H order contexts satisfy the minimum structure")
    frame["sharing"] = frame.apply(
        lambda row: "shared" if int(row["n_lines"]) > int(row["n_nations"]) else "independent",
        axis=1,
    )
    return frame


def select_contexts(
    candidates: pd.DataFrame,
    games_per_condition: int,
    seed: int,
) -> list[tuple[int, tuple[str, str, str]]]:
    if games_per_condition <= 0:
        raise ValueError("games_per_condition must be positive")

    rng = random.Random(seed)
    candidate_records = candidates.to_dict(orient="records")
    rng.shuffle(candidate_records)
    used: set[int] = set()
    selected: list[tuple[int, tuple[str, str, str]]] = []

    for condition in CONDITION_ORDER:
        sharing, _hierarchy, _value = condition
        matching = [
            row
            for row in candidate_records
            if int(row["o_orderkey"]) not in used
            and row["sharing"] == sharing
        ]
        if len(matching) < games_per_condition:
            raise RuntimeError(
                f"Not enough contexts for sharing={sharing}: "
                f"need {games_per_condition}, found {len(matching)}"
            )
        for row in matching[:games_per_condition]:
            order_key = int(row["o_orderkey"])
            selected.append((order_key, condition))
            used.add(order_key)
    return selected


def _split_for_condition(
    condition: tuple[str, str, str],
    count: int,
    index: int,
    split_mode: str,
) -> str:
    if split_mode == "external":
        return "scale_ood"
    if split_mode != "training":
        raise ValueError(f"Unknown split mode: {split_mode}")
    if condition == OOD_CONDITION:
        return "ood"
    if count >= 20:
        test_count = 10
        validation_count = 15
        train_count = count - test_count - validation_count
        if index < train_count:
            return "train"
        if index < train_count + validation_count:
            return "validation"
        return "in_distribution"
    train_count = max(1, count - 2 * max(0, count // 5))
    edge_count = max(0, count // 5)
    if index < train_count:
        return "train"
    if index < train_count + edge_count:
        return "validation"
    return "in_distribution"


def _context_rows(con: duckdb.DuckDBPyConnection, order_key: int) -> tuple[dict, list[dict]]:
    order_row = con.execute(
        """
        SELECT
            o.o_orderkey,
            o.o_custkey,
            o.o_totalprice::DOUBLE AS o_totalprice,
            o.o_orderpriority,
            c.c_acctbal::DOUBLE AS c_acctbal,
            c.c_mktsegment
        FROM orders AS o
        JOIN customer AS c ON o.o_custkey = c.c_custkey
        WHERE o.o_orderkey = ?
        """,
        [order_key],
    ).fetchdf()
    if len(order_row) != 1:
        raise RuntimeError(f"Expected one order/customer row for orderkey={order_key}")

    line_rows = con.execute(
        """
        SELECT
            l.l_orderkey,
            l.l_linenumber,
            l.l_suppkey,
            l.l_quantity::DOUBLE AS l_quantity,
            l.l_extendedprice::DOUBLE AS l_extendedprice,
            s.s_acctbal::DOUBLE AS s_acctbal,
            s.s_nationkey,
            n.n_name,
            n.n_regionkey
        FROM lineitem AS l
        JOIN supplier AS s ON l.l_suppkey = s.s_suppkey
        JOIN nation AS n ON s.s_nationkey = n.n_nationkey
        WHERE l.l_orderkey = ?
        ORDER BY l.l_linenumber
        LIMIT 6
        """,
        [order_key],
    ).fetchdf()
    if line_rows.empty:
        raise RuntimeError(f"No lineitems for orderkey={order_key}")
    return order_row.iloc[0].to_dict(), line_rows.to_dict(orient="records")


def _owner_customer(customer_key: int) -> str:
    return f"customer:{customer_key}"


def _owner_supplier(supplier_key: int) -> str:
    return f"supplier:{supplier_key}"


def _owner_nation(nation_key: int) -> str:
    return f"nation:{nation_key}"


def build_player_relations_from_rows(
    order: dict,
    lines: Sequence[dict],
    *,
    max_lineitems: int,
    max_nations: int,
) -> tuple[list[PlayerRecord], list[dict[str, str]]]:
    """Build player and relation-edge records from extracted SQL context rows."""

    order_key = int(order["o_orderkey"])
    customer_key = int(order["o_custkey"])
    players: list[PlayerRecord] = []
    relation_edges: list[dict[str, str]] = []

    player_index = len(players)
    order_id = f"o:{order_key}"
    players.append(
        PlayerRecord(
            player_id=order_id,
            player_index=player_index,
            relation="order",
            relation_key=str(order_key),
            owner_id=_owner_customer(customer_key),
            attributes={
                "total_price": float(order["o_totalprice"]),
                "priority_code": _priority_code(str(order["o_orderpriority"])),
            },
        )
    )

    player_index = len(players)
    customer_id = f"c:{customer_key}"
    players.append(
        PlayerRecord(
            player_id=customer_id,
            player_index=player_index,
            relation="customer",
            relation_key=str(customer_key),
            owner_id=_owner_customer(customer_key),
            attributes={
                "account_balance": float(order["c_acctbal"]),
                "segment_code": _segment_code(str(order["c_mktsegment"])),
            },
        )
    )
    relation_edges.append(
        {"source": order_id, "target": customer_id, "type": "order_customer"}
    )

    selected_lines = list(lines[:max_lineitems])
    supplier_rows: dict[int, dict] = {}
    for row in selected_lines:
        supplier_key = int(row["l_suppkey"])
        line_id = f"l:{order_key}:{int(row['l_linenumber'])}"
        supplier_id = f"s:{supplier_key}"
        nation_id = f"n:{int(row['s_nationkey'])}"
        player_index = len(players)
        players.append(
            PlayerRecord(
                player_id=line_id,
                player_index=player_index,
                relation="lineitem",
                relation_key=f"{order_key}:{int(row['l_linenumber'])}",
                owner_id=_owner_supplier(supplier_key),
                attributes={
                    "quantity": float(row["l_quantity"]),
                    "extended_price": float(row["l_extendedprice"]),
                },
                links={
                    "order_id": order_id,
                    "supplier_id": supplier_id,
                    "nation_id": nation_id,
                },
            )
        )
        supplier_rows[supplier_key] = row
        relation_edges.append(
            {"source": line_id, "target": order_id, "type": "lineitem_order"}
        )
        relation_edges.append(
            {
                "source": line_id,
                "target": supplier_id,
                "type": "lineitem_supplier",
            }
        )

    for supplier_key, row in supplier_rows.items():
        supplier_id = f"s:{supplier_key}"
        nation_id = f"n:{int(row['s_nationkey'])}"
        player_index = len(players)
        players.append(
            PlayerRecord(
                player_id=supplier_id,
                player_index=player_index,
                relation="supplier",
                relation_key=str(supplier_key),
                owner_id=_owner_supplier(supplier_key),
                attributes={"account_balance": float(row["s_acctbal"])},
                links={"nation_id": nation_id},
            )
        )
        relation_edges.append(
            {"source": supplier_id, "target": nation_id, "type": "supplier_nation"}
        )

    nation_keys = sorted(
        {int(row["s_nationkey"]) for row in supplier_rows.values()}
    )
    for nation_key in nation_keys[:max_nations]:
        nation_id = f"n:{nation_key}"
        row = next(
            item
            for item in supplier_rows.values()
            if int(item["s_nationkey"]) == nation_key
        )
        player_index = len(players)
        players.append(
            PlayerRecord(
                player_id=nation_id,
                player_index=player_index,
                relation="nation",
                relation_key=str(nation_key),
                owner_id=_owner_nation(nation_key),
                attributes={"region_key": float(row["n_regionkey"])},
            )
        )

    if len(players) > 12:
        raise RuntimeError(
            f"Context {order_key} produced {len(players)} players, expected <=12"
        )
    return players, relation_edges


def build_game_from_context(
    con: duckdb.DuckDBPyConnection,
    order_key: int,
    condition: tuple[str, str, str],
    split: str,
    database_label: str,
    revenue_pool: float,
    max_lineitems: int,
    max_nations: int,
) -> GameRecord:
    order, lines = _context_rows(con, order_key)
    players, relation_edges = build_player_relations_from_rows(
        order,
        lines,
        max_lineitems=max_lineitems,
        max_nations=max_nations,
    )
    selected_lines = lines[:max_lineitems]
    supplier_rows: dict[int, dict] = {}
    selected_line_ids: list[str] = []
    for row in selected_lines:
        supplier_key = int(row["l_suppkey"])
        line_id = f"l:{order_key}:{int(row['l_linenumber'])}"
        selected_line_ids.append(line_id)
        supplier_rows[supplier_key] = row

    nation_keys = sorted({int(row["s_nationkey"]) for row in supplier_rows.values()})

    base_weights = [g0_player_weight(player) for player in players]
    base_total = sum(base_weights)
    if base_total <= 0:
        raise RuntimeError("G0 base weights must be positive")
    base_share = [weight / base_total for weight in base_weights]

    values = [
        utility_from_mask(players, mask, condition[2]) for mask in range(1 << len(players))
    ]
    shapley = exact_shapley(values, len(players))
    total = sum(shapley)
    if total <= 1e-12:
        raise RuntimeError("Exact Shapley values sum to zero")
    shapley_share = [float(value / total) for value in shapley]

    graph = build_provenance_value_graph(
        game_id=f"{database_label}_{order_key}",
        players=players,
        relation_edges=relation_edges,
        condition={
            "source_sharing": condition[0],
            "hierarchy": condition[1],
            "value_function": condition[2],
        },
        value_type=condition[2],
    )

    return GameRecord(
        game_id=f"{database_label}_{order_key}",
        source_database=database_label,
        split=split,
        condition={
            "source_sharing": condition[0],
            "hierarchy": condition[1],
            "value_function": condition[2],
        },
        players=players,
        relation_edges=relation_edges,
        graph=graph,
        base_share=base_share,
        shapley_share=shapley_share,
        revenue_pool=float(revenue_pool),
        metadata={
            "order_key": order_key,
            "selected_lineitems": selected_line_ids,
            "n_players": len(players),
            "n_lineitems": len(selected_line_ids),
            "n_suppliers": len(supplier_rows),
            "n_nations": min(len(nation_keys), max_nations),
        },
    )


def g0_player_weight(player: PlayerRecord) -> float:
    if player.relation == "order":
        return 0.75
    if player.relation == "customer":
        return 0.75
    if player.relation == "lineitem":
        return 0.20 + 0.02 * float(player.attributes.get("quantity", 0.0))
    if player.relation == "supplier":
        return 0.15
    if player.relation == "nation":
        return 0.05
    raise KeyError(player.relation)


def utility_from_mask(players: Sequence[PlayerRecord], mask: int, value_type: str) -> float:
    active = [
        player for player in players if mask & (1 << player.player_index)
    ]
    by_relation: dict[str, list[PlayerRecord]] = {}
    for player in active:
        by_relation.setdefault(player.relation, []).append(player)

    order_on = bool(by_relation.get("order"))
    customer_on = bool(by_relation.get("customer"))
    lines = by_relation.get("lineitem", [])
    active_supplier_ids = {
        player.player_id for player in by_relation.get("supplier", [])
    }
    active_nation_ids = {player.player_id for player in by_relation.get("nation", [])}

    if value_type == "additive":
        return float(sum(g0_player_weight(player) for player in active))

    valid_order = order_on and customer_on
    if not valid_order or not lines:
        return 0.0

    line_count = len(lines)
    quantity_sum = sum(float(player.attributes["quantity"]) for player in lines)
    supplier_ids = {
        player.links["supplier_id"]
        for player in lines
        if player.links.get("supplier_id") in active_supplier_ids
    }
    nation_ids = {
        player.links["nation_id"]
        for player in lines
        if player.links.get("supplier_id") in active_supplier_ids
        and player.links.get("nation_id") in active_nation_ids
    }

    if value_type == "threshold":
        score = 0.5 * min(line_count, 2) + 0.02 * min(quantity_sum, 40.0)
        score += 0.5 if supplier_ids else 0.0
        score += 0.25 if len(nation_ids) >= 2 else 0.0
        return float(score)

    if value_type == "joint":
        base = 0.25 * min(line_count, 4) + 0.03 * min(quantity_sum, 80.0)
        base *= 1.0 + 0.15 * min(len(supplier_ids), 2)
        if len(nation_ids) >= 2:
            base += 0.20 * min(line_count, 4)
        return float(base)

    raise KeyError(value_type)


def exact_shapley(values: Sequence[float], n_players: int) -> list[float]:
    if len(values) != 1 << n_players:
        raise ValueError("Coalition value count does not match the player count")
    result = [0.0] * n_players
    for player in range(n_players):
        bit = 1 << player
        for mask in range(1 << n_players):
            if mask & bit:
                continue
            weight = 1.0 / (n_players * math.comb(n_players - 1, mask.bit_count()))
            result[player] += weight * (float(values[mask | bit]) - float(values[mask]))
    return result


def _priority_code(value: str) -> float:
    order = ("1-URGENT", "2-HIGH", "3-MEDIUM", "4-NOT SPECIFIED", "5-LOW")
    try:
        return float(order.index(value) + 1) / len(order)
    except ValueError:
        return 0.0


def _segment_code(value: str) -> float:
    order = ("AUTOMOBILE", "BUILDING", "FURNITURE", "MACHINERY", "HOUSEHOLD")
    try:
        return float(order.index(value) + 1) / len(order)
    except ValueError:
        return 0.0


def generate_games(config: GenerationConfig) -> list[GameRecord]:
    candidates = load_candidates(config.database_path)
    selected = select_contexts(candidates, config.games_per_condition, config.seed)
    database_label = config.database_path.stem.lower()
    games: list[GameRecord] = []
    con = duckdb.connect(str(config.database_path), read_only=True)
    try:
        for condition in CONDITION_ORDER:
            condition_rows = [
                (order_key, item_condition)
                for order_key, item_condition in selected
                if item_condition == condition
            ]
            for index, (order_key, item_condition) in enumerate(condition_rows):
                split = _split_for_condition(
                    condition,
                    len(condition_rows),
                    index,
                    config.split_mode,
                )
                games.append(
                    build_game_from_context(
                        con=con,
                        order_key=order_key,
                        condition=item_condition,
                        split=split,
                        database_label=database_label,
                        revenue_pool=config.revenue_pool,
                        max_lineitems=config.max_lineitems,
                        max_nations=config.max_nations,
                    )
                )
    finally:
        con.close()
    return games


def write_jsonl(games: Iterable[GameRecord], output_path: str | Path) -> None:
    import json

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing dataset: {path}")
    with path.open("w", encoding="utf-8") as handle:
        for game in games:
            handle.write(json.dumps(game.to_dict(), ensure_ascii=False, sort_keys=True))
            handle.write("\n")
