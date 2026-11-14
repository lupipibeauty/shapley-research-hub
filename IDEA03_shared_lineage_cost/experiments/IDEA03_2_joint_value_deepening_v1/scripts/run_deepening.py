from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import sys
import time
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import duckdb
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(WORKSPACE / "aggregate_report_shapley" / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"))

from joint_game import (  # noqa: E402
    CITY_PROVINCE,
    NODES,
    build_game,
    component_value,
    components_to_poly,
    exact_shapley,
    poly_shapley,
    report_python,
    structure_metrics,
    sufficient_statistics,
    value,
    value_components,
)
from Algorithms.LExaShap.ShapleyCircuit import DNFCircuit  # noqa: E402


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def create_db(game):
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE active_players(player_index INTEGER)")
    con.execute("CREATE TABLE nodes(ord INTEGER,node VARCHAR)")
    con.executemany("INSERT INTO nodes VALUES (?,?)", list(enumerate(NODES)))
    con.execute("CREATE TABLE d(city VARCHAR,province VARCHAR)")
    con.executemany("INSERT INTO d VALUES (?,?)", list(CITY_PROVINCE.items()))
    con.execute("CREATE TABLE e(player_index INTEGER,eid VARCHAR)")
    con.execute("CREATE TABLE b(player_index INTEGER,sid VARCHAR,eid VARCHAR,city VARCHAR,industry VARCHAR)")
    con.execute("CREATE TABLE h(player_index INTEGER,sid VARCHAR,workers INTEGER)")
    con.execute("CREATE TABLE r1(player_index INTEGER,rid VARCHAR,sid VARCHAR,city VARCHAR)")
    con.execute("CREATE TABLE r2(player_index INTEGER,rid VARCHAR,eid VARCHAR,city VARCHAR)")
    for player in game.players:
        if player.relation == "E":
            con.execute("INSERT INTO e VALUES (?,?)", [player.index, player.key])
    for site in game.sites:
        con.execute("INSERT INTO b VALUES (?,?,?,?,?)", [site.b_player, site.sid, site.eid, site.city, site.industry])
        con.execute("INSERT INTO h VALUES (?,?,?)", [site.h_player, site.sid, site.workers])
    for link in game.links:
        table = "r1" if game.query_version == "F1_SITE_LINK" else "r2"
        con.execute(f"INSERT INTO {table} VALUES (?,?,?,?)", [link.player, link.rid, link.object_id, link.city])
    return con


def sql_report(con, game, mask: int):
    con.execute("DELETE FROM active_players")
    selected = [(i,) for i in range(game.n) if mask & (1 << i)]
    if selected:
        con.executemany("INSERT INTO active_players VALUES (?)", selected)
    sql_name = {"F0_EBH": "report_f0.sql", "F1_SITE_LINK": "report_f1.sql", "F2_ENTITY_LINK": "report_f2.sql"}[game.query_version]
    rows = con.execute((ROOT / "sql" / sql_name).read_text(encoding="utf-8")).fetchall()
    output = {}
    for node, c, s, w, m, share in rows:
        output[(node, "enterprise_count")] = int(c)
        output[(node, "site_count")] = int(s)
        output[(node, "workers")] = int(w)
        output[(node, "mfg_workers")] = int(m)
        output[(node, "mfg_share")] = None if share is None else Fraction(int(m), int(w))
    return output


def validate_sql(game, exhaustive: bool) -> dict:
    con = create_db(game)
    if exhaustive:
        masks = range(1 << game.n)
    else:
        boundary = {0, (1 << game.n) - 1}
        boundary.update((index * 7919) % (1 << game.n) for index in range(64))
        masks = sorted(boundary)
    checked = 0
    started = time.perf_counter()
    for mask in masks:
        expected, observed = report_python(game, mask), sql_report(con, game, mask)
        if expected != observed:
            raise AssertionError((game.game_id, mask, expected, observed))
        checked += 1
    con.close()
    return {"game_id": game.game_id, "status": "VERIFIED", "masks_checked": checked,
            "exhaustive": exhaustive, "seconds": time.perf_counter() - started}


def official_boolean(dnf):
    circuit = DNFCircuit([set(str(player) for player in clause) for clause in dnf])
    scale = (2 ** len(circuit.vars)) / math.factorial(len(circuit.vars))
    output = {}
    for variable in circuit.vars:
        output[int(str(variable.label))] = sum(float(g) * float(p) for g, p in zip(variable.grad, variable.prob)) * scale
    return output


def lexashap_allocation(game, components):
    grouped: defaultdict[tuple, Fraction] = defaultdict(Fraction)
    dnfs = {}
    for coefficient, dnf, _label in components:
        key = tuple(tuple(sorted(clause)) for clause in dnf)
        grouped[key] += coefficient
        dnfs[key] = dnf
    output = [0.0] * game.n
    for key, coefficient in grouped.items():
        if not coefficient:
            continue
        for player, share in official_boolean(dnfs[key]).items():
            output[player] += float(coefficient) * share
    return output, len([value for value in grouped.values() if value])


def compile_roadd(game, value_name: str):
    unique = {}
    nodes = []
    terminals = {}
    def terminal_id(v: Fraction):
        if v not in terminals:
            terminals[v] = -(len(terminals) + 1)
        return terminals[v]
    def build(level: int, mask: int):
        if level == game.n:
            return terminal_id(value(game, mask, value_name))
        low = build(level + 1, mask)
        high = build(level + 1, mask | (1 << level))
        if low == high:
            return low
        key = (level, low, high)
        if key not in unique:
            unique[key] = len(nodes)
            nodes.append(key)
        return unique[key]
    root = build(0, 0)
    return {"root": root, "nonterminal_nodes": len(nodes), "terminal_nodes": len(terminals),
            "total_nodes": len(nodes) + len(terminals)}


def oracle_float(game, value_name: str):
    n = game.n
    values = np.asarray([float(value(game, mask, value_name)) for mask in range(1 << n)], dtype=np.float64)
    counts = np.fromiter((mask.bit_count() for mask in range(1 << n)), dtype=np.int16)
    factorial = [math.factorial(i) for i in range(n + 1)]
    weights = np.asarray([factorial[k] * factorial[n - k - 1] / factorial[n] if k < n else 0.0 for k in counts])
    masks = np.arange(1 << n, dtype=np.int64)
    output = np.zeros(n, dtype=np.float64)
    for player in range(n):
        bit = 1 << player
        base = masks[(masks & bit) == 0]
        output[player] = np.sum(weights[base] * (values[base | bit] - values[base]))
    return output, values


def benchmark_game(game, value_name: str):
    rows = []
    transform_start = time.perf_counter()
    components = value_components(game, value_name)
    transform_seconds = time.perf_counter() - transform_start
    check_masks = range(1 << game.n) if game.n <= 12 else sorted({0, (1 << game.n) - 1, *[(i * 7919) % (1 << game.n) for i in range(2048)]})
    for mask in check_masks:
        if component_value(components, mask) != value(game, mask, value_name):
            raise AssertionError((game.game_id, value_name, mask, component_value(components, mask), value(game, mask, value_name)))

    oracle_start = time.perf_counter()
    oracle, values = oracle_float(game, value_name)
    oracle_seconds = time.perf_counter() - oracle_start
    rows.append({"game_id": game.game_id, "query_version": game.query_version, "value": value_name,
                 "method": "B0_FULL_COALITION_ORACLE", "status": "VERIFIED", "transform_seconds": 0,
                 "compile_solve_seconds": oracle_seconds, "components": 0, "representation_nodes": len(values),
                 "max_abs_error": 0.0})

    poly_start = time.perf_counter()
    poly = components_to_poly(components)
    sparse = poly_shapley(poly, game.n)
    poly_seconds = time.perf_counter() - poly_start
    rows.append({"game_id": game.game_id, "query_version": game.query_version, "value": value_name,
                 "method": "SPARSE_HARSANYI_FROM_PROVENANCE", "status": "VERIFIED",
                 "transform_seconds": transform_seconds, "compile_solve_seconds": poly_seconds,
                 "components": len(components), "representation_nodes": len(poly),
                 "max_term_degree": max((mask.bit_count() for mask in poly), default=0),
                 "max_abs_error": max(abs(a - float(b)) for a, b in zip(oracle, sparse))})

    lexa_start = time.perf_counter()
    lexa, unique = lexashap_allocation(game, components)
    lexa_seconds = time.perf_counter() - lexa_start
    rows.append({"game_id": game.game_id, "query_version": game.query_version, "value": value_name,
                 "method": "OFFICIAL_LEXASHAP_BOOLEAN_COMPONENTS", "status": "VERIFIED",
                 "transform_seconds": transform_seconds, "compile_solve_seconds": lexa_seconds,
                 "components": len(components), "representation_nodes": unique,
                 "max_abs_error": max(abs(a - b) for a, b in zip(oracle, lexa))})

    add_start = time.perf_counter()
    add = compile_roadd(game, value_name) if game.n <= 14 else {"total_nodes": None}
    add_seconds = time.perf_counter() - add_start
    rows.append({"game_id": game.game_id, "query_version": game.query_version, "value": value_name,
                 "method": "LOCAL_ROADD_DIAGNOSTIC_ADAPTER", "status": "REPRESENTATION_ONLY_NOT_SOLVER" if game.n <= 14 else "RESOURCE_LIMIT_POLICY",
                 "transform_seconds": 0, "compile_solve_seconds": add_seconds,
                 "components": 0, "representation_nodes": add["total_nodes"], "max_abs_error": None})
    return rows, sparse, components, poly, add


def main():
    run_id = time.strftime("DEEP_%Y%m%d_%H%M%S")
    run = ROOT / "runs" / run_id
    raw = run / "raw"
    raw.mkdir(parents=True)
    games = [
        build_game("F0_EBH"),
        build_game("F1_SITE_LINK", "balanced"),
        build_game("F1_SITE_LINK", "concentrated"),
        build_game("F2_ENTITY_LINK", "balanced"),
        build_game("F2_ENTITY_LINK", "concentrated"),
    ]
    sql_rows, structure_rows, algorithm_rows, component_rows, shapley_rows, state_rows = [], [], [], [], [], []
    for game in games:
        # The earlier V2 already exhaustively checked the frozen F0 evaluator.
        # This phase checks the revised SQL path on deterministic boundary/sample masks.
        sql_rows.append(validate_sql(game, exhaustive=False))
        structure_rows.append(structure_metrics(game))
        seen_states = {sufficient_statistics(game, mask) for mask in range(1 << game.n)}
        state_rows.append({"game_id": game.game_id, "n": game.n, "joint_statistic_states": len(seen_states)})
        for value_name in ("G0", "G1", "G2"):
            rows, oracle, components, poly, add = benchmark_game(game, value_name)
            algorithm_rows.extend(rows)
            component_rows.append({
                "game_id": game.game_id, "value": value_name, "raw_boolean_components": len(components),
                "raw_dnf_clauses": sum(len(dnf) for _c, dnf, _l in components),
                "maximum_component_variables": max((len(set().union(*dnf)) for _c, dnf, _l in components), default=0),
                "harsanyi_terms": len(poly), "max_harsanyi_degree": max((mask.bit_count() for mask in poly), default=0),
                "roadd_nodes": add["total_nodes"],
            })
            for player, allocation in zip(game.players, oracle):
                shapley_rows.append({"game_id": game.game_id, "value": value_name, "player_id": player.player_id,
                                     "relation": player.relation, "shapley": float(allocation),
                                     "shapley_fraction": str(allocation), "payment_R1000": float(allocation * 1000)})
    write_csv(raw / "sql_validation.csv", sql_rows)
    write_csv(raw / "structure_metrics.csv", structure_rows)
    write_csv(raw / "joint_state_counts.csv", state_rows)
    write_csv(raw / "algorithm_comparison.csv", algorithm_rows)
    write_csv(raw / "component_metrics.csv", component_rows)
    write_csv(raw / "record_shapley.csv", shapley_rows)

    f0 = games[0]
    target = next(player for player in f0.players if player.player_id == "H:S2")
    coalitions = {
        "PA_context_only": ["E:E1", "B:S2"],
        "PA_plus_PB_coverage": ["E:E1", "B:S2", "E:E2", "B:S3", "H:S3"],
    }
    marginal_rows = []
    by_id = {player.player_id: player.index for player in f0.players}
    for label, ids in coalitions.items():
        mask = sum(1 << by_id[item] for item in ids)
        before, after = value(f0, mask, "G2"), value(f0, mask | (1 << target.index), "G2")
        marginal_rows.append({"context": label, "coalition": ";".join(ids), "player": target.player_id,
                              "before_G2": str(before), "after_G2": str(after), "marginal_G2": str(after - before)})
    write_csv(raw / "minimal_context_marginals.csv", marginal_rows)

    official = WORKSPACE / "aggregate_report_shapley" / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main" / "Algorithms" / "LExaShap" / "ShapleyCircuit.py"
    manifest = {
        "run_id": run_id,
        "status": "VERIFIED",
        "python": sys.version,
        "platform": platform.platform(),
        "duckdb": duckdb.__version__,
        "games": [game.game_id for game in games],
        "official_lexashap_source": str(official),
        "official_lexashap_sha256": sha256(official),
        "notes": [
            "N<=16 only; no large grid.",
            "Each Q version uses 65 unique deterministic boundary/sample masks for SQL/Python equality; exact Shapley remains exhaustive in Python at N<=16.",
            "LOCAL_ROADD_DIAGNOSTIC_ADAPTER is not presented as an official or optimized ADD family benchmark.",
        ],
    }
    write_json(run / "environment_manifest.json", manifest)
    write_json(ROOT / "LATEST_RUN.json", {"run_id": run_id, "path": str(run.relative_to(ROOT)), "status": "VERIFIED"})
    print(json.dumps({"run_id": run_id, "games": len(games), "algorithm_cells": len(algorithm_rows),
                      "sql_checks": sum(row["masks_checked"] for row in sql_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
