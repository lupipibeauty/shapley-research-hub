from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import sys
import time
import tracemalloc
from collections import Counter, defaultdict, deque
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT.parent
WORKSPACE = ROOT.parents[2]
STAGE1 = EXPERIMENTS / "IDEA03_2_cross_region_source_control_v1"
STAGE0 = EXPERIMENTS / "IDEA03_stage0_fidelity_freeze_20261113"
OFFICIAL = WORKSPACE / "aggregate_report_shapley" / "external" / "abramovich" / "source" / "LExaBan-LExaShap-main"
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"

sys.path.insert(0, str(OFFICIAL))
sys.path.insert(0, str(STAGE0 / "src"))

from Algorithms.LExaShap.ShapleyCircuit import (  # noqa: E402
    DNFCircuit,
    DNFCircuitNode,
    lift_recursively,
)
from Algorithms.LExaShap.ShapleyEngine import Value  # noqa: E402
from validate_frozen_values import coordinate_weights  # noqa: E402


PROTOCOL = ROOT / "config" / "stage2a_protocol.json"
STAGE1_PROTOCOL = STAGE1 / "config" / "stage1_protocol.json"
FROZEN = STAGE0 / "config" / "frozen_value_function.json"
FIXTURES = STAGE1 / "results" / "new_fixture_records.csv"
PLAYERS = STAGE1 / "results" / "new_player_mapping.csv"
ORACLE = STAGE1 / "results" / "new_shapley.csv"
STRICT_GAMES = ("STRICT_CONCENTRATED", "STRICT_BALANCED")
NODES = ("NAT", "PA", "PB", "A1", "A2", "B1", "B2")
METRICS = ("enterprise_count", "site_count", "workers", "mfg_workers", "mfg_share")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def canonical_dnf(dnf) -> tuple[tuple[int, ...], ...]:
    clauses = sorted({tuple(sorted(set(clause))) for clause in dnf}, key=lambda x: (len(x), x))
    minimal: list[tuple[int, ...]] = []
    for clause in clauses:
        current = set(clause)
        if not any(set(existing).issubset(current) for existing in minimal):
            minimal.append(clause)
    return tuple(sorted(minimal))


def dnf_true(dnf: tuple[tuple[int, ...], ...], selected: set[int]) -> bool:
    return any(set(clause).issubset(selected) for clause in dnf)


def exact_boolean_shapley(dnf: tuple[tuple[int, ...], ...]) -> dict[int, Fraction]:
    variables = sorted({item for clause in dnf for item in clause})
    m = len(variables)
    output: dict[int, Fraction] = {}
    for player in variables:
        others = [item for item in variables if item != player]
        phi = Fraction(0)
        for mask in range(1 << len(others)):
            selected = {others[j] for j in range(len(others)) if mask & (1 << j)}
            delta = int(dnf_true(dnf, selected | {player})) - int(dnf_true(dnf, selected))
            if delta:
                k = len(selected)
                phi += Fraction(math.factorial(k) * math.factorial(m - k - 1), math.factorial(m)) * delta
        output[player] = phi
    return output


def tree_metrics(root) -> dict[str, int]:
    queue = deque([(root, 0)])
    nodes = leaves = max_depth = 0
    widths = Counter()
    while queue:
        node, depth = queue.popleft()
        nodes += 1
        widths[depth] += 1
        max_depth = max(max_depth, depth)
        children = list(node.children) if node.children else []
        if not children:
            leaves += 1
        for child in children:
            queue.append((child, depth + 1))
    return {
        "dtree_nodes": nodes,
        "dtree_leaves": leaves,
        "dtree_depth": max_depth,
        "dtree_max_layer_width": max(widths.values(), default=0),
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
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
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
        return {
            "working_set_bytes": int(counters.WorkingSetSize),
            "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
        }
    except Exception as exc:  # pragma: no cover - platform fallback
        return {"working_set_bytes": f"UNAVAILABLE:{type(exc).__name__}", "peak_working_set_bytes": "UNAVAILABLE"}


def compile_official(dnf: tuple[tuple[int, ...], ...]) -> tuple[dict, dict[int, float]]:
    # This calls the official d-tree and arithmetic Value implementation directly.
    # It deliberately does not add a local OBDD/d-DNNF compiler.
    Value.all_assignments_by_size_cache.clear()
    tracemalloc.start()
    before = process_memory()
    started = time.perf_counter()
    variables = sorted({item for clause in dnf for item in clause})
    var_to_value = {item: Value(0.5, {str(item)}, label=str(item)) for item in variables}
    lifted = lift_recursively([{var_to_value[item] for item in clause} for clause in dnf])
    DNFCircuit.timeout = 3600
    DNFCircuitNode.start_time = time.time()
    root = DNFCircuitNode(lifted, "root")
    root.recursively_expand()
    compile_seconds = time.perf_counter() - started
    solve_started = time.perf_counter()
    root.value.backward()
    solve_seconds = time.perf_counter() - solve_started
    _current, peak_python = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    after = process_memory()

    scale = (2 ** len(variables)) / math.factorial(len(variables))
    shares = {
        item: sum(float(g) * float(p) for g, p in zip(var_to_value[item].grad, var_to_value[item].prob)) * scale
        for item in variables
    }
    metrics = {
        "variables": len(variables),
        "clauses": len(dnf),
        "literal_occurrences": sum(len(clause) for clause in dnf),
        **tree_metrics(root),
        "arithmetic_dag_nodes": value_dag_nodes(root.value),
        "terminal_states": "NOT_APPLICABLE_DTREE",
        "compile_seconds": compile_seconds,
        "solve_seconds": solve_seconds,
        "peak_python_bytes": peak_python,
        "working_set_before_bytes": before["working_set_bytes"],
        "working_set_after_bytes": after["working_set_bytes"],
        "process_peak_working_set_bytes": after["peak_working_set_bytes"],
        "status": "VERIFIED_AUTHOR_DTREE",
    }
    return metrics, shares


def min_fill_order(n: int, clauses: list[tuple[int, ...]]) -> tuple[list[int], int]:
    adjacency = {i: set() for i in range(n)}
    for clause in clauses:
        for i, left in enumerate(clause):
            for right in clause[i + 1 :]:
                adjacency[left].add(right)
                adjacency[right].add(left)
    remaining = set(range(n))
    order: list[int] = []
    width = 0
    while remaining:
        choices = []
        for node in remaining:
            neighbors = sorted(adjacency[node] & remaining)
            missing = sum(
                right not in adjacency[left]
                for i, left in enumerate(neighbors)
                for right in neighbors[i + 1 :]
            )
            choices.append((missing, len(neighbors), node))
        _fill, _degree, node = min(choices)
        neighbors = sorted(adjacency[node] & remaining)
        width = max(width, len(neighbors))
        for i, left in enumerate(neighbors):
            for right in neighbors[i + 1 :]:
                adjacency[left].add(right)
                adjacency[right].add(left)
        remaining.remove(node)
        order.append(node)
    return order, width


def load_games() -> dict[str, dict]:
    player_rows = read_csv(PLAYERS)
    fixture_rows = read_csv(FIXTURES)
    games = {}
    for game_id in STRICT_GAMES:
        mapping_rows = sorted(
            (row for row in player_rows if row["game_id"] == game_id),
            key=lambda row: int(row["player_index"]),
        )
        id_to_index = {row["player_id"]: int(row["player_index"]) for row in mapping_rows}
        sites = []
        for row in sorted((item for item in fixture_rows if item["game_id"] == game_id), key=lambda item: item["sid"]):
            sites.append(
                {
                    "sid": row["sid"],
                    "eid": row["eid"],
                    "city": row["city"],
                    "province": row["province"],
                    "industry": row["industry"],
                    "workers": int(row["workers"]),
                    "clause": (
                        id_to_index[row["E_player"]],
                        id_to_index[row["B_player"]],
                        id_to_index[row["H_player"]],
                    ),
                }
            )
        games[game_id] = {
            "n": len(mapping_rows),
            "players": mapping_rows,
            "sites": sites,
            "witnesses": [tuple(sorted(site["clause"])) for site in sites],
        }
    return games


def site_in_node(site: dict, node: str) -> bool:
    if node == "NAT":
        return True
    if node in {"PA", "PB"}:
        return site["province"] == node
    return site["city"] == node


def report_from_witness_mask(game: dict, mask: int) -> dict[tuple[str, str], Fraction | int | None]:
    active = [site for i, site in enumerate(game["sites"]) if mask & (1 << i)]
    report = {}
    for node in NODES:
        rows = [site for site in active if site_in_node(site, node)]
        enterprise_count = len({site["eid"] for site in rows})
        workers = sum(site["workers"] for site in rows)
        mfg_workers = sum(site["workers"] for site in rows if site["industry"] == "manufacturing")
        report[(node, "enterprise_count")] = enterprise_count
        report[(node, "site_count")] = len(rows)
        report[(node, "workers")] = workers
        report[(node, "mfg_workers")] = mfg_workers
        report[(node, "mfg_share")] = None if workers == 0 else Fraction(mfg_workers, workers)
    return report


def mobius(values: list[Fraction], dimensions: int) -> list[Fraction]:
    coefficients = list(values)
    for bit in range(dimensions):
        flag = 1 << bit
        for mask in range(1 << dimensions):
            if mask & flag:
                coefficients[mask] -= coefficients[mask ^ flag]
    return coefficients


def add_component(rows: list[dict], value: str, label: str, coefficient: Fraction, dnf) -> None:
    if coefficient == 0:
        return
    canonical = canonical_dnf(dnf)
    rows.append(
        {
            "value": value,
            "label": label,
            "coefficient": coefficient,
            "dnf": canonical,
        }
    )


def decompose_values(game: dict, frozen: dict) -> list[dict]:
    weights = coordinate_weights(
        frozen["main_value"]["hierarchy_weights"],
        frozen["main_value"]["family_weights"],
    )
    full_mask = (1 << len(game["sites"])) - 1
    target = report_from_witness_mask(game, full_mask)
    components: list[dict] = []

    for node in NODES:
        node_sites = [site for site in game["sites"] if site_in_node(site, node)]
        by_enterprise = defaultdict(list)
        for site in node_sites:
            by_enterprise[site["eid"]].append(site)

        count_target = target[(node, "enterprise_count")]
        if count_target:
            coefficient = weights[(node, "enterprise_count")] / count_target
            for eid, sites in sorted(by_enterprise.items()):
                add_component(components, "v_fid_main", f"{node}:enterprise_count:{eid}", coefficient, [site["clause"] for site in sites])

        site_target = target[(node, "site_count")]
        if site_target:
            coefficient = weights[(node, "site_count")] / site_target
            for site in node_sites:
                add_component(components, "v_fid_main", f"{node}:site_count:{site['sid']}", coefficient, [site["clause"]])

        workers_target = target[(node, "workers")]
        if workers_target:
            for site in node_sites:
                coefficient = weights[(node, "workers")] * Fraction(site["workers"], workers_target)
                add_component(components, "v_fid_main", f"{node}:workers:{site['sid']}", coefficient, [site["clause"]])

        mfg_target = target[(node, "mfg_workers")]
        if mfg_target:
            for site in node_sites:
                if site["industry"] == "manufacturing":
                    coefficient = weights[(node, "mfg_workers")] * Fraction(site["workers"], mfg_target)
                    add_component(components, "v_fid_main", f"{node}:mfg_workers:{site['sid']}", coefficient, [site["clause"]])

        ratio_target = target[(node, "mfg_share")]
        ratio_values = []
        for mask in range(1 << len(game["sites"])):
            candidate = report_from_witness_mask(game, mask)[(node, "mfg_share")]
            if candidate is None and ratio_target is None:
                loss = Fraction(0)
            elif candidate is None or ratio_target is None:
                loss = Fraction(1)
            else:
                loss = abs(candidate - ratio_target)
            ratio_values.append(weights[(node, "mfg_share")] * (Fraction(1) - loss))
        for mask, coefficient in enumerate(mobius(ratio_values, len(game["sites"]))):
            if not mask or not coefficient:
                continue
            clause = set()
            for bit, site in enumerate(game["sites"]):
                if mask & (1 << bit):
                    clause.update(site["clause"])
            add_component(components, "v_fid_main", f"{node}:mfg_share:mobius_{mask}", coefficient, [clause])

    target_gap = target[("PA", "mfg_share")] - target[("PB", "mfg_share")]
    gap_values = []
    for mask in range(1 << len(game["sites"])):
        report = report_from_witness_mask(game, mask)
        left, right = report[("PA", "mfg_share")], report[("PB", "mfg_share")]
        loss = Fraction(1) if left is None or right is None else abs((left - right) - target_gap) / 2
        gap_values.append(Fraction(1) - loss)
    for mask, coefficient in enumerate(mobius(gap_values, len(game["sites"]))):
        if not mask or not coefficient:
            continue
        clause = set()
        for bit, site in enumerate(game["sites"]):
            if mask & (1 << bit):
                clause.update(site["clause"])
        add_component(components, "v_gap_PA_PB_mfg_share", f"gap:mobius_{mask}", coefficient, [clause])
    return components


def oracle_index() -> dict[tuple[str, str, str], Fraction]:
    output = {}
    for row in read_csv(ORACLE):
        if row["game_id"] in STRICT_GAMES:
            output[(row["game_id"], row["value"], row["player_id"])] = Fraction(row["shapley_fraction"])
    return output


def run() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))
    games = load_games()
    oracle = oracle_index()
    started = time.time()

    order_rows = []
    source_rows = []
    component_rows = []
    reuse_rows = []
    exact_rows = []
    component_check_rows = []
    compiled_cache: dict[tuple[tuple[int, ...], ...], tuple[dict, dict[int, float]]] = {}
    exact_cache: dict[tuple[tuple[int, ...], ...], dict[int, Fraction]] = {}

    for game_id, game in games.items():
        physical = list(range(game["n"]))
        structural, width = min_fill_order(game["n"], game["witnesses"])
        for name, order in (("PHYSICAL", physical), ("STRUCTURAL_MIN_FILL", structural)):
            order_rows.append(
                {
                    "game_id": game_id,
                    "order_name": name,
                    "order": " ".join(map(str, order)),
                    "min_fill_width": width if name == "STRUCTURAL_MIN_FILL" else "NOT_COMPUTED_FOR_POLICY",
                    "author_compiler_consumes_order": False,
                    "status": "INPUT_UNSUPPORTED_AUTHOR_INTERFACE",
                }
            )

        source_dnfs = [("GLOBAL_ANY_WITNESS", canonical_dnf(game["witnesses"]))]
        by_e = defaultdict(list)
        for site in game["sites"]:
            by_e[site["eid"]].append(site["clause"])
        source_dnfs.extend((f"ENTERPRISE_COMPONENT:{eid}", canonical_dnf(clauses)) for eid, clauses in sorted(by_e.items()))
        for scope, dnf in source_dnfs:
            metrics, shares = compile_official(dnf)
            exact = exact_boolean_shapley(dnf)
            max_error = max((abs(shares.get(player, 0.0) - float(phi)) for player, phi in exact.items()), default=0.0)
            source_rows.append(
                {
                    "game_id": game_id,
                    "scope": scope,
                    "order_policy": "AUTHOR_DTREE_HEURISTIC_PYTHONHASHSEED_0",
                    **metrics,
                    "boolean_shapley_max_abs_error": max_error,
                    "semantic_check": "VERIFIED" if max_error <= protocol["correctness"]["tolerance"] else "FAILED_CORRECTNESS",
                }
            )
            if max_error > protocol["correctness"]["tolerance"]:
                raise AssertionError((game_id, scope, max_error))

        components = decompose_values(game, frozen)
        for row in components:
            component_rows.append(
                {
                    "game_id": game_id,
                    "value": row["value"],
                    "label": row["label"],
                    "coefficient": str(row["coefficient"]),
                    "dnf": ";".join("&".join(map(str, clause)) for clause in row["dnf"]),
                    "clauses": len(row["dnf"]),
                    "variables": len({item for clause in row["dnf"] for item in clause}),
                }
            )

        for value_name in protocol["frozen_values"]:
            selected = [row for row in components if row["value"] == value_name]
            grouped = defaultdict(Fraction)
            for row in selected:
                grouped[row["dnf"]] += row["coefficient"]
            grouped = {dnf: coefficient for dnf, coefficient in grouped.items() if coefficient}
            allocation = [0.0] * game["n"]
            cache_hits = cache_misses = 0
            total_dtree_nodes = total_arithmetic_nodes = 0
            total_compile = total_solve = 0.0
            peak_python = 0
            for dnf, coefficient in grouped.items():
                if dnf in compiled_cache:
                    metrics, shares = compiled_cache[dnf]
                    cache_hits += 1
                else:
                    metrics, shares = compile_official(dnf)
                    compiled_cache[dnf] = (metrics, shares)
                    cache_misses += 1
                if dnf not in exact_cache:
                    exact_cache[dnf] = exact_boolean_shapley(dnf)
                exact_component = exact_cache[dnf]
                component_error = max((abs(shares.get(player, 0.0) - float(phi)) for player, phi in exact_component.items()), default=0.0)
                component_check_rows.append(
                    {
                        "game_id": game_id,
                        "value": value_name,
                        "dnf": ";".join("&".join(map(str, clause)) for clause in dnf),
                        "coefficient": str(coefficient),
                        "max_abs_error": component_error,
                        "status": "VERIFIED" if component_error <= protocol["correctness"]["tolerance"] else "FAILED_CORRECTNESS",
                    }
                )
                if component_error > protocol["correctness"]["tolerance"]:
                    raise AssertionError((game_id, value_name, dnf, component_error))
                for player, share in shares.items():
                    allocation[player] += float(coefficient) * share
                total_dtree_nodes += int(metrics["dtree_nodes"])
                total_arithmetic_nodes += int(metrics["arithmetic_dag_nodes"])
                total_compile += float(metrics["compile_seconds"])
                total_solve += float(metrics["solve_seconds"])
                peak_python = max(peak_python, int(metrics["peak_python_bytes"]))

            max_oracle_error = 0.0
            for player_row, observed in zip(game["players"], allocation):
                expected = oracle[(game_id, value_name, player_row["player_id"])]
                error = abs(observed - float(expected))
                max_oracle_error = max(max_oracle_error, error)
                exact_rows.append(
                    {
                        "game_id": game_id,
                        "value": value_name,
                        "player_index": player_row["player_index"],
                        "player_id": player_row["player_id"],
                        "relation": player_row["relation"],
                        "direct_source_shapley": observed,
                        "oracle_fraction": str(expected),
                        "oracle_float": float(expected),
                        "abs_error": error,
                        "status": "VERIFIED" if error <= protocol["correctness"]["tolerance"] else "FAILED_CORRECTNESS",
                    }
                )
            if max_oracle_error > protocol["correctness"]["tolerance"]:
                raise AssertionError((game_id, value_name, max_oracle_error))
            reuse_rows.append(
                {
                    "game_id": game_id,
                    "value": value_name,
                    "raw_components": len(selected),
                    "unique_dnfs_after_coefficient_merge": len(grouped),
                    "full_component_cache_hits_global_run_order": cache_hits,
                    "full_component_cache_misses_global_run_order": cache_misses,
                    "partial_subexpression_cross_output_reuse": "NOT_SUPPORTED_BY_AUTHOR_INTERFACE",
                    "numeric_multioutput_state_reuse": "NOT_IMPLEMENTED",
                    "sum_unique_component_dtree_nodes": total_dtree_nodes,
                    "sum_unique_component_arithmetic_dag_nodes": total_arithmetic_nodes,
                    "sum_first_seen_component_compile_seconds": total_compile,
                    "sum_first_seen_component_solve_seconds": total_solve,
                    "max_component_peak_python_bytes": peak_python,
                    "max_abs_oracle_error": max_oracle_error,
                    "status": "VERIFIED_EXACT_ADAPTATION",
                }
            )

    write_csv(RESULTS / "variable_orders.csv", order_rows)
    write_csv(RESULTS / "source_compilation_metrics.csv", source_rows)
    write_csv(RESULTS / "value_components.csv", component_rows)
    write_csv(RESULTS / "multioutput_reuse_metrics.csv", reuse_rows)
    write_csv(RESULTS / "component_boolean_exactness.csv", component_check_rows)
    write_csv(RESULTS / "exact_shapley_comparison.csv", exact_rows)

    status = "VERIFIED" if all(row["status"] == "VERIFIED" for row in exact_rows) else "FAILED_CORRECTNESS"
    manifest = {
        "run_id": "STAGE2A_20261113_CANONICAL",
        "status": status,
        "stage": "2A_ONLY",
        "fixtures": list(STRICT_GAMES),
        "algorithm_input_used_full_player_coalition_table": False,
        "algorithm_input_used_harsanyi_oracle": False,
        "oracle_used_after_solver_output_for_validation_only": True,
        "mature_compiler": "official LExaShap DNFCircuit/d-tree",
        "ordered_compiler_comparison": "INPUT_UNSUPPORTED_AUTHOR_INTERFACE",
        "partial_subexpression_cross_output_reuse": "NOT_SUPPORTED_BY_AUTHOR_INTERFACE",
        "elapsed_seconds": time.time() - started,
        "python": sys.version,
        "platform": platform.platform(),
        "pythonhashseed": "0 required by canonical command",
        "process_memory_at_end": process_memory(),
        "input_hashes": {
            str(path.relative_to(WORKSPACE)): sha256(path)
            for path in (
                PROTOCOL,
                Path(__file__).resolve(),
                STAGE1_PROTOCOL,
                FROZEN,
                FIXTURES,
                PLAYERS,
                ORACLE,
                OFFICIAL / "README.md",
                OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyCircuit.py",
                OFFICIAL / "Algorithms" / "LExaShap" / "ShapleyEngine.py",
            )
        },
        "output_hashes": {},
    }
    outputs = sorted(RESULTS.glob("*.csv"))
    manifest["output_hashes"] = {str(path.relative_to(ROOT)): sha256(path) for path in outputs}
    (RESULTS / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    with (LOGS / "run_events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": "stage2a_complete", "status": status}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    run()
