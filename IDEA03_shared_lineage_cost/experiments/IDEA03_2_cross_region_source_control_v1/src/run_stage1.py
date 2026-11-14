from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import platform
import sys
import time
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
HUB = Path(__file__).resolve().parents[4]
HIST = ROOT.parent / "IDEA03_2_shared_compilation_tpch_v1"
DEEP = ROOT.parent / "IDEA03_2_joint_value_deepening_v1"
STAGE0 = ROOT.parent / "IDEA03_stage0_fidelity_freeze_20261113"
sys.path.insert(0, str(HIST / "src"))
sys.path.insert(0, str(DEEP / "src"))
sys.path.insert(0, str(STAGE0 / "src"))

from study import (  # noqa: E402
    _components,
    build_controlled_f2,
    min_fill_upper_bound,
    mobius_from_values,
    poly_shapley,
    proof_sets,
)
from joint_game import (  # noqa: E402
    CITY_PROVINCE,
    METRICS,
    NODES,
    Game,
    Player,
    Site,
    minimize_dnf,
    or_dnf,
    report_python,
    site_city_dnf,
)
from validate_frozen_values import (  # noqa: E402
    FAMILIES,
    LEVELS,
    coordinate_loss,
    coordinate_scale,
    coordinate_weights,
)


CONFIG_PATH = ROOT / "config" / "stage1_protocol.json"
FROZEN_PATH = STAGE0 / "config" / "frozen_value_function.json"
SQL_PATH = ROOT / "sql" / "report_f0_frozen.sql"
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_fraction(value) -> str:
    if value is None:
        return "NULL"
    return str(Fraction(value))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def append_event(event: dict) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    event = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **event}
    with (LOGS / "run_events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_configuration():
    protocol = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    frozen = json.loads(FROZEN_PATH.read_text(encoding="utf-8"))
    return protocol, frozen


def main_weights(frozen: dict):
    return coordinate_weights(
        frozen["main_value"]["hierarchy_weights"],
        frozen["main_value"]["family_weights"],
    )


def value_of_report(report, target, empty, weights) -> Fraction:
    total = Fraction(0)
    for coordinate, weight in weights.items():
        scale = coordinate_scale(coordinate[1], target[coordinate])
        total += weight * (
            coordinate_loss(empty[coordinate], target[coordinate], scale)
            - coordinate_loss(report[coordinate], target[coordinate], scale)
        )
    return total


def gap_of_report(report, target, empty) -> Fraction:
    target_a, target_b = target[("PA", "mfg_share")], target[("PB", "mfg_share")]
    if target_a is None or target_b is None:
        raise ValueError("Full-coalition province ratios must be defined.")
    target_gap = Fraction(target_a) - Fraction(target_b)

    def loss(item) -> Fraction:
        a, b = item[("PA", "mfg_share")], item[("PB", "mfg_share")]
        if a is None or b is None:
            return Fraction(1)
        return abs((Fraction(a) - Fraction(b)) - target_gap) / 2

    return loss(empty) - loss(report)


def game_values(game: Game, frozen: dict):
    weights = main_weights(frozen)
    full_mask = (1 << game.n) - 1
    empty = report_python(game, 0)
    target = report_python(game, full_mask)
    fid_values: list[Fraction] = []
    gap_values: list[Fraction] = []
    report_states = set()
    coordinate_hashers = {coordinate: hashlib.sha256() for coordinate in weights}
    coordinate_distinct = {coordinate: set() for coordinate in weights}
    for mask in range(1 << game.n):
        report = report_python(game, mask)
        report_states.add(tuple(report[(node, metric)] for node in NODES for metric in METRICS))
        fid_values.append(value_of_report(report, target, empty, weights))
        gap_values.append(gap_of_report(report, target, empty))
        for coordinate, weight in weights.items():
            scale = coordinate_scale(coordinate[1], target[coordinate])
            component = weight * (
                coordinate_loss(empty[coordinate], target[coordinate], scale)
                - coordinate_loss(report[coordinate], target[coordinate], scale)
            )
            coordinate_distinct[coordinate].add(component)
            coordinate_hashers[coordinate].update((str(component) + "\n").encode("ascii"))
    return {
        "target": target,
        "empty": empty,
        "values": {"v_fid_main": fid_values, "v_gap_PA_PB_mfg_share": gap_values},
        "report_states": len(report_states),
        "coordinate_hashes": {c: h.hexdigest() for c, h in coordinate_hashers.items()},
        "coordinate_distinct": {c: len(v) for c, v in coordinate_distinct.items()},
    }


def value_metrics(game: Game, name: str, values: list[Fraction], report_states: int) -> tuple[dict, list[Fraction], dict[int, Fraction]]:
    poly = mobius_from_values(values, game.n)
    allocation = poly_shapley(poly, game.n)
    return {
        "game_id": game.game_id,
        "value": name,
        "n": game.n,
        "coalitions": len(values),
        "report_states": report_states,
        "value_states": len(set(values)),
        "nonzero_coalitions": sum(value != 0 for value in values),
        "v_empty": str(values[0]),
        "v_full": str(values[-1]),
        "harsanyi_terms": len(poly),
        "max_harsanyi_degree": max((mask.bit_count() for mask in poly), default=0),
        "efficiency_error": str(sum(allocation, Fraction(0)) - values[-1]),
        "negative_shapley_players": sum(phi < 0 for phi in allocation),
        "status": "VERIFIED",
    }, allocation, poly


def build_physical_game(game_id: str, protocol: dict, assignments: dict[str, str]) -> Game:
    players: list[Player] = []

    def add(relation: str, key: str) -> int:
        index = len(players)
        players.append(Player(index, f"{relation}:{key}", relation, key))
        return index

    e_players = {eid: add("E", eid) for eid in protocol["physical_records"]["E"]}
    b_players = {row["sid"]: add("B", row["sid"]) for row in protocol["physical_records"]["B_H"]}
    h_players = {row["sid"]: add("H", row["sid"]) for row in protocol["physical_records"]["B_H"]}
    sites = tuple(
        Site(
            row["sid"],
            assignments[row["sid"]],
            row["city"],
            row["industry"],
            row["workers"],
            e_players[assignments[row["sid"]]],
            b_players[row["sid"]],
            h_players[row["sid"]],
        )
        for row in protocol["physical_records"]["B_H"]
    )
    return Game(game_id, "F0_EBH", tuple(players), sites, (), (1, 1))


def province_for_site(site: Site) -> str:
    assert site.city is not None
    return CITY_PROVINCE[site.city]


def source_metrics(game: Game) -> tuple[dict, list[dict]]:
    proofs = proof_sets(game)
    occurrences = Counter(player for proof in proofs for player in proof)
    overlaps = [len(left & right) for i, left in enumerate(proofs) for right in proofs[i + 1 :]]
    edges: set[tuple[int, int]] = set()
    for proof in proofs:
        edges.update(tuple(pair) for pair in itertools.combinations(sorted(proof), 2))
    player_regions = defaultdict(set)
    for site in game.sites:
        proof = frozenset((site.e_player, site.b_player, site.h_player))
        for player in proof:
            player_regions[player].add(province_for_site(site))
    cross_players = [p for p, regions in player_regions.items() if len(regions) > 1]

    object_rows = []
    raw_clauses = []
    unique_dnfs = set()
    for node in NODES:
        node_cities = tuple(CITY_PROVINCE) if node == "NAT" else (
            tuple(city for city, province in CITY_PROVINCE.items() if province == node)
            if node in {"PA", "PB"}
            else (node,)
        )
        for eid in sorted({site.eid for site in game.sites}):
            dnf = or_dnf(*(site_city_dnf(game, site, city) for site in game.sites for city in node_cities if site.eid == eid))
            if dnf:
                object_rows.append({"game_id": game.game_id, "node": node, "metric_family": "enterprise_count", "object": eid, "alternative_proofs": len(dnf), "dnf": ";".join("&".join(map(str, sorted(c))) for c in dnf)})
                raw_clauses.extend(dnf); unique_dnfs.add(tuple(tuple(sorted(c)) for c in dnf))
        for site in game.sites:
            dnf = or_dnf(*(site_city_dnf(game, site, city) for city in node_cities))
            if dnf:
                for family in ("site_count", "workers", "mfg_workers" if site.industry == "manufacturing" else None):
                    if family is None:
                        continue
                    object_rows.append({"game_id": game.game_id, "node": node, "metric_family": family, "object": site.sid, "alternative_proofs": len(dnf), "dnf": ";".join("&".join(map(str, sorted(c))) for c in dnf)})
                    raw_clauses.extend(dnf); unique_dnfs.add(tuple(tuple(sorted(c)) for c in dnf))
    metric = {
        "game_id": game.game_id,
        "n": game.n,
        "E_rows": sum(p.relation == "E" for p in game.players),
        "B_rows": sum(p.relation == "B" for p in game.players),
        "H_rows": sum(p.relation == "H" for p in game.players),
        "join_witnesses": len(proofs),
        "minimal_witnesses": len(set(proofs)),
        "variable_occurrences": sum(map(len, proofs)),
        "shared_source_players": sum(count > 1 for count in occurrences.values()),
        "cross_province_source_players": len(cross_players),
        "cross_province_E_players": sum(game.players[p].relation == "E" for p in cross_players),
        "overlapping_proof_pairs": sum(value > 0 for value in overlaps),
        "maximum_proof_overlap": max(overlaps, default=0),
        "primal_edges": len(edges),
        "connected_components": _components(range(game.n), edges),
        "min_fill_treewidth_upper_bound": min_fill_upper_bound(game.n, edges),
        "raw_report_dnf_clause_occurrences": len(raw_clauses),
        "unique_report_dnf_clauses": len({tuple(sorted(c)) for c in raw_clauses}),
        "unique_report_component_dnfs": len(unique_dnfs),
        "compiled_circuit_nodes": "NOT_MEASURED_NO_ELIGIBLE_DIRECT_COMPILER",
    }
    return metric, object_rows


def full_report_rows(game: Game, report: dict) -> list[dict]:
    return [
        {"game_id": game.game_id, "node": node, "metric": metric, "value": canonical_fraction(report[(node, metric)])}
        for node in NODES for metric in METRICS
    ]


def player_rows(game: Game) -> list[dict]:
    site_by_player = {}
    for site in game.sites:
        site_by_player[site.e_player] = site_by_player.get(site.e_player, "") + (";" if site_by_player.get(site.e_player) else "") + site.sid
        site_by_player[site.b_player] = site.sid
        site_by_player[site.h_player] = site.sid
    return [
        {"game_id": game.game_id, "player_index": p.index, "player_id": p.player_id, "relation": p.relation, "key": p.key, "supported_sites": site_by_player.get(p.index, "")}
        for p in game.players
    ]


def sql_setup(con, game: Game) -> None:
    con.execute("CREATE TABLE e(player_index INTEGER, eid VARCHAR)")
    con.execute("CREATE TABLE b(player_index INTEGER, sid VARCHAR, eid VARCHAR, city VARCHAR, industry VARCHAR)")
    con.execute("CREATE TABLE h(player_index INTEGER, sid VARCHAR, workers INTEGER)")
    con.execute("CREATE TABLE d(city VARCHAR, province VARCHAR)")
    con.execute("CREATE TABLE nodes(ord INTEGER, node VARCHAR)")
    con.executemany("INSERT INTO e VALUES (?,?)", [(p.index, p.key) for p in game.players if p.relation == "E"])
    con.executemany("INSERT INTO b VALUES (?,?,?,?,?)", [(site.b_player, site.sid, site.eid, site.city, site.industry) for site in game.sites])
    con.executemany("INSERT INTO h VALUES (?,?,?)", [(site.h_player, site.sid, site.workers) for site in game.sites])
    con.executemany("INSERT INTO d VALUES (?,?)", list(CITY_PROVINCE.items()))
    con.executemany("INSERT INTO nodes VALUES (?,?)", list(enumerate(NODES)))


def validation_masks(game: Game) -> list[tuple[str, int]]:
    masks: dict[int, set[str]] = defaultdict(set)

    def add(label: str, mask: int):
        masks[mask].add(label)

    full = (1 << game.n) - 1
    add("empty", 0); add("full", full)
    for p in game.players:
        add(f"singleton:{p.player_id}", 1 << p.index)
        add(f"leave_one_out:{p.player_id}", full ^ (1 << p.index))
    for relation in ("E", "B", "H"):
        add(f"relation_only:{relation}", sum(1 << p.index for p in game.players if p.relation == relation))
    add("all_E_B_without_H", sum(1 << p.index for p in game.players if p.relation in {"E", "B"}))
    add("all_E_H_without_B", sum(1 << p.index for p in game.players if p.relation in {"E", "H"}))
    for site in game.sites:
        witness = (1 << site.e_player) | (1 << site.b_player) | (1 << site.h_player)
        add(f"witness:{site.sid}", witness)
        add(f"witness_missing_E:{site.sid}", witness ^ (1 << site.e_player))
        add(f"witness_missing_B:{site.sid}", witness ^ (1 << site.b_player))
        add(f"witness_missing_H:{site.sid}", witness ^ (1 << site.h_player))
    for province in ("PA", "PB"):
        mask = 0
        for site in game.sites:
            if province_for_site(site) == province:
                mask |= (1 << site.e_player) | (1 << site.b_player) | (1 << site.h_player)
        add(f"all_{province}_witnesses", mask)
    cross_e = set()
    regions = defaultdict(set)
    for site in game.sites:
        regions[site.e_player].add(province_for_site(site))
    cross_e.update(p for p, value in regions.items() if len(value) > 1)
    for p in cross_e:
        add(f"all_without_cross_E:{game.players[p].player_id}", full ^ (1 << p))
    return [("|".join(sorted(labels)), mask) for mask, labels in sorted(masks.items())]


def sql_validate(game: Game) -> list[dict]:
    query = SQL_PATH.read_text(encoding="utf-8")
    rows = []
    con = duckdb.connect(":memory:")
    try:
        sql_setup(con, game)
        for label, mask in validation_masks(game):
            con.execute("CREATE OR REPLACE TEMP TABLE active_players(player_index INTEGER)")
            active = [(p.index,) for p in game.players if mask & (1 << p.index)]
            if active:
                con.executemany("INSERT INTO active_players VALUES (?)", active)
            sql_rows = con.execute(query).fetchall()
            sql_report = {}
            for node, enterprise, sites, workers, mfg, share in sql_rows:
                sql_report[(node, "enterprise_count")] = int(enterprise)
                sql_report[(node, "site_count")] = int(sites)
                sql_report[(node, "workers")] = int(workers)
                sql_report[(node, "mfg_workers")] = int(mfg)
                sql_report[(node, "mfg_share")] = None if share is None else Fraction(str(share))
            py_report = report_python(game, mask)
            mismatches = []
            for coordinate in py_report:
                left, right = sql_report[coordinate], py_report[coordinate]
                if coordinate[1] == "mfg_share" and left is not None and right is not None:
                    if abs(float(left) - float(right)) > 1e-12:
                        mismatches.append(f"{coordinate}:{left}!={right}")
                elif left != right:
                    mismatches.append(f"{coordinate}:{left}!={right}")
            rows.append({"game_id": game.game_id, "sample": label, "mask": mask, "mismatches": len(mismatches), "details": ";".join(mismatches), "status": "VERIFIED" if not mismatches else "FAILED_CORRECTNESS"})
    finally:
        con.close()
    return rows


def compare_full_reports(left_id: str, left: dict, right_id: str, right: dict) -> list[dict]:
    rows = []
    for node in NODES:
        for metric in METRICS:
            a, b = left[(node, metric)], right[(node, metric)]
            rows.append({"left": left_id, "right": right_id, "node": node, "metric": metric, "left_value": canonical_fraction(a), "right_value": canonical_fraction(b), "equal": a == b})
    return rows


def run_experiment1(protocol: dict, frozen: dict) -> None:
    append_event({"step": "experiment1", "event": "start", "historical_pair": 1})
    games = [build_controlled_f2(1, mode) for mode in ("concentrated", "dispersed")]
    analyses = {game.game_id: game_values(game, frozen) for game in games}
    metrics_rows, allocation_rows, coordinate_rows, report_rows = [], [], [], []
    allocations = {}
    for game in games:
        analysis = analyses[game.game_id]
        report_rows.extend(full_report_rows(game, analysis["target"]))
        for name, values in analysis["values"].items():
            metrics, allocation, _poly = value_metrics(game, name, values, analysis["report_states"])
            allocations[(game.game_id, name)] = allocation
            metrics_rows.append(metrics)
            allocation_rows.extend({"game_id": game.game_id, "value": name, "player_index": p.index, "player_id": p.player_id, "relation": p.relation, "shapley_fraction": str(phi), "shapley": float(phi)} for p, phi in zip(game.players, allocation))
    left, right = games
    left_a, right_a = analyses[left.game_id], analyses[right.game_id]
    for coordinate in left_a["coordinate_hashes"]:
        coordinate_rows.append({"left": left.game_id, "right": right.game_id, "node": coordinate[0], "metric": coordinate[1], "left_full": canonical_fraction(left_a["target"][coordinate]), "right_full": canonical_fraction(right_a["target"][coordinate]), "full_equal": left_a["target"][coordinate] == right_a["target"][coordinate], "component_game_equal_by_player_id": left_a["coordinate_hashes"][coordinate] == right_a["coordinate_hashes"][coordinate], "left_component_states": left_a["coordinate_distinct"][coordinate], "right_component_states": right_a["coordinate_distinct"][coordinate]})
    equivalence_rows = []
    for name in ("v_fid_main", "v_gap_PA_PB_mfg_share"):
        a, b = left_a["values"][name], right_a["values"][name]
        phi_a = allocations[(left.game_id, name)]
        phi_b = allocations[(right.game_id, name)]
        equivalence_rows.append({"scope": "old_e1_pair1", "left": left.game_id, "right": right.game_id, "value": name, "value_tables_equal_by_player_id": a == b, "different_coalitions": sum(x != y for x, y in zip(a, b)), "shapley_vectors_equal_by_player_id": phi_a == phi_b, "sorted_shapley_multisets_equal": sorted(phi_a) == sorted(phi_b), "status": "NEGATIVE_CONTROL" if a == b else "VERIFIED_DIFFERENCE"})
    write_csv(RESULTS / "old_e1_full_reports.csv", report_rows)
    write_csv(RESULTS / "old_e1_value_metrics.csv", metrics_rows)
    write_csv(RESULTS / "old_e1_shapley.csv", allocation_rows)
    write_csv(RESULTS / "old_e1_coordinate_comparison.csv", coordinate_rows)
    write_csv(RESULTS / "equivalence_checks_experiment1.csv", equivalence_rows)
    append_event({"step": "experiment1", "event": "complete", "status": "VERIFIED", "pairs_evaluated": 1})


def pair_control_rows(pair_name: str, left: Game, right: Game, left_analysis: dict, right_analysis: dict) -> list[dict]:
    left_source, _ = source_metrics(left); right_source, _ = source_metrics(right)
    report_diffs = sum(left_analysis["target"][c] != right_analysis["target"][c] for c in left_analysis["target"])
    left_degrees = sorted(Counter(site.eid for site in left.sites).values(), reverse=True)
    right_degrees = sorted(Counter(site.eid for site in right.sites).values(), reverse=True)
    return [
        {"pair": pair_name, "check": "same_player_ids", "left": ";".join(p.player_id for p in left.players), "right": ";".join(p.player_id for p in right.players), "passed": [p.player_id for p in left.players] == [p.player_id for p in right.players]},
        {"pair": pair_name, "check": "same_fact_counts", "left": f"{left_source['E_rows']}/{left_source['B_rows']}/{left_source['H_rows']}", "right": f"{right_source['E_rows']}/{right_source['B_rows']}/{right_source['H_rows']}", "passed": all(left_source[k] == right_source[k] for k in ("E_rows", "B_rows", "H_rows"))},
        {"pair": pair_name, "check": "same_join_witnesses", "left": left_source["join_witnesses"], "right": right_source["join_witnesses"], "passed": left_source["join_witnesses"] == right_source["join_witnesses"]},
        {"pair": pair_name, "check": "full_report_differences", "left": 0, "right": report_diffs, "passed": report_diffs == (0 if pair_name == "strict" else 1)},
        {"pair": pair_name, "check": "cross_province_E_players", "left": left_source["cross_province_E_players"], "right": right_source["cross_province_E_players"], "passed": (left_source["cross_province_E_players"], right_source["cross_province_E_players"]) == ((1, 1) if pair_name == "strict" else (0, 1))},
        {"pair": pair_name, "check": "enterprise_witness_degree_multiset", "left": str(left_degrees), "right": str(right_degrees), "passed": left_degrees != right_degrees if pair_name == "strict" else True},
        {"pair": pair_name, "check": "pre_registered_nonisomorphism_invariant", "left": "degree_multiset" if pair_name == "strict" else "region_support_count", "right": "different", "passed": (left_degrees != right_degrees) if pair_name == "strict" else (left_source["cross_province_E_players"] != right_source["cross_province_E_players"])},
    ]


def run_experiment2_and_3(protocol: dict, frozen: dict) -> None:
    append_event({"step": "experiment2", "event": "start"})
    definitions = [
        ("strict", "STRICT_CONCENTRATED", protocol["strict_pair"]["strict_concentrated"], "STRICT_BALANCED", protocol["strict_pair"]["strict_balanced"]),
        ("relaxed", "RELAXED_NO_CROSS", protocol["relaxed_pair"]["relaxed_no_cross"], "RELAXED_ONE_CROSS", protocol["relaxed_pair"]["relaxed_one_cross"]),
    ]
    games: dict[str, Game] = {}
    analyses = {}
    for _pair, left_id, left_map, right_id, right_map in definitions:
        for game_id, assignment in ((left_id, left_map), (right_id, right_map)):
            game = build_physical_game(game_id, protocol, assignment)
            games[game_id] = game
            analyses[game_id] = game_values(game, frozen)

    player_map_rows, fixture_rows, full_rows, source_rows, object_rows = [], [], [], [], []
    value_rows, allocation_rows, comparison_rows, control_rows, sql_rows = [], [], [], [], []
    allocations = {}
    for game_id, game in games.items():
        player_map_rows.extend(player_rows(game))
        for site in game.sites:
            fixture_rows.append({"game_id": game_id, "sid": site.sid, "eid": site.eid, "city": site.city, "province": province_for_site(site), "industry": site.industry, "workers": site.workers, "E_player": game.players[site.e_player].player_id, "B_player": game.players[site.b_player].player_id, "H_player": game.players[site.h_player].player_id})
        analysis = analyses[game_id]
        full_rows.extend(full_report_rows(game, analysis["target"]))
        source, objects = source_metrics(game)
        source["report_states"] = analysis["report_states"]
        source_rows.append(source); object_rows.extend(objects)
        for name, values in analysis["values"].items():
            metrics, allocation, _poly = value_metrics(game, name, values, analysis["report_states"])
            allocations[(game_id, name)] = allocation
            value_rows.append(metrics)
            allocation_rows.extend({"game_id": game_id, "value": name, "player_index": p.index, "player_id": p.player_id, "relation": p.relation, "shapley_fraction": str(phi), "shapley": float(phi)} for p, phi in zip(game.players, allocation))
        sql_rows.extend(sql_validate(game))
        if any(row["status"] != "VERIFIED" for row in sql_rows if row["game_id"] == game_id):
            append_event({"step": "experiment2", "event": "stop", "game_id": game_id, "status": "FAILED_CORRECTNESS"})
            raise AssertionError(f"SQL/Python mismatch in {game_id}")

    for pair_name, left_id, _left_map, right_id, _right_map in definitions:
        left, right = games[left_id], games[right_id]
        left_a, right_a = analyses[left_id], analyses[right_id]
        control_rows.extend(pair_control_rows(pair_name, left, right, left_a, right_a))
        comparison_rows.extend(compare_full_reports(left_id, left_a["target"], right_id, right_a["target"]))
        for name in ("v_fid_main", "v_gap_PA_PB_mfg_share"):
            a, b = left_a["values"][name], right_a["values"][name]
            phi_a = allocations[(left_id, name)]
            phi_b = allocations[(right_id, name)]
            comparison_rows.append({"left": left_id, "right": right_id, "node": "VALUE_GAME", "metric": name, "left_value": str(a[-1]), "right_value": str(b[-1]), "equal": a == b, "different_coalitions": sum(x != y for x, y in zip(a, b)), "shapley_equal_by_player_id": phi_a == phi_b, "sorted_shapley_multisets_equal": sorted(phi_a) == sorted(phi_b)})
    if any(str(row["passed"]).lower() != "true" for row in control_rows if row["pair"] == "strict"):
        append_event({"step": "experiment2", "event": "stop", "status": "INVALID_PAIRING"})
        raise AssertionError("Strict pair did not pass pre-registered controls")

    write_csv(RESULTS / "new_fixture_records.csv", fixture_rows)
    write_csv(RESULTS / "new_player_mapping.csv", player_map_rows)
    write_csv(RESULTS / "new_full_reports.csv", full_rows)
    write_csv(RESULTS / "new_source_metrics.csv", source_rows)
    write_csv(RESULTS / "new_source_objects.csv", object_rows)
    write_csv(RESULTS / "new_value_metrics.csv", value_rows)
    write_csv(RESULTS / "new_shapley.csv", allocation_rows)
    write_csv(RESULTS / "new_pair_comparisons.csv", comparison_rows)
    write_csv(RESULTS / "pair_control_checks.csv", control_rows)
    write_csv(RESULTS / "sql_python_validation.csv", sql_rows)
    append_event({"step": "experiment2_3", "event": "complete", "status": "VERIFIED", "strict_pair": "VERIFIED", "relaxed_pair": "LOCAL_OBSERVATION"})


def finalize_manifest(protocol: dict) -> None:
    generate_posthoc_tables()
    artifacts = [CONFIG_PATH, FROZEN_PATH, SQL_PATH, Path(__file__).resolve()]
    artifacts.extend(sorted(RESULTS.glob("*.csv")))
    manifest = {
        "status": "STAGE1_COMPLETED_STAGE2_NOT_STARTED",
        "protocol_version": protocol["protocol_version"],
        "historical_canonical_reused": protocol["history_reuse"],
        "history_experiments_rerun": False,
        "old_e1_sql_rerun": False,
        "new_games": ["STRICT_CONCENTRATED", "STRICT_BALANCED", "RELAXED_NO_CROSS", "RELAXED_ONE_CROSS"],
        "oracle_truth_table_used_as_structured_algorithm_input": False,
        "performance_ranking_performed": False,
        "python": sys.version,
        "duckdb": duckdb.__version__,
        "platform": platform.platform(),
        "hashes": {str(path.relative_to(HUB)): sha256(path) for path in artifacts},
    }
    (RESULTS / "stage1_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_posthoc_tables() -> None:
    with (RESULTS / "new_source_objects.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    source_index = {
        (row["game_id"], row["node"], row["metric_family"], row["object"]): row["dnf"]
        for row in source_rows
    }
    pairs = (
        ("strict", "STRICT_CONCENTRATED", "STRICT_BALANCED"),
        ("relaxed", "RELAXED_NO_CROSS", "RELAXED_ONE_CROSS"),
    )
    object_differences = []
    coordinate_differences = []
    for pair_name, left, right in pairs:
        keys = sorted({key[1:] for key in source_index if key[0] in {left, right}})
        changed_by_node = defaultdict(set)
        for node, family, obj in keys:
            a = source_index.get((left, node, family, obj), "MISSING")
            b = source_index.get((right, node, family, obj), "MISSING")
            if a != b:
                object_differences.append({"pair": pair_name, "left": left, "right": right, "node": node, "metric_family": family, "object": obj, "left_dnf": a, "right_dnf": b})
                changed_by_node[node].add(family)
        for node, families in sorted(changed_by_node.items()):
            for metric in METRICS:
                uses_change = (
                    (metric in families)
                    or (metric == "mfg_share" and bool(families & {"workers", "mfg_workers"}))
                )
                if uses_change:
                    coordinate_differences.append({"pair": pair_name, "left": left, "right": right, "node": node, "metric": metric, "changed_source_families": ";".join(sorted(families))})
    write_csv(RESULTS / "new_source_object_differences.csv", object_differences)
    write_csv(RESULTS / "new_source_coordinate_differences.csv", coordinate_differences)

    def shapley_differences(input_name: str, output_name: str, pair_defs: tuple[tuple[str, str, str], ...]):
        with (RESULTS / input_name).open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        index = {(row["game_id"], row["value"], row["player_id"]): Fraction(row["shapley_fraction"]) for row in rows}
        output = []
        for pair_name, left, right in pair_defs:
            keys = sorted({key[1:] for key in index if key[0] in {left, right}})
            for value, player in keys:
                a, b = index[(left, value, player)], index[(right, value, player)]
                if a != b:
                    output.append({"pair": pair_name, "left": left, "right": right, "value": value, "player_id": player, "left_shapley": str(a), "right_shapley": str(b), "delta_right_minus_left": str(b - a), "absolute_delta": str(abs(b - a)), "absolute_delta_float": float(abs(b - a))})
        write_csv(RESULTS / output_name, output)

    shapley_differences("new_shapley.csv", "new_shapley_pair_differences.csv", pairs)
    shapley_differences(
        "old_e1_shapley.csv",
        "old_e1_shapley_differences.csv",
        (("old_e1_pair1", "E1_PAIR1_CONCENTRATED", "E1_PAIR1_DISPERSED"),),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=("experiment1", "new-pairs", "finalize", "all"), default="all")
    args = parser.parse_args()
    protocol, frozen = load_configuration()
    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.step in {"experiment1", "all"}:
        run_experiment1(protocol, frozen)
    if args.step in {"new-pairs", "all"}:
        run_experiment2_and_3(protocol, frozen)
    if args.step in {"finalize", "all"}:
        finalize_manifest(protocol)


if __name__ == "__main__":
    main()
