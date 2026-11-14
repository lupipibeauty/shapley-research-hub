from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import platform
import sys
import time
import tracemalloc
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT.parent
WORKSPACE = ROOT.parents[2]
STAGE3A = EXPERIMENTS / "IDEA03_stage3A_q9_nonstar_gate_v1"
STAGE2A = EXPERIMENTS / "IDEA03_stage2A_mature_source_compilation_20261113"
OFFICIAL = WORKSPACE / "aggregate_report_shapley" / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
CONFIG = ROOT / "config" / "stage3b1_protocol.json"
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"

sys.path.insert(0, str(OFFICIAL))

from Algorithms.LExaShap.ShapleyCircuit import DNFCircuit, DNFCircuitNode, lift_recursively  # noqa: E402
from Algorithms.LExaShap.ShapleyEngine import Value  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"empty output refused: {path}")
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def log_event(event: str, **payload) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "run_events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": event, "time": time.time(), **payload}, ensure_ascii=False) + "\n")


def player_ids(row: dict[str, str], boundary: str) -> tuple[str, ...]:
    common = (row["partsupp_player_id"], row["lineitem_player_id"], row["order_player_id"])
    if boundary == "P2":
        return common
    return (row["part_player_id"], row["supplier_player_id"]) + common


def relation(player: str) -> str:
    prefix = player.split(":", 1)[0]
    return {"P": "PART", "S": "SUPPLIER", "PS": "PARTSUPP", "L": "LINEITEM", "O": "ORDERS"}[prefix]


def add_edge(graph: dict[str, set[str]], left: str, right: str) -> None:
    graph.setdefault(left, set()).add(right)
    graph.setdefault(right, set()).add(left)


def connected_components(graph: dict[str, set[str]]) -> list[set[str]]:
    remaining = set(graph)
    output = []
    while remaining:
        root = min(remaining)
        remaining.remove(root)
        comp = {root}
        queue = deque([root])
        while queue:
            current = queue.popleft()
            for neighbor in graph[current]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    comp.add(neighbor)
                    queue.append(neighbor)
        output.append(comp)
    return sorted(output, key=lambda c: (min(c), len(c)))


def min_fill_order(graph: dict[str, set[str]]) -> tuple[list[str], int]:
    g = {node: set(neighbors) for node, neighbors in graph.items()}
    order: list[str] = []
    width = 0
    while g:
        def score(node: str):
            neighbors = list(g[node])
            missing = sum(1 for a, b in itertools.combinations(neighbors, 2) if b not in g[a])
            return missing, len(neighbors), node
        node = min(g, key=score)
        neighbors = list(g[node])
        width = max(width, len(neighbors))
        for a, b in itertools.combinations(neighbors, 2):
            g[a].add(b)
            g[b].add(a)
        for neighbor in neighbors:
            g[neighbor].discard(node)
        del g[node]
        order.append(node)
    return order, width


def build_graphs(clauses: list[tuple[str, ...]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    incidence: dict[str, set[str]] = {}
    primal: dict[str, set[str]] = {}
    for index, clause in enumerate(clauses, 1):
        witness = f"W:{index}"
        incidence.setdefault(witness, set())
        for player in clause:
            add_edge(incidence, witness, f"P:{player}")
            primal.setdefault(player, set())
        for left, right in itertools.combinations(clause, 2):
            add_edge(primal, left, right)
    return incidence, primal


def structure_metrics(object_id: str, family: str, m: int, boundary: str, clauses: list[tuple[str, ...]]) -> dict:
    incidence, primal = build_graphs(clauses)
    overlaps = Counter(len(set(a) & set(b)) for a, b in itertools.combinations(clauses, 2))
    inc_components = connected_components(incidence)
    primal_components = connected_components(primal)
    _, inc_width = min_fill_order(incidence)
    _, primal_width = min_fill_order(primal)
    degrees = Counter(player for clause in clauses for player in clause)
    inc_edges = sum(map(len, incidence.values())) // 2
    cycle_rank = inc_edges - len(incidence) + len(inc_components)
    return {
        "object_id": object_id,
        "family": family,
        "m": m,
        "boundary": boundary,
        "players": len(primal),
        "witnesses": len(clauses),
        "witness_size": len(clauses[0]),
        "literal_occurrences": sum(map(len, clauses)),
        "max_player_witness_degree": max(degrees.values()),
        "max_witness_overlap": max(overlaps, default=0),
        "overlap_ge_2_pairs": sum(count for overlap, count in overlaps.items() if overlap >= 2),
        "connected_components": len(primal_components),
        "largest_primal_component_players": max(map(len, primal_components)),
        "incidence_cycle_rank": cycle_rank,
        "incidence_min_fill_width_upper_bound": inc_width,
        "primal_min_fill_width_upper_bound": primal_width,
        "primal_clique_lower_bound": len(clauses[0]) - 1,
    }


def tree_metrics(root) -> dict[str, int]:
    queue = deque([(root, 0)])
    nodes = leaves = depth_max = 0
    widths = Counter()
    while queue:
        node, depth = queue.popleft()
        nodes += 1
        widths[depth] += 1
        depth_max = max(depth_max, depth)
        children = list(node.children) if node.children else []
        if not children:
            leaves += 1
        for child in children:
            queue.append((child, depth + 1))
    return {
        "dtree_shell_nodes": nodes,
        "dtree_shell_leaves": leaves,
        "dtree_shell_depth": depth_max,
        "dtree_shell_max_layer_width": max(widths.values(), default=0),
    }


def value_dag_nodes(value) -> int:
    seen = set()
    stack = [value]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        stack.extend(current._prev)
    return len(seen)


def process_memory() -> dict[str, int | str]:
    if platform.system() != "Windows":
        return {"working_set_bytes": "UNAVAILABLE", "peak_working_set_bytes": "UNAVAILABLE"}
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = PMC()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_current_process.restype = wintypes.HANDLE
        get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
        get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        get_memory.restype = wintypes.BOOL
        handle = get_current_process()
        ok = get_memory(handle, ctypes.byref(counters), counters.cb)
        if not ok:
            raise OSError("GetProcessMemoryInfo failed")
        return {"working_set_bytes": int(counters.WorkingSetSize), "peak_working_set_bytes": int(counters.PeakWorkingSetSize)}
    except Exception as exc:
        return {"working_set_bytes": f"UNAVAILABLE:{type(exc).__name__}", "peak_working_set_bytes": "UNAVAILABLE"}


def inclusion_exclusion_count(dnf: tuple[tuple[int, ...], ...], n: int) -> int:
    count = 0
    for mask in range(1, 1 << len(dnf)):
        union = set()
        chosen = 0
        for index, clause in enumerate(dnf):
            if mask & (1 << index):
                union.update(clause)
                chosen += 1
        term = 1 << (n - len(union))
        count += term if chosen % 2 else -term
    return count


def compile_official(object_id: str, dnf: tuple[tuple[int, ...], ...]) -> tuple[dict, dict[int, float]]:
    log_event("lexashap_start", object_id=object_id)
    Value.all_assignments_by_size_cache.clear()
    tracemalloc.start()
    before = process_memory()
    started = time.perf_counter_ns()
    variables = sorted({item for clause in dnf for item in clause})
    var_to_value = {item: Value(0.5, {str(item)}, label=str(item)) for item in variables}
    lifted = lift_recursively([{var_to_value[item] for item in clause} for clause in dnf])
    DNFCircuit.timeout = 3600
    DNFCircuitNode.start_time = time.time()
    root = DNFCircuitNode(lifted, "root")
    root.recursively_expand()
    compile_ns = time.perf_counter_ns() - started
    solve_started = time.perf_counter_ns()
    root.value.backward()
    solve_ns = time.perf_counter_ns() - solve_started
    _, peak_python = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    after = process_memory()
    scale = (2 ** len(variables)) / math.factorial(len(variables))
    shares = {
        item: sum(float(g) * float(p) for g, p in zip(var_to_value[item].grad, var_to_value[item].prob)) * scale
        for item in variables
    }
    metrics = {
        "object_id": object_id,
        "variables": len(variables),
        "clauses": len(dnf),
        "literal_occurrences": sum(map(len, dnf)),
        **tree_metrics(root),
        "arithmetic_dag_nodes": value_dag_nodes(root.value),
        "compile_ns": compile_ns,
        "solve_ns": solve_ns,
        "peak_python_bytes": peak_python,
        "working_set_before_bytes": before["working_set_bytes"],
        "working_set_after_bytes": after["working_set_bytes"],
        "process_peak_working_set_bytes": after["peak_working_set_bytes"],
        "efficiency_sum": sum(shares.values()),
        "efficiency_abs_error": abs(sum(shares.values()) - 1.0),
        "min_share": min(shares.values()),
        "max_share": max(shares.values()),
        "status": "VERIFIED_AUTHOR_DTREE",
        "cold_scope": "AUTHOR_VALUE_CACHE_CLEARED_IN_PROCESS",
    }
    log_event("lexashap_complete", object_id=object_id, arithmetic_dag_nodes=metrics["arithmetic_dag_nodes"])
    return metrics, shares


@dataclass(frozen=True)
class Factor:
    scope: tuple[str, ...]
    values: tuple[int, ...]

    def __post_init__(self):
        if len(self.values) != 1 << len(self.scope):
            raise ValueError("invalid factor size")


def bit(index: int, position: int, width: int) -> int:
    return (index >> (width - position - 1)) & 1


def assignment_index(scope: tuple[str, ...], assignment: dict[str, int]) -> int:
    result = 0
    for variable in scope:
        result = (result << 1) | assignment[variable]
    return result


def multiply(factors: list[Factor], counters: dict[str, int]) -> Factor:
    scope = tuple(dict.fromkeys(variable for factor in factors for variable in factor.scope))
    values = []
    width = len(scope)
    counters["factor_products"] += 1
    counters["generated_product_cells"] += 1 << width
    for row in range(1 << width):
        assignment = {variable: bit(row, index, width) for index, variable in enumerate(scope)}
        value = 1
        for factor in factors:
            value *= factor.values[assignment_index(factor.scope, assignment)]
            counters["multiplications"] += 1
        values.append(value)
    return Factor(scope, tuple(values))


def sum_out(factor: Factor, variable: str, counters: dict[str, int]) -> Factor:
    position = factor.scope.index(variable)
    scope = factor.scope[:position] + factor.scope[position + 1:]
    values = []
    width = len(scope)
    counters["generated_sum_cells"] += 1 << width
    for row in range(1 << width):
        assignment = {name: bit(row, index, width) for index, name in enumerate(scope)}
        assignment[variable] = 0
        low = factor.values[assignment_index(factor.scope, assignment)]
        assignment[variable] = 1
        high = factor.values[assignment_index(factor.scope, assignment)]
        values.append(low + high)
        counters["additions"] += 1
    return Factor(scope, tuple(values))


def witness_factors(clauses: list[tuple[str, ...]]) -> list[Factor]:
    factors = []
    for index, clause in enumerate(clauses, 1):
        scope = (f"Y{index}",) + clause
        width = len(scope)
        values = []
        for row in range(1 << width):
            truth = [bit(row, position, width) for position in range(width)]
            values.append(int(truth[0] == int(all(truth[1:]))))
        factors.append(Factor(scope, tuple(values)))
    y_scope = tuple(f"Y{index}" for index in range(1, len(clauses) + 1))
    factors.append(Factor(y_scope, tuple(int(row != 0) for row in range(1 << len(y_scope)))))
    return factors


def component_leaf_first_order(clauses: list[tuple[str, ...]]) -> list[str]:
    _, primal = build_graphs(clauses)
    priority = {"LINEITEM": 0, "ORDERS": 1, "PARTSUPP": 2, "SUPPLIER": 3, "PART": 4}
    output = []
    for component in connected_components(primal):
        output.extend(sorted(component, key=lambda p: (priority[relation(p)], p)))
    return output


def run_ve(object_id: str, clauses: list[tuple[str, ...]], order_name: str, expected_count: int) -> dict:
    log_event("ve_start", object_id=object_id, order=order_name)
    _, primal = build_graphs(clauses)
    if order_name == "MIN_FILL_SOURCE":
        player_order, source_width = min_fill_order(primal)
    elif order_name == "SOURCE_COMPONENT_LEAF_FIRST":
        player_order = component_leaf_first_order(clauses)
        source_width = "NOT_APPLICABLE_FIXED_LOCAL_ORDER"
    else:
        raise KeyError(order_name)
    order = player_order + [f"Y{index}" for index in range(1, len(clauses) + 1)]
    factors = witness_factors(clauses)
    counters = {"factor_products": 0, "generated_product_cells": 0, "generated_sum_cells": 0, "multiplications": 0, "additions": 0}
    maxima = {"frontier": 0, "product": 0, "output": 0, "player_frontier": 0, "player_product": 0, "player_output": 0}
    tracemalloc.start()
    started = time.perf_counter_ns()
    for step, variable in enumerate(order):
        selected = [factor for factor in factors if variable in factor.scope]
        factors = [factor for factor in factors if variable not in factor.scope]
        if not selected:
            continue
        product = multiply(selected, counters)
        reduced = sum_out(product, variable, counters)
        factors.append(reduced)
        frontier = len(product.scope) - 1
        maxima["frontier"] = max(maxima["frontier"], frontier)
        maxima["product"] = max(maxima["product"], len(product.values))
        maxima["output"] = max(maxima["output"], len(reduced.values))
        if step < len(player_order):
            maxima["player_frontier"] = max(maxima["player_frontier"], frontier)
            maxima["player_product"] = max(maxima["player_product"], len(product.values))
            maxima["player_output"] = max(maxima["player_output"], len(reduced.values))
    final = multiply(factors, counters)
    elapsed_ns = time.perf_counter_ns() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if final.scope:
        raise AssertionError(f"variables remain: {final.scope}")
    observed = final.values[0]
    result = {
        "object_id": object_id,
        "order_name": order_name,
        "player_order": "|".join(player_order),
        "source_min_fill_width": source_width,
        "model_count_ve": observed,
        "model_count_inclusion_exclusion": expected_count,
        "exact_match": observed == expected_count,
        "maximum_frontier": maxima["frontier"],
        "maximum_product_factor_cells": maxima["product"],
        "maximum_output_factor_cells": maxima["output"],
        "player_phase_maximum_frontier": maxima["player_frontier"],
        "player_phase_maximum_product_factor_cells": maxima["player_product"],
        "player_phase_maximum_output_factor_cells": maxima["player_output"],
        "generated_factor_cells": counters["generated_product_cells"] + counters["generated_sum_cells"],
        "factor_products": counters["factor_products"],
        "multiplications": counters["multiplications"],
        "additions": counters["additions"],
        "cold_runtime_ns": elapsed_ns,
        "peak_python_bytes": peak,
        "implementation_status": "REFERENCE_DIAGNOSTIC_IMPLEMENTATION",
    }
    log_event("ve_complete", object_id=object_id, order=order_name, exact_match=result["exact_match"])
    return result


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / "run_events.jsonl").write_text("", encoding="utf-8")
    log_event("canonical_run_start", protocol=cfg["protocol_id"])
    sources = {
        "Q9_L": read_csv(STAGE3A / "results" / "q9_l_witnesses.csv"),
        "Q9_H": read_csv(STAGE3A / "results" / "q9_h_witnesses.csv"),
    }
    objects = []
    structure_rows = []
    player_rows = []
    witness_rows = []
    for family in cfg["families"]:
        for m in cfg["prefix_witness_counts"]:
            selected = sources[family][:m]
            for boundary in cfg["boundaries"]:
                object_id = f"{family}{m}_{boundary}"
                clauses = [tuple(player_ids(row, boundary)) for row in selected]
                players = sorted({player for clause in clauses for player in clause})
                index = {player: i for i, player in enumerate(players)}
                dnf = tuple(tuple(index[player] for player in clause) for clause in clauses)
                objects.append((object_id, family, m, boundary, selected, clauses, players, dnf))
                structure_rows.append(structure_metrics(object_id, family, m, boundary, clauses))
                for player, player_index in index.items():
                    player_rows.append({"object_id": object_id, "player_index": player_index, "player_id": player, "relation": relation(player)})
                for witness_index, (row, clause, numeric) in enumerate(zip(selected, clauses, dnf), 1):
                    witness_rows.append({
                        "object_id": object_id,
                        "witness_index": witness_index,
                        "stage3a_witness_id": row["witness_id"],
                        "physical_players": "|".join(clause),
                        "numeric_clause": "|".join(map(str, numeric)),
                    })

    write_csv(RESULTS / "subinstance_structure.csv", structure_rows)
    write_csv(RESULTS / "player_map.csv", player_rows)
    write_csv(RESULTS / "witness_map.csv", witness_rows)

    lex_rows = []
    share_rows = []
    correctness_rows = []
    ve_rows = []
    for object_id, family, m, boundary, _selected, clauses, players, dnf in objects:
        expected_count = inclusion_exclusion_count(dnf, len(players))
        lex_metrics, shares = compile_official(object_id, dnf)
        lex_rows.append({"family": family, "m": m, "boundary": boundary, **lex_metrics})
        for player_index, share in shares.items():
            share_rows.append({"object_id": object_id, "player_index": player_index, "player_id": players[player_index], "boolean_shapley": share})
        for order_name in cfg["ve"]["orders"]:
            ve = run_ve(object_id, clauses, order_name, expected_count)
            ve_rows.append({"family": family, "m": m, "boundary": boundary, "players": len(players), "witnesses": m, **ve})
        correctness_rows.append({
            "object_id": object_id,
            "players": len(players),
            "witnesses": m,
            "model_count_inclusion_exclusion": expected_count,
            "lexashap_efficiency_abs_error": lex_metrics["efficiency_abs_error"],
            "lexashap_efficiency_pass": lex_metrics["efficiency_abs_error"] <= 1e-9,
            "ve_paths_exact": all(row["exact_match"] for row in ve_rows if row["object_id"] == object_id),
            "coalition_oracle_used": False,
        })

    write_csv(RESULTS / "lexashap_metrics.csv", lex_rows)
    write_csv(RESULTS / "lexashap_shares.csv", share_rows)
    write_csv(RESULTS / "ve_metrics.csv", ve_rows)
    write_csv(RESULTS / "correctness_checks.csv", correctness_rows)

    manifest = {
        "status": "VERIFIED",
        "protocol_id": cfg["protocol_id"],
        "python": sys.version,
        "platform": platform.platform(),
        "official_source": str(OFFICIAL),
        "objects": len(objects),
        "lexashap_runs": len(lex_rows),
        "ve_runs": len(ve_rows),
        "correctness_all_pass": all(row["lexashap_efficiency_pass"] and row["ve_paths_exact"] for row in correctness_rows),
        "ordered_compiler_gate": cfg["ordered_compiler_gate"],
        "coalition_enumeration": False,
        "complete_report_g": False,
        "config_sha256": sha256(CONFIG),
        "stage3a_q9_l_sha256": sha256(STAGE3A / "results" / "q9_l_witnesses.csv"),
        "stage3a_q9_h_sha256": sha256(STAGE3A / "results" / "q9_h_witnesses.csv"),
        "official_shapley_circuit_sha256": sha256(OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyCircuit.py"),
    }
    (RESULTS / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log_event("canonical_run_complete", **manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log_event("canonical_run_failed", error_type=type(exc).__name__, error=str(exc))
        raise
