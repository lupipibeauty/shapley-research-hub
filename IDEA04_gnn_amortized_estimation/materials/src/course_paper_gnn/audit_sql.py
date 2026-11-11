from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import duckdb

from .data import load_games
from .tpch import utility_from_mask


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit provenance-state utilities against context SQL"
    )
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--games", type=int, default=5)
    parser.add_argument("--masks", default="all", help="'all' or an integer sample size")
    parser.add_argument("--tolerance", type=float, default=1e-10)
    parser.add_argument("--seed", type=int, default=20261107)
    return parser.parse_args()


def _mask_list(n_players: int, specification: str, seed: int) -> list[int]:
    total = 1 << n_players
    if specification == "all":
        return list(range(total))
    sample_size = int(specification)
    if sample_size <= 0 or sample_size > total:
        raise ValueError("mask sample size must be between 1 and 2^players")
    rng = random.Random(seed)
    required = [0, total - 1]
    remaining = [mask for mask in range(total) if mask not in required]
    return required + rng.sample(remaining, min(sample_size - len(required), len(remaining)))


def _select_games(games: list, count: int, seed: int) -> list:
    if count <= 0:
        raise ValueError("games must be positive")
    rng = random.Random(seed)
    grouped: dict[str, list] = {}
    for game in games:
        key = "/".join(game.condition.values())
        grouped.setdefault(key, []).append(game)
    for values in grouped.values():
        rng.shuffle(values)
    selected = []
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


def _prepare_context(con: duckdb.DuckDBPyConnection, game: object) -> None:
    order_key = int(game.metadata["order_key"])
    order_player = next(player for player in game.players if player.relation == "order")
    customer_player = next(player for player in game.players if player.relation == "customer")
    line_players = [player for player in game.players if player.relation == "lineitem"]
    supplier_keys = [
        int(player.relation_key)
        for player in game.players
        if player.relation == "supplier"
    ]
    nation_keys = [
        int(player.relation_key)
        for player in game.players
        if player.relation == "nation"
    ]
    line_numbers = [
        int(player.relation_key.split(":")[1]) for player in line_players
    ]

    con.execute("DROP TABLE IF EXISTS audit_active")
    con.execute("DROP TABLE IF EXISTS audit_orders")
    con.execute("DROP TABLE IF EXISTS audit_customer")
    con.execute("DROP TABLE IF EXISTS audit_lineitem")
    con.execute("DROP TABLE IF EXISTS audit_supplier")
    con.execute("DROP TABLE IF EXISTS audit_nation")
    con.execute("CREATE TEMP TABLE audit_active(player_id VARCHAR)")
    con.execute(
        """
        CREATE TEMP TABLE audit_orders AS
        SELECT o_orderkey, o_totalprice
        FROM orders
        WHERE o_orderkey = ?
        """,
        [order_key],
    )
    con.execute(
        """
        CREATE TEMP TABLE audit_customer AS
        SELECT c_custkey, c_acctbal
        FROM customer
        WHERE c_custkey = ?
        """,
        [int(customer_player.relation_key)],
    )
    con.execute(
        """
        CREATE TEMP TABLE audit_lineitem AS
        SELECT l_orderkey, l_linenumber, l_suppkey, l_quantity, l_extendedprice
        FROM lineitem
        WHERE l_orderkey = ?
          AND l_linenumber IN (SELECT * FROM UNNEST(?::BIGINT[]))
        """,
        [order_key, line_numbers],
    )
    con.execute(
        """
        CREATE TEMP TABLE audit_supplier AS
        SELECT s_suppkey, s_nationkey, s_acctbal
        FROM supplier
        WHERE s_suppkey IN (SELECT * FROM UNNEST(?::BIGINT[]))
        """,
        [supplier_keys],
    )
    con.execute(
        """
        CREATE TEMP TABLE audit_nation AS
        SELECT n_nationkey, n_regionkey
        FROM nation
        WHERE n_nationkey IN (SELECT * FROM UNNEST(?::INTEGER[]))
        """,
        [nation_keys],
    )


def _sql_utility(con: duckdb.DuckDBPyConnection, value_type: str) -> float:
    additive_sql = """
        (SELECT 0.75 * COUNT(*) FROM audit_orders)
        + (SELECT 0.75 * COUNT(*) FROM audit_customer)
        + (
            SELECT COALESCE(SUM(0.20 + 0.02 * l_quantity), 0)
            FROM audit_lineitem l
            WHERE 'l:' || l_orderkey || ':' || l_linenumber
                  IN (SELECT player_id FROM audit_active)
          )
        + (
            SELECT COALESCE(0.15 * COUNT(*), 0)
            FROM audit_supplier s
            WHERE 's:' || s_suppkey IN (SELECT player_id FROM audit_active)
          )
        + (
            SELECT COALESCE(0.05 * COUNT(*), 0)
            FROM audit_nation n
            WHERE 'n:' || n_nationkey IN (SELECT player_id FROM audit_active)
          )
    """
    if value_type == "additive":
        value = con.execute(
            f"""
            SELECT
                (SELECT 0.75 * COUNT(*) FROM audit_orders o
                 WHERE 'o:' || o.o_orderkey IN (SELECT player_id FROM audit_active))
                + (SELECT 0.75 * COUNT(*) FROM audit_customer c
                   WHERE 'c:' || c.c_custkey IN (SELECT player_id FROM audit_active))
                + (SELECT {additive_sql} - 0.75 * (SELECT COUNT(*) FROM audit_orders)
                   - 0.75 * (SELECT COUNT(*) FROM audit_customer))
            """
        ).fetchone()[0]
        return float(value)

    metrics = con.execute(
        """
        WITH
        active_order AS (
            SELECT * FROM audit_orders o
            WHERE 'o:' || o.o_orderkey IN (SELECT player_id FROM audit_active)
        ),
        active_customer AS (
            SELECT * FROM audit_customer c
            WHERE 'c:' || c.c_custkey IN (SELECT player_id FROM audit_active)
        ),
        active_line AS (
            SELECT * FROM audit_lineitem l
            WHERE 'l:' || l.l_orderkey || ':' || l.l_linenumber
                  IN (SELECT player_id FROM audit_active)
        ),
        active_supplier AS (
            SELECT * FROM audit_supplier s
            WHERE 's:' || s.s_suppkey IN (SELECT player_id FROM audit_active)
        ),
        active_nation AS (
            SELECT * FROM audit_nation n
            WHERE 'n:' || n.n_nationkey IN (SELECT player_id FROM audit_active)
        )
        SELECT
            EXISTS(SELECT 1 FROM active_order)
            AND EXISTS(SELECT 1 FROM active_customer) AS valid_order,
            (SELECT COUNT(*) FROM active_line) AS line_count,
            (SELECT COALESCE(SUM(l_quantity), 0) FROM active_line) AS quantity_sum,
            (
                SELECT COUNT(DISTINCT l_suppkey)
                FROM active_line l
                WHERE l_suppkey IN (SELECT s_suppkey FROM active_supplier)
            ) AS supplier_count,
            (
                SELECT COUNT(DISTINCT s_nationkey)
                FROM active_line l
                JOIN active_supplier s ON l_suppkey = s_suppkey
                WHERE s_nationkey IN (SELECT n_nationkey FROM active_nation)
            ) AS nation_count
        """
    ).fetchone()
    valid_order, line_count, quantity_sum, supplier_count, nation_count = metrics
    if not valid_order or int(line_count) == 0:
        return 0.0
    line_count = int(line_count)
    quantity_sum = float(quantity_sum)
    supplier_count = int(supplier_count)
    nation_count = int(nation_count)
    if value_type == "threshold":
        return float(
            0.5 * min(line_count, 2)
            + 0.02 * min(quantity_sum, 40.0)
            + (0.5 if supplier_count > 0 else 0.0)
            + (0.25 if nation_count >= 2 else 0.0)
        )
    if value_type == "joint":
        value = 0.25 * min(line_count, 4) + 0.03 * min(quantity_sum, 80.0)
        value *= 1.0 + 0.15 * min(supplier_count, 2)
        if nation_count >= 2:
            value += 0.20 * min(line_count, 4)
        return float(value)
    raise KeyError(value_type)


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite audit directory: {args.output}")
    args.output.mkdir(parents=True)
    games = _select_games(load_games(args.data), args.games, args.seed)
    connection = duckdb.connect(str(args.db), read_only=True)
    rows: list[dict] = []
    try:
        for game in games:
            _prepare_context(connection, game)
            masks = _mask_list(
                len(game.players),
                args.masks,
                seed=args.seed + game.metadata["order_key"],
            )
            value_type = game.condition["value_function"]
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
                sql_value = _sql_utility(connection, value_type)
                python_value = utility_from_mask(game.players, mask, value_type)
                rows.append(
                    {
                        "game_id": game.game_id,
                        "mask": mask,
                        "value_function": value_type,
                        "python_utility": python_value,
                        "sql_utility": sql_value,
                        "absolute_error": abs(python_value - sql_value),
                    }
                )
    finally:
        connection.close()

    with (args.output / "per_mask_audit.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    mismatches = [row for row in rows if row["absolute_error"] > args.tolerance]
    summary = {
        "status": "PASS" if not mismatches else "FAIL",
        "games": len(games),
        "masks_checked": len(rows),
        "max_absolute_error": max(row["absolute_error"] for row in rows),
        "mismatches": len(mismatches),
        "tolerance": args.tolerance,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
