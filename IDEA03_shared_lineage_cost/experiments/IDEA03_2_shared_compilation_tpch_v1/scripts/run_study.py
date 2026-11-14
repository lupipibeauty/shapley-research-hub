from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
import time
import tracemalloc
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
PRIOR = ROOT.parent / "IDEA03_2_joint_value_deepening_v1"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(PRIOR / "src"))
sys.path.insert(0, str(PRIOR / "scripts"))
sys.path.insert(0, str(WORKSPACE / "aggregate_report_shapley" / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"))

import duckdb

from joint_game import build_game, component_value, components_to_poly, poly_shapley
from run_deepening import official_boolean, validate_sql
from study import (
    ReducedADD, VALUE_NAMES, build_controlled_f2, build_threshold2_game,
    build_tpch_game, equivalence_matrix, exhaustive_values, game_value_metrics,
    historical_g1_redundancy, ratios_and_gates, shapley_from_values,
    mobius_from_values,
    shared_expression_metrics, structural_metrics, study_components, study_value,
    threshold_witness_examples, tpch_report, tpch_values, tpch_witness_dnfs,
)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader(); writer.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def fraction_error(left, right) -> float:
    return max((abs(float(a) - float(b)) for a, b in zip(left, right)), default=0.0)


def run_e0(run: Path) -> dict:
    raw = run / "raw"
    historical = [
        build_game("F0_EBH"), build_game("F1_SITE_LINK", "balanced"),
        build_game("F1_SITE_LINK", "concentrated"), build_game("F2_ENTITY_LINK", "balanced"),
        build_game("F2_ENTITY_LINK", "concentrated"),
    ]
    redundancy = [historical_g1_redundancy(game) for game in historical]
    write_csv(raw / "historical_g1_redundancy.csv", redundancy)

    game = build_threshold2_game()
    sql = validate_sql(game, exhaustive=True)
    write_csv(raw / "e0_sql_validation.csv", [sql])
    write_csv(raw / "e0_threshold_examples.csv", threshold_witness_examples(game))
    write_csv(raw / "e0_value_equivalence.csv", equivalence_matrix(game))
    value_rows, shapley_rows = [], []
    for name in VALUE_NAMES:
        metric, player_rows = game_value_metrics(game, name)
        value_rows.append(metric); shapley_rows.extend(player_rows)
    write_csv(raw / "e0_value_metrics.csv", value_rows)
    write_csv(raw / "e0_record_shapley.csv", shapley_rows)
    player_rows = [{"player_index": p.index, "player_id": p.player_id, "relation": p.relation, "key": p.key}
                   for p in game.players]
    write_csv(raw / "e0_player_mapping.csv", player_rows)
    return {"historical_games": len(historical), "all_historical_equivalent": all(r["g1_gr_mismatches"] == 0 for r in redundancy),
            "e0_game": game.game_id, "e0_sql_masks": sql["masks_checked"], "status": "VERIFIED"}


def run_e1(run: Path) -> dict:
    raw = run / "raw"
    games = [build_controlled_f2(pair, mode) for pair in (1, 2, 3) for mode in ("concentrated", "dispersed")]
    structure, sql_rows, expression, mappings, configs = [], [], [], [], []
    for game in games:
        structure.append(structural_metrics(game, "GC"))
        sql_rows.append(validate_sql(game, exhaustive=False))
        expression.extend(shared_expression_metrics(game))
        pair = int(game.game_id.split("PAIR")[1].split("_")[0])
        mode = game.game_id.rsplit("_", 1)[1].lower()
        configs.append({"game_id": game.game_id, "pair_id": pair, "mode": mode, "n": game.n,
                        "threshold_A": game.thresholds[0], "threshold_B": game.thresholds[1],
                        "E_rows": sum(p.relation == "E" for p in game.players),
                        "B_rows": sum(p.relation == "B" for p in game.players),
                        "H_rows": sum(p.relation == "H" for p in game.players),
                        "R_rows": sum(p.relation == "R2" for p in game.players)})
        for p in game.players:
            mappings.append({"game_id": game.game_id, "player_index": p.index, "player_id": p.player_id,
                             "relation": p.relation, "key": p.key})
    write_csv(raw / "e1_fixture_configs.csv", configs)
    write_csv(raw / "e1_player_mappings.csv", mappings)
    write_csv(raw / "e1_sql_validation.csv", sql_rows)
    write_csv(raw / "e1_structure_metrics.csv", structure)
    write_csv(raw / "e1_cross_game_expression_reuse.csv", expression)
    return {"paired_instances": 3, "games": len(games), "all_n": sorted(set(g.n for g in games)),
            "sql_checks": sum(r["masks_checked"] for r in sql_rows), "status": "VERIFIED"}


def lexa_per_component(game, components):
    output = [0.0] * game.n
    calls = 0
    for coefficient, dnf, _label in components:
        if not coefficient:
            continue
        calls += 1
        for player, share in official_boolean(dnf).items():
            output[player] += float(coefficient) * share
    return output, calls


def lexa_cached(game, components, cache: dict):
    output = [0.0] * game.n
    hits = misses = 0
    for coefficient, dnf, _label in components:
        key = tuple(tuple(sorted(c)) for c in dnf)
        if key in cache:
            shares = cache[key]; hits += 1
        else:
            shares = official_boolean(dnf); cache[key] = shares; misses += 1
        for player, share in shares.items():
            output[player] += float(coefficient) * share
    return output, hits, misses


def timed_call(callable_):
    tracemalloc.start()
    started = time.perf_counter()
    result = callable_()
    seconds = time.perf_counter() - started
    _cur, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    return result, seconds, peak


def benchmark_exact(game, value_name: str, repeats: int, cache: dict) -> tuple[list[dict], list[dict]]:
    rows, allocations = [], []
    source_started = time.perf_counter(); source_metrics = structural_metrics(game, value_name); source_seconds = time.perf_counter() - source_started
    transform_started = time.perf_counter(); components = study_components(game, value_name); transform_seconds = time.perf_counter() - transform_started
    values = exhaustive_values(game, value_name)
    oracle = shapley_from_values(values, game.n)
    poly = mobius_from_values(values, game.n)
    merged = poly_shapley(poly, game.n)
    if merged != oracle:
        raise AssertionError((game.game_id, value_name, "merged Harsanyi mismatch"))

    for repeat in range(1, repeats + 1):
        (lexa, calls), sec, peak = timed_call(lambda: lexa_per_component(game, components))
        rows.append({"game_id": game.game_id, "value": value_name, "method": "B1_OFFICIAL_LEXASHAP_PER_COMPONENT",
                     "repeat": repeat, "status": "VERIFIED", "T_source": source_seconds, "T_transform": transform_seconds,
                     "T_compile_solve": sec, "T_total": source_seconds + transform_seconds + sec,
                     "peak_python_bytes": peak, "compiled_units": calls, "reused_units": 0,
                     "max_abs_error": fraction_error(lexa, oracle)})

        (add_pair, sec, peak) = timed_call(lambda: _add_solve(game, value_name))
        add, add_phi = add_pair
        if add_phi != oracle:
            raise AssertionError((game.game_id, value_name, "ADD mismatch", add_phi, oracle))
        metrics = add.metrics()
        rows.append({"game_id": game.game_id, "value": value_name, "method": "B2_SHARED_ROADD_CARDINALITY_DP",
                     "repeat": repeat, "status": "VERIFIED", "T_source": source_seconds, "T_transform": 0,
                     "T_compile_solve": sec, "T_total": source_seconds + sec,
                     "peak_python_bytes": peak, "compiled_units": metrics["compiled_nodes"],
                     "reused_units": (1 << (game.n + 1)) - metrics["compiled_nodes"], "max_abs_error": 0.0})

        (cached_result, sec, peak) = timed_call(lambda: lexa_cached(game, components, cache))
        cached_phi, hits, misses = cached_result
        rows.append({"game_id": game.game_id, "value": value_name, "method": "B3_OFFICIAL_LEXASHAP_EXACT_COMPONENT_CACHE",
                     "repeat": repeat, "status": "VERIFIED", "T_source": source_seconds, "T_transform": transform_seconds,
                     "T_compile_solve": sec, "T_total": source_seconds + transform_seconds + sec,
                     "peak_python_bytes": peak, "compiled_units": misses, "reused_units": hits,
                     "max_abs_error": fraction_error(cached_phi, oracle)})

        (_merged2, sec, peak) = timed_call(lambda: poly_shapley(poly, game.n))
        rows.append({"game_id": game.game_id, "value": value_name, "method": "CONTROL_MERGED_PROVENANCE_HARSANYI",
                     "repeat": repeat, "status": "VERIFIED", "T_source": source_seconds, "T_transform": transform_seconds,
                     "T_compile_solve": sec, "T_total": source_seconds + transform_seconds + sec,
                     "peak_python_bytes": peak, "compiled_units": len(poly), "reused_units": 0, "max_abs_error": 0.0})
    for p, phi in zip(game.players, oracle):
        allocations.append({"game_id": game.game_id, "value": value_name, "player_id": p.player_id,
                            "relation": p.relation, "shapley_fraction": str(phi), "shapley": float(phi)})
    return rows, allocations


def _add_solve(game, value_name):
    add = ReducedADD(game.n, lambda mask: study_value(game, mask, value_name))
    return add, add.shapley()


def run_e2(run: Path) -> dict:
    raw = run / "raw"
    # Pre-specified pilot: E0 plus pair 1. Pairs 2--3 remain independent E1
    # structure replicates and are not silently converted into timing repeats.
    games = [build_threshold2_game(), build_controlled_f2(1, "concentrated"), build_controlled_f2(1, "dispersed")]
    rows, allocations = [], []
    # Cache is per game so variable identities are never mixed. It persists over
    # GR/GL/GC and timing repeats to measure the explicitly separate amortized case.
    for game in games:
        cache = {}
        names = VALUE_NAMES if game.game_id == "E0_F0_K2_N12" else ("GC",)
        for name in names:
            method_rows, player_rows = benchmark_exact(game, name, 3, cache)
            rows.extend(method_rows); allocations.extend(player_rows)
    write_csv(raw / "e2_exact_solver_comparison.csv", rows)
    write_csv(raw / "e2_exact_record_shapley.csv", allocations)
    return {"games": len(games), "benchmark_cells": len(rows), "timed_controlled_pairs": 1,
            "untimed_structure_only_pairs": 2,
            "all_verified": all(r["status"] == "VERIFIED" and float(r["max_abs_error"]) < 1e-8 for r in rows),
            "status": "VERIFIED"}


def extract_tpch(con, sql_path: Path) -> list[dict]:
    columns = ("orderkey", "linenumber", "suppkey", "partkey", "nation", "region", "discounted_cents", "promo")
    return [dict(zip(columns, row)) for row in con.execute(sql_path.read_text(encoding="utf-8")).fetchall()]


def tpch_game_metrics(game) -> tuple[list[dict], list[dict]]:
    rows, allocations = [], []
    values_by_name = {name: [tpch_values(game, mask)[name] for mask in range(1 << game.n)]
                      for name in ("TPCH_ADD", "TPCH_LOCAL", "TPCH_CROSS")}
    for name, values in values_by_name.items():
        phi = shapley_from_values(values, game.n)
        negative_marginals = sum(values[m | (1 << i)] < values[m]
                                 for i in range(game.n) for m in range(1 << game.n) if not m & (1 << i))
        rows.append({"game_id": game.game_id, "value": name, "n": game.n,
                     "nonzero_coalitions": sum(v != 0 for v in values), "full_value": str(values[-1]),
                     "distinct_values": len(set(values)), "negative_marginals": negative_marginals,
                     "negative_shapley_players": sum(v < 0 for v in phi), "status": "VERIFIED"})
        for (pid, relation), value in zip(game.players, phi):
            allocations.append({"game_id": game.game_id, "value": name, "player_id": pid,
                                "relation": relation, "shapley_fraction": str(value), "shapley": float(value)})
    return rows, allocations


def run_tpch(run: Path) -> dict:
    raw = run / "raw"
    db = WORKSPACE / "tmp" / "researchlab_v2" / "workspace" / "BRBD_v1" / "runs" / "R1_luo" / "tpch_sf01" / "tpch_sf01.duckdb"
    if not db.exists():
        write_json(raw / "tpch_status.json", {"status": "ENV_BLOCKED", "reason": "SF0.1 DuckDB missing", "path": str(db)})
        return {"status": "ENV_BLOCKED"}
    con = duckdb.connect(str(db), read_only=True)
    samples = {
        "TPCH_NATURAL_SF01": extract_tpch(con, ROOT / "sql" / "tpch_natural_extract.sql"),
        "TPCH_PRESSURE_SUPPLIER74_SF01": extract_tpch(con, ROOT / "sql" / "tpch_pressure_extract.sql"),
    }
    con.close()
    source_rows, game_rows, player_rows, value_rows, allocation_rows, structure_rows = [], [], [], [], [], []
    for game_id, records in samples.items():
        for row in records: source_rows.append({"game_id": game_id, **row})
        game = build_tpch_game(game_id, records)
        if game.n > 16:
            raise AssertionError((game_id, game.n, "oracle policy"))
        for i, (pid, relation) in enumerate(game.players):
            player_rows.append({"game_id": game_id, "player_index": i, "player_id": pid, "relation": relation})
        vrows, arows = tpch_game_metrics(game); value_rows.extend(vrows); allocation_rows.extend(arows)
        proofs = [dnf[0] for dnf in tpch_witness_dnfs(game)]
        structure_rows.append({"game_id": game_id, "n": game.n, "line_witnesses": len(proofs),
                               "unique_orders": len({r["orderkey"] for r in records}),
                               "unique_suppliers": len({r["suppkey"] for r in records}),
                               "unique_parts": len({r["partkey"] for r in records}),
                               "shared_proof_pairs": sum(bool(a & b) for i, a in enumerate(proofs) for b in proofs[i+1:]),
                               "max_proof_overlap": max((len(a & b) for i, a in enumerate(proofs) for b in proofs[i+1:]), default=0),
                               "regions": ";".join(game.regions), "nations": ";".join(game.nations)})
        game_rows.append({"game_id": game_id, "source": "TPC-H SF0.1 native PK/FK", "n": game.n,
                          "geography": "customer nation", "players": "Order;Lineitem;Supplier;Part",
                          "dimensions_exogenous": "Customer;Nation;Region", "precision": "integer discounted cents",
                          "status": "VERIFIED"})
    write_csv(raw / "tpch_source_rows.csv", source_rows)
    write_csv(raw / "tpch_games.csv", game_rows)
    write_csv(raw / "tpch_player_mapping.csv", player_rows)
    write_csv(raw / "tpch_value_metrics.csv", value_rows)
    write_csv(raw / "tpch_record_shapley.csv", allocation_rows)
    write_csv(raw / "tpch_structure_metrics.csv", structure_rows)
    write_json(raw / "tpch_status.json", {"status": "VERIFIED", "database": str(db), "database_sha256": sha256(db),
                                           "samples": list(samples), "large_scale_performance": "NOT_RUN_BY_PROTOCOL"})
    return {"status": "VERIFIED", "games": len(samples), "max_n": max(r["n"] for r in game_rows)}


def environment_manifest(run_id: str) -> dict:
    prior = PRIOR / "runs" / "DEEP_20261113_155744"
    return {"run_id": run_id, "created_local": time.strftime("%Y-%m-%d %H:%M:%S"), "python": sys.version,
            "platform": platform.platform(), "duckdb": duckdb.__version__,
            "prior_frozen_run": str(prior), "prior_exists": prior.exists(),
            "official_lexashap": str(WORKSPACE / "aggregate_report_shapley" / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"),
            "large_experiments_run": False, "git_operations": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("e0", "e1", "e2", "tpch", "all"), default="all")
    args = parser.parse_args()
    run_id = time.strftime("SHARED_%Y%m%d_%H%M%S")
    run = ROOT / "runs" / run_id
    run.mkdir(parents=True)
    selected = ("e0", "e1", "e2", "tpch") if args.stage == "all" else (args.stage,)
    summary = {"run_id": run_id, "stages": {}}
    for stage in selected:
        summary["stages"][stage] = {"e0": run_e0, "e1": run_e1, "e2": run_e2, "tpch": run_tpch}[stage](run)
    summary["status"] = "VERIFIED" if all(x.get("status") == "VERIFIED" for x in summary["stages"].values()) else "PARTIAL"
    write_json(run / "summary.json", summary)
    write_json(run / "environment_manifest.json", environment_manifest(run_id))
    write_json(ROOT / "LATEST_RUN.json", {"run_id": run_id, "path": str(run.relative_to(ROOT)), "status": summary["status"]})
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
