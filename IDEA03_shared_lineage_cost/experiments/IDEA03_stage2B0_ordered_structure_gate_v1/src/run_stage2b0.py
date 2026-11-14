from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import os
import platform
import sys
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "stage2b0_protocol.json"
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"


@dataclass(frozen=True)
class Factor:
    scope: tuple[str, ...]
    values: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.values) != 1 << len(self.scope):
            raise ValueError("factor table size does not match scope")


def bit(index: int, position: int, width: int) -> int:
    return (index >> (width - position - 1)) & 1


def assignment_index(scope: tuple[str, ...], assignment: dict[str, int]) -> int:
    value = 0
    for var in scope:
        value = (value << 1) | assignment[var]
    return value


def multiply(factors: list[Factor], counters: dict[str, int]) -> Factor:
    if not factors:
        return Factor((), (1,))
    scope = tuple(dict.fromkeys(v for f in factors for v in f.scope))
    out = []
    width = len(scope)
    counters["factor_products"] += 1
    counters["generated_product_cells"] += 1 << width
    for row in range(1 << width):
        a = {v: bit(row, i, width) for i, v in enumerate(scope)}
        value = 1
        for f in factors:
            value *= f.values[assignment_index(f.scope, a)]
            counters["multiplications"] += 1
        out.append(value)
    return Factor(scope, tuple(out))


def sum_out(factor: Factor, var: str, counters: dict[str, int]) -> Factor:
    position = factor.scope.index(var)
    scope = factor.scope[:position] + factor.scope[position + 1 :]
    out = []
    width = len(scope)
    counters["generated_sum_cells"] += 1 << width
    for row in range(1 << width):
        a = {v: bit(row, i, width) for i, v in enumerate(scope)}
        a[var] = 0
        lo = factor.values[assignment_index(factor.scope, a)]
        a[var] = 1
        hi = factor.values[assignment_index(factor.scope, a)]
        out.append(lo + hi)
        counters["additions"] += 1
    return Factor(scope, tuple(out))


def witness_factors(assignment: tuple[int, ...]) -> list[Factor]:
    factors: list[Factor] = []
    for site, enterprise in enumerate(assignment):
        scope = (f"Y{site + 1}", f"E{enterprise + 1}", f"B{site + 1}", f"H{site + 1}")
        values = []
        for row in range(16):
            y, e, b, h = (bit(row, i, 4) for i in range(4))
            values.append(int(y == (e & b & h)))
        factors.append(Factor(scope, tuple(values)))
    y_scope = tuple(f"Y{i + 1}" for i in range(6))
    factors.append(Factor(y_scope, tuple(int(row != 0) for row in range(64))))
    return factors


def player_name(index: int) -> str:
    if index < 4:
        return f"E{index + 1}"
    if index < 10:
        return f"B{index - 3}"
    return f"H{index - 9}"


def player_graph(assignment: tuple[int, ...]) -> dict[str, set[str]]:
    graph = {player_name(i): set() for i in range(16)}
    for site, enterprise in enumerate(assignment):
        clause = [f"E{enterprise + 1}", f"B{site + 1}", f"H{site + 1}"]
        for a, b in itertools.combinations(clause, 2):
            graph[a].add(b)
            graph[b].add(a)
    return graph


def min_fill_order(graph: dict[str, set[str]], key_index: dict[str, int] | None = None) -> tuple[list[str], int]:
    g = {v: set(ns) for v, ns in graph.items()}
    order: list[str] = []
    width = 0
    if key_index is None:
        key_index = {v: i for i, v in enumerate(sorted(g))}
    while g:
        def score(v: str) -> tuple[int, int, int]:
            ns = list(g[v])
            missing = sum(1 for a, b in itertools.combinations(ns, 2) if b not in g[a])
            return missing, len(ns), key_index.get(v, 10**9)
        v = min(g, key=score)
        ns = list(g[v])
        width = max(width, len(ns))
        for a, b in itertools.combinations(ns, 2):
            g[a].add(b)
            g[b].add(a)
        for n in ns:
            g[n].discard(v)
        del g[v]
        order.append(v)
    return order, width


def component_order(assignment: tuple[int, ...]) -> list[str]:
    order: list[str] = []
    for enterprise in range(4):
        sites = [site for site, e in enumerate(assignment) if e == enterprise]
        for site in sites:
            order.extend([f"B{site + 1}", f"H{site + 1}"])
        order.append(f"E{enterprise + 1}")
    return order


def order_for(name: str, assignment: tuple[int, ...]) -> tuple[list[str], int]:
    graph = player_graph(assignment)
    if name == "PHYSICAL_E_B_H":
        return [player_name(i) for i in range(16)], -1
    if name == "MIN_FILL_SOURCE":
        return min_fill_order(graph, {player_name(i): i for i in range(16)})
    if name == "ENTERPRISE_COMPONENT_GROUPED":
        return component_order(assignment), -1
    raise KeyError(name)


def inclusion_exclusion_count(assignment: tuple[int, ...]) -> int:
    clauses = []
    for site, enterprise in enumerate(assignment):
        clauses.append({f"E{enterprise + 1}", f"B{site + 1}", f"H{site + 1}"})
    count = 0
    for mask in range(1, 1 << len(clauses)):
        union: set[str] = set()
        chosen = 0
        for i, clause in enumerate(clauses):
            if mask & (1 << i):
                union.update(clause)
                chosen += 1
        term = 1 << (16 - len(union))
        count += term if chosen % 2 else -term
    return count


def run_ve(assignment: tuple[int, ...], order_name: str) -> dict[str, object]:
    order, source_min_fill_width = order_for(order_name, assignment)
    full_order = order + [f"Y{i + 1}" for i in range(6)]
    factors = witness_factors(assignment)
    counters = {
        "factor_products": 0,
        "generated_product_cells": 0,
        "generated_sum_cells": 0,
        "multiplications": 0,
        "additions": 0,
    }
    max_frontier = 0
    max_product_cells = 0
    max_output_cells = 0
    player_max_frontier = 0
    player_max_product_cells = 0
    player_max_output_cells = 0
    tracemalloc.start()
    started = time.perf_counter_ns()
    for step, var in enumerate(full_order):
        selected = [f for f in factors if var in f.scope]
        factors = [f for f in factors if var not in f.scope]
        if not selected:
            continue
        product = multiply(selected, counters)
        reduced = sum_out(product, var, counters)
        factors.append(reduced)
        frontier = len(product.scope) - 1
        max_frontier = max(max_frontier, frontier)
        max_product_cells = max(max_product_cells, len(product.values))
        max_output_cells = max(max_output_cells, len(reduced.values))
        if step < 16:
            player_max_frontier = max(player_max_frontier, frontier)
            player_max_product_cells = max(player_max_product_cells, len(product.values))
            player_max_output_cells = max(player_max_output_cells, len(reduced.values))
    final = multiply(factors, counters)
    elapsed_ns = time.perf_counter_ns() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if final.scope:
        raise AssertionError(f"VE did not eliminate all variables: {final.scope}")
    independent = inclusion_exclusion_count(assignment)
    return {
        "order_name": order_name,
        "order": "|".join(order),
        "source_min_fill_width": source_min_fill_width if source_min_fill_width >= 0 else "NOT_APPLICABLE",
        "model_count_ve": final.values[0],
        "model_count_inclusion_exclusion": independent,
        "exact_match": final.values[0] == independent,
        "max_frontier": max_frontier,
        "max_product_factor_cells": max_product_cells,
        "max_output_factor_cells": max_output_cells,
        "player_phase_max_frontier": player_max_frontier,
        "player_phase_max_product_factor_cells": player_max_product_cells,
        "player_phase_max_output_factor_cells": player_max_output_cells,
        "generated_factor_cells": counters["generated_product_cells"] + counters["generated_sum_cells"],
        "factor_products": counters["factor_products"],
        "multiplications": counters["multiplications"],
        "additions": counters["additions"],
        "cold_compile_ns": elapsed_ns,
        "peak_tracemalloc_bytes": peak,
        "compiled_nodes": "NOT_EXPOSED_REFERENCE_VE",
        "nonterminal_nodes": "NOT_EXPOSED_REFERENCE_VE",
    }


def enterprise_counts(assignment: tuple[int, ...], sites: list[dict[str, object]]) -> dict[str, int]:
    groups: dict[str, set[int]] = {g: set() for g in ["NAT", "PA", "PB", "A1", "A2", "B1", "B2"]}
    for site, enterprise in zip(sites, assignment):
        groups["NAT"].add(enterprise)
        groups[str(site["province"])].add(enterprise)
        groups[str(site["city"])].add(enterprise)
    return {g: len(es) for g, es in groups.items()}


def canonicalize(assignment: tuple[int, ...]) -> tuple[int, ...]:
    mapping: dict[int, int] = {}
    next_label = 0
    out = []
    for e in assignment:
        if e not in mapping:
            mapping[e] = next_label
            next_label += 1
        out.append(mapping[e])
    return tuple(out)


def assignment_features(assignment: tuple[int, ...], sites: list[dict[str, object]]) -> dict[str, object]:
    degrees = [assignment.count(e) for e in range(4)]
    cross_province = 0
    cross_city = 0
    for e in range(4):
        positions = [i for i, x in enumerate(assignment) if x == e]
        if len({sites[i]["province"] for i in positions}) > 1:
            cross_province += 1
        if len({sites[i]["city"] for i in positions}) > 1:
            cross_city += 1
    graph = player_graph(assignment)
    _, width = min_fill_order(graph, {player_name(i): i for i in range(16)})
    return {
        "assignment": "|".join(str(x) for x in assignment),
        "degree_sequence": "|".join(map(str, sorted(degrees, reverse=True))),
        "max_enterprise_degree": max(degrees),
        "cross_province_enterprises": cross_province,
        "cross_city_enterprises": cross_city,
        "witness_count": 6,
        "dnf_clause_count": 6,
        "variable_occurrences": 18,
        "connected_components": 4,
        "largest_component_players": 1 + 2 * max(degrees),
        "incidence_treewidth_exact": 1,
        "primal_treewidth_exact": 2,
        "min_fill_width": width,
    }


def coordinate_dependencies(sites: list[dict[str, object]]) -> tuple[list[str], dict[str, set[int]]]:
    metrics = ["enterprise_count", "site_count", "workers", "mfg_workers", "mfg_share"]
    geos = ["NAT", "PA", "PB", "A1", "A2", "B1", "B2"]
    coords = [f"{g}:{m}" for g in geos for m in metrics]
    dependencies = {c: set() for c in coords}
    for i, site in enumerate(sites):
        relevant = ["NAT", str(site["province"]), str(site["city"])]
        for geo in relevant:
            for metric in ["enterprise_count", "site_count", "workers", "mfg_share"]:
                dependencies[f"{geo}:{metric}"].add(i)
            if site["industry"] == "mfg":
                dependencies[f"{geo}:mfg_workers"].add(i)
    return coords, dependencies


def source_coordinate_metrics(assignment: tuple[int, ...], sites: list[dict[str, object]]) -> tuple[dict[str, object], list[dict[str, object]]]:
    coords, dependencies = coordinate_dependencies(sites)
    witness_degrees = [sum(i in dependencies[c] for c in coords) for i in range(6)]
    player_coords: dict[str, set[str]] = {player_name(i): set() for i in range(16)}
    for coord, witness_sites in dependencies.items():
        for site in witness_sites:
            player_coords[f"E{assignment[site] + 1}"].add(coord)
            player_coords[f"B{site + 1}"].add(coord)
            player_coords[f"H{site + 1}"].add(coord)
    graph: dict[str, set[str]] = {}
    for p in player_coords:
        graph[f"P:{p}"] = set()
    for c in coords:
        graph[f"C:{c}"] = set()
    for p, pcs in player_coords.items():
        for c in pcs:
            graph[f"P:{p}"].add(f"C:{c}")
            graph[f"C:{c}"].add(f"P:{p}")
    _, graph_width = min_fill_order(graph)
    coordinate_source_sets = [tuple(sorted(dependencies[c])) for c in coords]
    summary = {
        "player_coordinate_edges": sum(len(v) for v in player_coords.values()),
        "max_player_coordinate_degree": max(map(len, player_coords.values())),
        "max_enterprise_coordinate_degree": max(len(player_coords[f"E{i}"]) for i in range(1, 5)),
        "max_witness_coordinate_degree": max(witness_degrees),
        "max_coordinate_witness_degree": max(map(len, dependencies.values())),
        "unique_coordinate_witness_source_sets": len(set(coordinate_source_sets)),
        "identical_coordinate_source_groups": sum(1 for s in set(coordinate_source_sets) if coordinate_source_sets.count(s) > 1),
        "source_coordinate_components": connected_components(graph),
        "source_coordinate_min_fill_width_upper_bound": graph_width,
    }
    rows = []
    for c in coords:
        rows.append({
            "coordinate": c,
            "witness_degree": len(dependencies[c]),
            "witness_sites": "|".join(f"S{i + 1}" for i in sorted(dependencies[c])),
        })
    return summary, rows


def connected_components(graph: dict[str, set[str]]) -> int:
    remaining = set(graph)
    count = 0
    while remaining:
        count += 1
        stack = [remaining.pop()]
        while stack:
            v = stack.pop()
            for n in graph[v]:
                if n in remaining:
                    remaining.remove(n)
                    stack.append(n)
    return count


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"refusing to write empty result: {path}")
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    sites = cfg["sites"]
    required = cfg["required_full_report_enterprise_counts"]
    all_valid = []
    reps: dict[tuple[int, ...], tuple[int, ...]] = {}
    for a in itertools.product(range(4), repeat=6):
        if enterprise_counts(a, sites) == required:
            all_valid.append(a)
            reps.setdefault(canonicalize(a), a)
    if len(all_valid) != 288 or len(reps) != 12:
        raise AssertionError((len(all_valid), len(reps)))

    strict_map = {name: tuple(value) for name, value in cfg["strict_instances"].items()}
    structure_rows = []
    compilation_rows = []
    coordinate_summary_rows = []
    coordinate_detail_rows: list[dict[str, object]] = []
    for rep_id, canonical in enumerate(sorted(reps), 1):
        labels = [name for name, a in strict_map.items() if canonicalize(a) == canonical]
        label = "|".join(labels) if labels else "systematic_representative"
        features = assignment_features(canonical, sites)
        coord_summary, coord_details = source_coordinate_metrics(canonical, sites)
        row = {"representative_id": f"R{rep_id:02d}", "fixture_label": label, **features, **coord_summary}
        structure_rows.append(row)
        coordinate_summary_rows.append({"representative_id": f"R{rep_id:02d}", "fixture_label": label, **coord_summary})
        for d in coord_details:
            coordinate_detail_rows.append({"representative_id": f"R{rep_id:02d}", **d})
        for order_name in cfg["orders"]:
            result = run_ve(canonical, order_name)
            compilation_rows.append({
                "representative_id": f"R{rep_id:02d}",
                "fixture_label": label,
                "degree_sequence": features["degree_sequence"],
                "max_enterprise_degree": features["max_enterprise_degree"],
                **result,
            })

    labelled_rows = []
    for a in all_valid:
        labelled_rows.append({
            "assignment": "|".join(map(str, a)),
            "canonical_representative": "|".join(map(str, canonicalize(a))),
            **enterprise_counts(a, sites),
        })
    validation_rows = []
    for row in compilation_rows:
        validation_rows.append({
            "representative_id": row["representative_id"],
            "order_name": row["order_name"],
            "model_count_ve": row["model_count_ve"],
            "model_count_inclusion_exclusion": row["model_count_inclusion_exclusion"],
            "exact_match": row["exact_match"],
            "semantic_validator": "6-clause DNF inclusion-exclusion; no coalition truth table",
        })
    if not all(r["exact_match"] for r in validation_rows):
        raise AssertionError("reference VE semantic validation failed")

    write_csv(RESULTS / "legal_labelled_assignments.csv", labelled_rows)
    write_csv(RESULTS / "structure_space.csv", structure_rows)
    write_csv(RESULTS / "ordered_compilation.csv", compilation_rows)
    write_csv(RESULTS / "semantic_validation.csv", validation_rows)
    write_csv(RESULTS / "source_coordinate_summary.csv", coordinate_summary_rows)
    write_csv(RESULTS / "source_coordinate_details.csv", coordinate_detail_rows)

    manifest = {
        "status": "VERIFIED",
        "implementation_status": cfg["implementation_status"],
        "python": sys.version,
        "platform": platform.platform(),
        "pid": os.getpid(),
        "candidate_assignments": 4**6,
        "legal_labelled_assignments": len(all_valid),
        "nonisomorphic_representatives": len(reps),
        "compilation_runs": len(compilation_rows),
        "orders": cfg["orders"],
        "no_new_dependency": True,
        "no_full_coalition_enumeration": True,
        "config_sha256": sha256(CONFIG),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / "run_events.jsonl").write_text(json.dumps({"event": "run_complete", **manifest}, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
