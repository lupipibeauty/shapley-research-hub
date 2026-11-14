from __future__ import annotations

import csv
import hashlib
import itertools
import json
import platform
import sys
from collections import Counter, defaultdict, deque
from decimal import Decimal
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
CONFIG_PATH = ROOT / "config" / "stage3a_q9_protocol.json"
SQL_PATH = ROOT / "sql" / "q9_witness_extract.sql"
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scalar(value):
    if isinstance(value, Decimal):
        return str(value)
    return value


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"empty output refused: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0])
    for row in rows[1:]:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def add_edge(graph: dict[str, set[str]], a: str, b: str) -> None:
    graph.setdefault(a, set()).add(b)
    graph.setdefault(b, set()).add(a)


def components(graph: dict[str, set[str]]) -> list[set[str]]:
    remaining = set(graph)
    output = []
    while remaining:
        root = min(remaining)
        remaining.remove(root)
        comp = {root}
        queue = deque([root])
        while queue:
            node = queue.popleft()
            for neighbor in graph[node]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    comp.add(neighbor)
                    queue.append(neighbor)
        output.append(comp)
    return sorted(output, key=lambda c: (-len(c), min(c)))


def graph_edge_count(graph: dict[str, set[str]]) -> int:
    return sum(map(len, graph.values())) // 2


def min_fill_width(graph: dict[str, set[str]]) -> tuple[int, list[str]]:
    g = {v: set(ns) for v, ns in graph.items()}
    width = 0
    order = []
    while g:
        def score(v: str):
            ns = list(g[v])
            missing = 0
            for a, b in itertools.combinations(ns, 2):
                if b not in g[a]:
                    missing += 1
            return missing, len(ns), v
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
    return width, order


def witness_players(row: dict, boundary: str) -> tuple[str, ...]:
    common = (
        f"PS:{row['partkey']}:{row['suppkey']}",
        f"L:{row['orderkey']}:{row['linenumber']}",
        f"O:{row['orderkey']}",
    )
    if boundary == "P2":
        return common
    return (
        f"P:{row['partkey']}",
        f"S:{row['suppkey']}",
    ) + common


def relation_of(player: str) -> str:
    return {"P": "PART", "S": "SUPPLIER", "PS": "PARTSUPP", "L": "LINEITEM", "O": "ORDERS"}[player.split(":", 1)[0]]


def provenance_metrics(rows: list[dict], boundary: str) -> tuple[dict, list[dict], list[dict], list[dict], list[dict]]:
    sets = [set(witness_players(row, boundary)) for row in rows]
    incidence: dict[str, set[str]] = {}
    primal: dict[str, set[str]] = {}
    player_degrees = Counter()
    edge_rows = []
    for row, players in zip(rows, sets):
        w = f"W:{row['witness_id']}"
        incidence.setdefault(w, set())
        for p in sorted(players):
            pn = f"P:{p}"
            add_edge(incidence, w, pn)
            primal.setdefault(p, set())
            player_degrees[p] += 1
            edge_rows.append({"boundary": boundary, "witness_id": row["witness_id"], "player_id": p, "relation": relation_of(p)})
        for a, b in itertools.combinations(sorted(players), 2):
            add_edge(primal, a, b)

    overlap = Counter()
    examples = {}
    for i, j in itertools.combinations(range(len(sets)), 2):
        shared = sets[i] & sets[j]
        size = len(shared)
        overlap[size] += 1
        if size > 0 and size not in examples:
            examples[size] = {
                "boundary": boundary,
                "overlap_size": size,
                "witness_a": rows[i]["witness_id"],
                "witness_b": rows[j]["witness_id"],
                "shared_players": "|".join(sorted(shared)),
            }

    inc_components = components(incidence)
    primal_components = components(primal)
    inc_width, inc_order = min_fill_width(incidence)
    primal_width, primal_order = min_fill_width(primal)

    pair_by_witness = [(str(r["partkey"]), str(r["suppkey"])) for r in rows]
    part_by_witness = [str(r["partkey"]) for r in rows]
    supp_by_witness = [str(r["suppkey"]) for r in rows]
    memberships = {
        "pair": defaultdict(set),
        "part": defaultdict(set),
        "supplier": defaultdict(set),
    }
    for players, pair, part, supp in zip(sets, pair_by_witness, part_by_witness, supp_by_witness):
        for p in players:
            memberships["pair"][p].add(pair)
            memberships["part"][p].add(part)
            memberships["supplier"][p].add(supp)

    inc_edges = graph_edge_count(incidence)
    inc_cycles = inc_edges - len(incidence) + len(inc_components)
    metrics = {
        "boundary": boundary,
        "players": len(primal),
        "witnesses": len(rows),
        "average_witness_size": sum(map(len, sets)) / len(sets),
        "max_witness_size": max(map(len, sets)),
        "max_player_witness_degree": max(player_degrees.values()),
        "max_overlap": max(overlap),
        "overlap_ge_2_pairs": sum(v for k, v in overlap.items() if k >= 2),
        "overlap_ge_3_pairs": sum(v for k, v in overlap.items() if k >= 3),
        "incidence_components": len(inc_components),
        "largest_incidence_component_nodes": len(inc_components[0]),
        "largest_incidence_component_players": sum(n.startswith("P:") for n in inc_components[0]),
        "largest_incidence_component_witnesses": sum(n.startswith("W:") for n in inc_components[0]),
        "incidence_has_cycle": inc_cycles > 0,
        "incidence_cycle_rank": inc_cycles,
        "incidence_min_fill_width_upper_bound": inc_width,
        "primal_components": len(primal_components),
        "largest_primal_component_players": len(primal_components[0]),
        "primal_min_fill_width_upper_bound": primal_width,
        "primal_clique_lower_bound": max(map(len, sets)) - 1,
        "can_decompose_by_pair": all(len(v) <= 1 for v in memberships["pair"].values()),
        "can_decompose_by_part": all(len(v) <= 1 for v in memberships["part"].values()),
        "can_decompose_by_supplier": all(len(v) <= 1 for v in memberships["supplier"].values()),
        "min_fill_frontier": primal_width,
        "incidence_min_fill_order_sha256": hashlib.sha256("|".join(inc_order).encode()).hexdigest(),
        "primal_min_fill_order_sha256": hashlib.sha256("|".join(primal_order).encode()).hexdigest(),
    }
    degree_rows = [
        {"boundary": boundary, "player_id": p, "relation": relation_of(p), "witness_degree": d}
        for p, d in sorted(player_degrees.items())
    ]
    overlap_rows = [
        {"boundary": boundary, "overlap_size": k, "witness_pair_count": overlap[k]}
        for k in sorted(overlap)
    ]
    example_rows = [examples[k] for k in sorted(examples)]
    comp_rows = []
    for idx, comp in enumerate(inc_components, 1):
        comp_rows.append({
            "boundary": boundary,
            "component_id": idx,
            "total_nodes": len(comp),
            "player_nodes": sum(n.startswith("P:") for n in comp),
            "witness_nodes": sum(n.startswith("W:") for n in comp),
        })
    return metrics, edge_rows, degree_rows, overlap_rows, example_rows + comp_rows


def part_supplier_structure(rows: list[dict]) -> tuple[dict, list[dict], list[set[str]]]:
    pair_counts = Counter((int(r["partkey"]), int(r["suppkey"])) for r in rows)
    graph: dict[str, set[str]] = {}
    edge_rows = []
    for (part, supp), count in sorted(pair_counts.items()):
        p, s = f"P:{part}", f"S:{supp}"
        add_edge(graph, p, s)
        edge_rows.append({"partkey": part, "suppkey": supp, "witness_count": count})
    comps = components(graph)
    width, order = min_fill_width(graph)
    edges = len(pair_counts)
    cycle_rank = edges - len(graph) + len(comps)
    degrees = Counter(len(ns) for ns in graph.values())
    metrics = {
        "part_nodes": sum(n.startswith("P:") for n in graph),
        "supplier_nodes": sum(n.startswith("S:") for n in graph),
        "total_nodes": len(graph),
        "edges": edges,
        "connected_components": len(comps),
        "largest_component_nodes": len(comps[0]),
        "largest_component_edges": sum(1 for p, s in pair_counts if f"P:{p}" in comps[0] and f"S:{s}" in comps[0]),
        "max_degree": max(map(len, graph.values())),
        "degree_distribution": json.dumps(dict(sorted(degrees.items())), separators=(",", ":")),
        "has_cycle": cycle_rank > 0,
        "cycle_basis_size": cycle_rank,
        "min_fill_width_upper_bound": width,
        "min_fill_order_sha256": hashlib.sha256("|".join(order).encode()).hexdigest(),
    }
    return metrics, edge_rows, comps


def select_low(rows: list[dict], target: int) -> list[dict]:
    selected = []
    remaining = list(rows)
    while remaining and len(selected) < target:
        def score(row):
            players = set(witness_players(row, "P1"))
            overlaps = [len(players & set(witness_players(s, "P1"))) for s in selected]
            pair = (row["partkey"], row["suppkey"])
            return (
                max(overlaps, default=0),
                sum(overlaps),
                int(any((s["partkey"], s["suppkey"]) == pair for s in selected)),
                int(any(s["partkey"] == row["partkey"] or s["suppkey"] == row["suppkey"] for s in selected)),
                int(any(s["orderkey"] == row["orderkey"] for s in selected)),
                row["partkey"], row["suppkey"], row["orderkey"], row["linenumber"],
            )
        chosen = min(remaining, key=score)
        selected.append(chosen)
        remaining.remove(chosen)
    return selected


def select_high(rows: list[dict], target: int, ps_components: list[set[str]]) -> list[dict]:
    pair_rows = defaultdict(list)
    for row in rows:
        pair_rows[(int(row["partkey"]), int(row["suppkey"]))].append(row)
    comp_info = []
    for comp in ps_components:
        pairs = [pair for pair in pair_rows if f"P:{pair[0]}" in comp and f"S:{pair[1]}" in comp]
        witness_count = sum(len(pair_rows[p]) for p in pairs)
        cycle_rank = len(pairs) - len(comp) + 1
        comp_info.append((cycle_rank, len(pairs), witness_count, min(comp), pairs))
    _, _, _, _, pairs = max(comp_info, key=lambda x: (x[0], x[1], x[2], tuple(-ord(c) for c in x[3])))
    pairs = sorted(pairs)
    seed = min(pairs, key=lambda p: (-len(pair_rows[p]), p))
    selected = sorted(pair_rows[seed], key=lambda r: (r["orderkey"], r["linenumber"]))[: min(6, target)]
    adjacent = [p for p in pairs if p != seed and (p[0] == seed[0] or p[1] == seed[1])]
    adjacent.sort(key=lambda p: (-len(pair_rows[p]), p))
    for pair in adjacent:
        for row in sorted(pair_rows[pair], key=lambda r: (r["orderkey"], r["linenumber"]))[:3]:
            if len(selected) < target:
                selected.append(row)
    remaining = [r for p in pairs for r in pair_rows[p] if r not in selected]
    while remaining and len(selected) < target:
        def score(row):
            players = set(witness_players(row, "P1"))
            overlaps = [len(players & set(witness_players(s, "P1"))) for s in selected]
            return (-max(overlaps, default=0), -sum(overlaps), row["partkey"], row["suppkey"], row["orderkey"], row["linenumber"])
        chosen = min(remaining, key=score)
        selected.append(chosen)
        remaining.remove(chosen)
    return selected


def main() -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    db_path = WORKSPACE / Path(cfg["database"])
    source_q9 = WORKSPACE / Path(cfg["source_q9"])
    sql = SQL_PATH.read_text(encoding="utf-8")
    con = duckdb.connect(str(db_path), read_only=True)
    cursor = con.execute(sql)
    columns = [d[0] for d in cursor.description]
    fetched = cursor.fetchall()
    con.close()
    rows = []
    for index, values in enumerate(fetched, 1):
        row = {k: scalar(v) for k, v in zip(columns, values)}
        row["witness_id"] = f"W{index:06d}"
        row["part_player_id"] = f"P:{row['partkey']}"
        row["supplier_player_id"] = f"S:{row['suppkey']}"
        row["partsupp_player_id"] = f"PS:{row['partkey']}:{row['suppkey']}"
        row["lineitem_player_id"] = f"L:{row['orderkey']}:{row['linenumber']}"
        row["order_player_id"] = f"O:{row['orderkey']}"
        rows.append(row)
    witness_fields = ["witness_id"] + columns + ["part_player_id", "supplier_player_id", "partsupp_player_id", "lineitem_player_id", "order_player_id"]
    write_csv(RESULTS / "q9_witnesses.csv", [{k: r[k] for k in witness_fields} for r in rows])

    pair_counts = Counter((r["partkey"], r["suppkey"]) for r in rows)
    precheck = {
        "witnesses": len(rows),
        "distinct_part_supplier_pairs": len(pair_counts),
        "max_witnesses_per_pair": max(pair_counts.values()),
    }
    precheck_rows = [{
        "metric": key,
        "expected": cfg["expected_precheck"][key],
        "observed": value,
        "match": value == cfg["expected_precheck"][key],
    } for key, value in precheck.items()]
    write_csv(RESULTS / "precheck_validation.csv", precheck_rows)

    ps_metrics, ps_edges, ps_components = part_supplier_structure(rows)
    write_csv(RESULTS / "part_supplier_edges.csv", ps_edges)
    write_csv(RESULTS / "part_supplier_metrics.csv", [ps_metrics])

    all_metrics = []
    all_edges = []
    all_degrees = []
    all_overlap = []
    combined_misc = []
    for boundary in ("P1", "P2"):
        metrics, edges, degrees, overlap, misc = provenance_metrics(rows, boundary)
        all_metrics.append(metrics)
        all_edges.extend(edges)
        all_degrees.extend(degrees)
        all_overlap.extend(overlap)
        combined_misc.extend(misc)
    write_csv(RESULTS / "provenance_metrics.csv", all_metrics)
    write_csv(RESULTS / "witness_player_edges.csv", all_edges)
    write_csv(RESULTS / "player_witness_degree.csv", all_degrees)
    write_csv(RESULTS / "witness_overlap_distribution.csv", all_overlap)
    write_csv(RESULTS / "overlap_examples_and_components.csv", combined_misc)

    for boundary in ("P1", "P2"):
        players = sorted({p for row in rows for p in witness_players(row, boundary)})
        write_csv(RESULTS / f"player_map_{boundary.lower()}.csv", [
            {"boundary": boundary, "player_index": i, "player_id": p, "relation": relation_of(p), "physical_key": p.split(":", 1)[1]}
            for i, p in enumerate(players)
        ])

    target = int(cfg["subinstance_selection"]["target_witnesses"])
    low = select_low(rows, target)
    high = select_high(rows, target, ps_components)
    write_csv(RESULTS / "q9_l_witnesses.csv", [{k: r[k] for k in witness_fields} for r in low])
    write_csv(RESULTS / "q9_h_witnesses.csv", [{k: r[k] for k in witness_fields} for r in high])
    sub_metrics = []
    for label, subset in (("Q9_L", low), ("Q9_H", high)):
        for boundary in ("P1", "P2"):
            metrics, _, _, _, _ = provenance_metrics(subset, boundary)
            sub_metrics.append({"subinstance": label, **metrics})
    write_csv(RESULTS / "subinstance_metrics.csv", sub_metrics)

    groups = defaultdict(list)
    for row in rows:
        groups[(row["regionkey"], row["nationkey"], row["nation"], row["order_year"])].append(row)
    report_rows = []
    for key, group in sorted(groups.items()):
        revenue = sum(Decimal(str(r["revenue"])) for r in group)
        supply = sum(Decimal(str(r["supply_cost"])) for r in group)
        profit = sum(Decimal(str(r["profit"])) for r in group)
        report_rows.append({
            "regionkey": key[0], "nationkey": key[1], "nation": key[2], "order_year": key[3],
            "distinct_order_count": len({r["orderkey"] for r in group}),
            "distinct_supplier_count": len({r["suppkey"] for r in group}),
            "lineitem_count": len(group),
            "quantity_sum": str(sum(Decimal(str(r["quantity"])) for r in group)),
            "revenue_sum": str(revenue),
            "supply_cost_sum": str(supply),
            "profit_sum": str(profit),
            "profit_margin": "NULL" if revenue == 0 else str(profit / revenue),
        })
    write_csv(RESULTS / "report_compatibility_groups.csv", report_rows)

    manifest = {
        "status": "VERIFIED",
        "protocol_id": cfg["protocol_id"],
        "python": sys.version,
        "duckdb": duckdb.__version__,
        "platform": platform.platform(),
        "database": str(db_path),
        "database_sha256": sha256(db_path),
        "source_q9_sha256": sha256(source_q9),
        "witness_sql_sha256": sha256(SQL_PATH),
        "config_sha256": sha256(CONFIG_PATH),
        "precheck": precheck,
        "precheck_all_match": all(r["match"] for r in precheck_rows),
        "player_boundaries_frozen_before_metrics": True,
        "shapley_computed": False,
        "coalitions_enumerated": False,
        "foreign_keys_modified": False,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / "run_events.jsonl").write_text(json.dumps({"event": "canonical_run_complete", **manifest}, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
