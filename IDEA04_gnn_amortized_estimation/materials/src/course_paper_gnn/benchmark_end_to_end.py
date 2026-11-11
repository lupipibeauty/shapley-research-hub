from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import time
from pathlib import Path

import duckdb

from .audit_sql import _prepare_context, _select_games, _sql_utility
from .data import collate_games, load_games, split_games
from .graph import build_provenance_value_graph
from .metrics import owner_shares
from .model import build_model
from .schema import GameRecord
from .tpch import (
    _context_rows,
    build_player_relations_from_rows,
    g0_player_weight,
)


PLAN_SQL = (
    """
    EXPLAIN
    SELECT
        o.o_orderkey,
        o.o_custkey,
        o.o_totalprice::DOUBLE,
        o.o_orderpriority,
        c.c_acctbal::DOUBLE,
        c.c_mktsegment
    FROM orders AS o
    JOIN customer AS c ON o.o_custkey = c.c_custkey
    WHERE o.o_orderkey = ?
    """,
    """
    EXPLAIN
    SELECT
        l.l_orderkey,
        l.l_linenumber,
        l.l_suppkey,
        l.l_quantity::DOUBLE,
        l.l_extendedprice::DOUBLE,
        s.s_acctbal::DOUBLE,
        s.s_nationkey,
        n.n_nationkey,
        n.n_regionkey
    FROM lineitem AS l
    JOIN supplier AS s ON l.l_suppkey = s.s_suppkey
    JOIN nation AS n ON s.s_nationkey = n.n_nationkey
    WHERE l.l_orderkey = ?
    ORDER BY l.l_linenumber
    LIMIT 6
    """,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark SQL lineage, graph, model, and MC stages separately"
    )
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--split", default="in_distribution")
    parser.add_argument("--games", type=int, default=10)
    parser.add_argument("--budgets", default="64,256,1024")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261114)
    return parser.parse_args()


def _p95(values: list[float]) -> float:
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]


def _measure(callable_: object, repeats: int) -> float:
    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        callable_()
        samples.append(time.perf_counter() - started)
    return statistics.median(samples) * 1000.0


def _load_model(checkpoint_path: Path) -> object:
    import torch

    checkpoint = torch.load(
        checkpoint_path,
        map_location="cpu",
        weights_only=False,
    )
    training_args = checkpoint["args"]
    model = build_model(
        checkpoint["model_name"],
        hidden_dim=int(training_args["hidden_dim"]),
        num_layers=int(training_args["num_layers"]),
        dropout=float(training_args["dropout"]),
        use_edges=not bool(training_args.get("no_edges", False)),
        use_anchor=not bool(training_args["no_anchor"]),
        use_zero_mask=not bool(training_args["no_zero_mask"]),
        use_simplex=not bool(training_args["no_simplex"]),
    )
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model


def _permutation_masks(
    player_count: int,
    *,
    seed: int,
    nominal_steps: int,
) -> list[int]:
    rng = random.Random(seed)
    masks: list[int] = []
    permutation_count = max(1, nominal_steps // player_count)
    for _ in range(permutation_count):
        order = list(range(player_count))
        rng.shuffle(order)
        mask = 0
        masks.append(mask)
        for player_index in order:
            mask |= 1 << player_index
            masks.append(mask)
    return masks


def _set_active(connection: duckdb.DuckDBPyConnection, game: object, mask: int) -> None:
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


def _median_summary(rows: list[dict], stage: str, value_field: str) -> dict:
    values = [float(row[value_field]) for row in rows]
    return {
        "stage": stage,
        "games": len(values),
        "median_ms": statistics.median(values),
        "mean_ms": statistics.mean(values),
        "p95_ms": _p95(values),
    }


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite output directory: {args.output}")
    games = _select_games(
        split_games(load_games(args.data), args.split),
        args.games,
        args.seed,
    )
    budgets = [int(item) for item in args.budgets.split(",")]
    model = _load_model(args.checkpoint)
    connection = duckdb.connect(str(args.db), read_only=True)
    rows: list[dict] = []
    try:
        for game in games:
            order_key = int(game.metadata["order_key"])

            def plan() -> None:
                for query in PLAN_SQL:
                    connection.execute(query, [order_key]).fetchall()

            plan_ms = _measure(plan, args.repeats)

            def extract_lineage() -> None:
                _prepare_context(connection, game)
                order, lines = _context_rows(connection, order_key)
                build_player_relations_from_rows(
                    order,
                    lines,
                    max_lineitems=4,
                    max_nations=2,
                )

            lineage_ms = _measure(extract_lineage, args.repeats)
            _prepare_context(connection, game)
            order, lines = _context_rows(connection, order_key)
            players, relation_edges = build_player_relations_from_rows(
                order,
                lines,
                max_lineitems=4,
                max_nations=2,
            )
            if len(players) != len(game.players):
                raise RuntimeError(
                    f"Player mismatch after SQL extraction: {game.game_id}"
                )

            def build_graph() -> object:
                return build_provenance_value_graph(
                    game_id=game.game_id,
                    players=players,
                    relation_edges=relation_edges,
                    condition=game.condition,
                    value_type=game.condition["value_function"],
                )

            graph_ms = _measure(build_graph, args.repeats)
            graph = build_graph()
            base_weights = [g0_player_weight(player) for player in players]
            total_weight = sum(base_weights)
            base_share = [weight / total_weight for weight in base_weights]
            inference_game = GameRecord(
                game_id=game.game_id,
                source_database=game.source_database,
                split=game.split,
                condition=dict(game.condition),
                players=players,
                relation_edges=relation_edges,
                graph=graph,
                base_share=base_share,
                shapley_share=list(game.shapley_share),
                revenue_pool=game.revenue_pool,
                metadata=dict(game.metadata),
            )

            def collate() -> object:
                return collate_games([inference_game])

            collate_ms = _measure(collate, args.repeats)
            batch = collate()
            import torch

            with torch.no_grad():
                model(batch)
                forward_samples = []
                for _ in range(args.repeats):
                    started = time.perf_counter()
                    prediction = model(batch)
                    forward_samples.append(time.perf_counter() - started)
            forward_ms = statistics.median(forward_samples) * 1000.0
            owners = [player.owner_id for player in players]
            aggregate_samples = []
            for _ in range(args.repeats):
                started = time.perf_counter()
                owner_shares(
                    prediction.detach().cpu().tolist(),
                    owners,
                )
                aggregate_samples.append(time.perf_counter() - started)
            aggregation_ms = statistics.median(aggregate_samples) * 1000.0

            row = {
                "game_id": game.game_id,
                "condition": "/".join(game.condition.values()),
                "players": len(players),
                "sql_bind_plan_ms": plan_ms,
                "lineage_extract_ms": lineage_ms,
                "graph_construct_ms": graph_ms,
                "graph_tensorize_ms": collate_ms,
                "model_forward_ms": forward_ms,
                "owner_aggregate_ms": aggregation_ms,
                "model_end_to_end_ms": (
                    plan_ms
                    + lineage_ms
                    + graph_ms
                    + collate_ms
                    + forward_ms
                    + aggregation_ms
                ),
            }
            for budget in budgets:
                masks = _permutation_masks(
                    len(game.players),
                    seed=args.seed + order_key,
                    nominal_steps=budget,
                )
                unique_masks = list(dict.fromkeys(masks))
                sql_samples = []
                for _ in range(args.repeats):
                    started = time.perf_counter()
                    for mask in unique_masks:
                        _set_active(connection, game, mask)
                        _sql_utility(
                            connection,
                            game.condition["value_function"],
                        )
                    sql_samples.append(time.perf_counter() - started)
                sql_seconds = statistics.median(sql_samples)
                row[f"mc_{budget}_unique_calls"] = len(unique_masks)
                row[f"mc_{budget}_nominal_evaluations"] = len(masks)
                row[f"mc_{budget}_sql_total_ms"] = sql_seconds * 1000.0
                row[f"mc_{budget}_ms_per_unique_call"] = (
                    sql_seconds * 1000.0 / len(unique_masks)
                )
                row[f"mc_{budget}_end_to_end_ms"] = (
                    plan_ms
                    + lineage_ms
                    + sql_seconds * 1000.0
                    + aggregation_ms
                )
            rows.append(row)
    finally:
        connection.close()

    args.output.mkdir(parents=True)
    with (args.output / "per_game.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    stages = [
        ("sql_bind_plan", "sql_bind_plan_ms"),
        ("lineage_extract", "lineage_extract_ms"),
        ("graph_construct", "graph_construct_ms"),
        ("graph_tensorize", "graph_tensorize_ms"),
        ("model_forward", "model_forward_ms"),
        ("owner_aggregate", "owner_aggregate_ms"),
        ("model_end_to_end", "model_end_to_end_ms"),
    ]
    summary = [
        _median_summary(rows, stage, field)
        for stage, field in stages
    ]
    for budget in budgets:
        summary.append(
            _median_summary(
                rows,
                f"mc_{budget}_end_to_end",
                f"mc_{budget}_end_to_end_ms",
            )
        )
        summary.append(
            _median_summary(
                rows,
                f"mc_{budget}_unique_sql_query",
                f"mc_{budget}_ms_per_unique_call",
            )
        )
    metadata = {
        "data": str(args.data),
        "database": str(args.db),
        "checkpoint": str(args.checkpoint),
        "split": args.split,
        "games": len(games),
        "budgets": budgets,
        "repeats": args.repeats,
        "seed": args.seed,
        "timing_scope": (
            "single Windows CPU/DuckDB process; median per game; "
            "sql_bind_plan is EXPLAIN only, not a pure parser microbenchmark"
        ),
        "cache_policy": (
            "MC de-duplicates coalition masks before executing SQL; "
            "model path performs no utility queries at inference"
        ),
        "excluded_from_timing": (
            "training labels, model training, disk cache effects, and "
            "network/database connection setup"
        ),
    }
    (args.output / "summary.json").write_text(
        json.dumps(
            {"metadata": metadata, "stages": summary},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"metadata": metadata, "stages": summary}, indent=2))


if __name__ == "__main__":
    main()
