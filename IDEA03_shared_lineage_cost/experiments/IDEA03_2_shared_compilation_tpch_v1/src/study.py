from __future__ import annotations

import itertools
import math
import sys
from collections import defaultdict, deque
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable
from dataclasses import dataclass


ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT.parent / "IDEA03_2_joint_value_deepening_v1"
sys.path.insert(0, str(PRIOR / "src"))

from joint_game import (  # noqa: E402
    CITY_PROVINCE,
    DNF,
    Game,
    Player,
    RegionLink,
    Site,
    _object_indicator_dnfs,
    and_dnf,
    component_value,
    components_to_poly,
    dnf_value,
    exact_shapley,
    minimize_dnf,
    poly_shapley,
    ratio_components,
    report_python,
    site_city_dnf,
    sufficient_statistics,
    threshold_dnf,
    value as historical_value,
)


VALUE_NAMES = ("GR", "GL", "GC")


def _add(players: list[Player], relation: str, key: str) -> int:
    index = len(players)
    players.append(Player(index, f"{relation}:{key}", relation, key))
    return index


def build_threshold2_game() -> Game:
    """N=12 fixture with two distinct enterprises in each province."""
    players: list[Player] = []
    eids = ("EA1", "EA2", "EB1", "EB2")
    e = {eid: _add(players, "E", eid) for eid in eids}
    rows = (
        ("SA1", "EA1", "A1", "manufacturing", 8),
        ("SA2", "EA2", "A2", "service", 12),
        ("SB1", "EB1", "B1", "manufacturing", 15),
        ("SB2", "EB2", "B2", "service", 5),
    )
    b = {sid: _add(players, "B", sid) for sid, *_ in rows}
    h = {sid: _add(players, "H", sid) for sid, *_ in rows}
    sites = tuple(
        Site(sid, eid, city, industry, workers, e[eid], b[sid], h[sid])
        for sid, eid, city, industry, workers in rows
    )
    return Game("E0_F0_K2_N12", "F0_EBH", tuple(players), sites, (), (2, 2))


def build_controlled_f2(pair_id: int, mode: str) -> Game:
    """N=16 paired F2 fixtures. Only the six native entity-link facts differ.

    Each pair keeps E/B/H rows, player ids, row counts, and total proof count fixed.
    Pair ids pre-specify site attributes; mode is never selected by runtime.
    """
    if pair_id not in (1, 2, 3) or mode not in {"concentrated", "dispersed"}:
        raise ValueError((pair_id, mode))
    players: list[Player] = []
    e = {eid: _add(players, "E", eid) for eid in ("E1", "E2")}
    workers = {
        1: (8, 12, 15, 5),
        2: (9, 11, 14, 6),
        3: (7, 13, 16, 4),
    }[pair_id]
    rows = (
        ("S1", "E1", "manufacturing", workers[0]),
        ("S2", "E1", "service", workers[1]),
        ("S3", "E2", "manufacturing", workers[2]),
        ("S4", "E2", "service", workers[3]),
    )
    b = {sid: _add(players, "B", sid) for sid, *_ in rows}
    h = {sid: _add(players, "H", sid) for sid, *_ in rows}
    sites = tuple(Site(sid, eid, None, industry, w, e[eid], b[sid], h[sid]) for sid, eid, industry, w in rows)

    # Both modes have three links per enterprise. Concentrated uses one city per
    # enterprise; dispersed uses two cities and therefore more report-coordinate reuse.
    entries = {
        "concentrated": (("E1", "A1"), ("E1", "A1"), ("E1", "A1"),
                         ("E2", "B1"), ("E2", "B1"), ("E2", "B1")),
        "dispersed": (("E1", "A1"), ("E1", "A1"), ("E1", "A2"),
                      ("E2", "B1"), ("E2", "B1"), ("E2", "B2")),
    }[mode]
    links = []
    for serial, (eid, city) in enumerate(entries, 1):
        rid = f"R{serial}"
        links.append(RegionLink(rid, eid, city, _add(players, "R2", rid)))
    return Game(f"E1_PAIR{pair_id}_{mode.upper()}", "F2_ENTITY_LINK", tuple(players), sites, tuple(links), (1, 1))


def ratios_and_gates(game: Game, mask: int) -> tuple[Fraction, Fraction, int, int]:
    ca, ma, wa, cb, mb, wb = sufficient_statistics(game, mask)
    ra = Fraction(ma, wa) if wa else Fraction(0)
    rb = Fraction(mb, wb) if wb else Fraction(0)
    return ra, rb, int(ca >= game.thresholds[0]), int(cb >= game.thresholds[1])


def study_value(game: Game, mask: int, name: str) -> Fraction:
    ra, rb, ta, tb = ratios_and_gates(game, mask)
    if name == "GR":
        return (ra + rb) / 2
    if name == "GL":
        return (ta * ra + tb * rb) / 2
    if name == "GC":
        return ta * tb * (ra + rb) / 2
    raise KeyError(name)


def study_components(game: Game, name: str) -> list[tuple[Fraction, DNF, str]]:
    ta = threshold_dnf(_object_indicator_dnfs(game, "PA", "enterprise"), game.thresholds[0])
    tb = threshold_dnf(_object_indicator_dnfs(game, "PB", "enterprise"), game.thresholds[1])
    ratios = {province: ratio_components(game, province) for province in ("PA", "PB")}
    if name == "GR":
        return [(coef / 2, dnf, label) for province in ("PA", "PB") for coef, dnf, label in ratios[province]]
    if name == "GL":
        return [(coef / 2, and_dnf(ta if province == "PA" else tb, dnf), f"T_{province[-1]}&{label}")
                for province in ("PA", "PB") for coef, dnf, label in ratios[province]]
    if name == "GC":
        gate = and_dnf(ta, tb)
        return [(coef / 2, and_dnf(gate, dnf), f"T_A&T_B&{label}")
                for province in ("PA", "PB") for coef, dnf, label in ratios[province]]
    raise KeyError(name)


def exhaustive_values(game: Game, name: str) -> list[Fraction]:
    return [study_value(game, mask, name) for mask in range(1 << game.n)]


def shapley_from_values(values: list[Fraction], n: int) -> list[Fraction]:
    factorial = [math.factorial(i) for i in range(n + 1)]
    result = [Fraction(0) for _ in range(n)]
    for player in range(n):
        bit = 1 << player
        for mask in range(1 << n):
            if mask & bit:
                continue
            k = mask.bit_count()
            result[player] += Fraction(factorial[k] * factorial[n-k-1], factorial[n]) * (values[mask | bit] - values[mask])
    return result


def mobius_from_values(values: list[Fraction], n: int) -> dict[int, Fraction]:
    """Exact Boolean-lattice Möbius transform in O(n 2^n).

    This avoids the unbounded 2^(number of DNF clauses) inclusion--exclusion
    expansion. It is used only for N<=16 audited fixtures.
    """
    coefficients = list(values)
    for player in range(n):
        bit = 1 << player
        for mask in range(1 << n):
            if mask & bit:
                coefficients[mask] -= coefficients[mask ^ bit]
    return {mask: value for mask, value in enumerate(coefficients) if value}


def historical_g1_redundancy(game: Game) -> dict:
    mismatches = []
    positive_ratio_gate_failures = 0
    for mask in range(1 << game.n):
        ra, rb, ta, tb = ratios_and_gates(game, mask)
        if (ra > 0 and not ta) or (rb > 0 and not tb):
            positive_ratio_gate_failures += 1
        gr = (ra + rb) / 2
        if historical_value(game, mask, "G1") != gr:
            mismatches.append(mask)
    return {
        "game_id": game.game_id,
        "n": game.n,
        "coalitions": 1 << game.n,
        "positive_ratio_gate_failures": positive_ratio_gate_failures,
        "g1_gr_mismatches": len(mismatches),
        "first_mismatch": mismatches[0] if mismatches else None,
        "status": "VERIFIED_EQUIVALENT" if not mismatches else "COUNTEREXAMPLE_FOUND",
    }


def player_region_support(game: Game) -> dict[int, set[str]]:
    support = {p.index: set() for p in game.players}
    for province in ("PA", "PB"):
        for kind in ("enterprise", "workers", "mfg"):
            for _label, _weight, dnf in _object_indicator_dnfs(game, province, kind):
                for clause in dnf:
                    for player in clause:
                        support[player].add(province)
    return support


def cross_region_mixed_differences(game: Game, values: list[Fraction]) -> int:
    """Count nonzero Δ_iΔ_j v(S) for PA-only i and PB-only j."""
    support = player_region_support(game)
    pa = [i for i, regions in support.items() if "PA" in regions and "PB" not in regions]
    pb = [i for i, regions in support.items() if "PB" in regions and "PA" not in regions]
    count = 0
    for i in pa:
        for j in pb:
            bits = (1 << i) | (1 << j)
            for mask in range(1 << game.n):
                if mask & bits:
                    continue
                mixed = values[mask | bits] - values[mask | (1 << i)] - values[mask | (1 << j)] + values[mask]
                count += int(mixed != 0)
    return count


def game_value_metrics(game: Game, name: str) -> tuple[dict, list[dict]]:
    values = exhaustive_values(game, name)
    allocation = shapley_from_values(values, game.n)
    negative_marginals = 0
    for player in range(game.n):
        bit = 1 << player
        negative_marginals += sum(values[mask | bit] < values[mask] for mask in range(1 << game.n) if not mask & bit)
    components = study_components(game, name)
    for mask, observed in enumerate(values):
        if component_value(components, mask) != observed:
            raise AssertionError((game.game_id, name, mask, component_value(components, mask), observed))
    poly = mobius_from_values(values, game.n)
    if poly_shapley(poly, game.n) != allocation:
        raise AssertionError((game.game_id, name, "Harsanyi mismatch"))
    metric = {
        "game_id": game.game_id,
        "value": name,
        "coalitions": len(values),
        "nonzero_value_coalitions": sum(v != 0 for v in values),
        "full_value": str(values[-1]),
        "effective_threshold_events": sum((ratios_and_gates(game, m)[2] + ratios_and_gates(game, m)[3]) for m in range(1 << game.n)),
        "cross_region_mixed_differences": cross_region_mixed_differences(game, values),
        "negative_marginals": negative_marginals,
        "negative_shapley_players": sum(v < 0 for v in allocation),
        "boolean_components": len(components),
        "raw_dnf_clauses": sum(len(dnf) for _, dnf, _ in components),
        "harsanyi_terms": len(poly),
        "max_harsanyi_degree": max((mask.bit_count() for mask in poly), default=0),
        "status": "VERIFIED",
    }
    rows = [{"game_id": game.game_id, "value": name, "player_id": p.player_id,
             "relation": p.relation, "shapley_fraction": str(phi), "shapley": float(phi)}
            for p, phi in zip(game.players, allocation)]
    return metric, rows


def equivalence_matrix(game: Game) -> list[dict]:
    values = {name: exhaustive_values(game, name) for name in VALUE_NAMES}
    rows = []
    for left in VALUE_NAMES:
        for right in VALUE_NAMES:
            mismatches = [i for i, (a, b) in enumerate(zip(values[left], values[right])) if a != b]
            rows.append({"game_id": game.game_id, "left": left, "right": right,
                         "equivalent": not mismatches, "mismatches": len(mismatches),
                         "first_mismatch": mismatches[0] if mismatches else None})
    return rows


def threshold_witness_examples(game: Game) -> list[dict]:
    predicates: dict[str, Callable[[Fraction, Fraction, int, int], bool]] = {
        "positive_ratio_but_C_lt_2": lambda ra, rb, ta, tb: (ra > 0 and not ta) or (rb > 0 and not tb),
        "positive_ratio_and_C_ge_2": lambda ra, rb, ta, tb: (ra > 0 and ta) or (rb > 0 and tb),
        "TA_true_TB_false": lambda ra, rb, ta, tb: bool(ta and not tb),
        "both_thresholds_true": lambda ra, rb, ta, tb: bool(ta and tb),
    }
    rows = []
    for label, predicate in predicates.items():
        for mask in range(1 << game.n):
            ra, rb, ta, tb = ratios_and_gates(game, mask)
            if predicate(ra, rb, ta, tb):
                rows.append({"example": label, "mask": mask,
                             "players": ";".join(p.player_id for p in game.players if mask & (1 << p.index)),
                             "rA": str(ra), "rB": str(rb), "TA": ta, "TB": tb,
                             **{name: str(study_value(game, mask, name)) for name in VALUE_NAMES}})
                break
    if len(rows) != len(predicates):
        raise AssertionError(("missing threshold witness", rows))
    return rows


def proof_sets(game: Game) -> list[frozenset[int]]:
    return [clause for site in game.sites for city in CITY_PROVINCE
            for clause in site_city_dnf(game, site, city)]


def _components(vertices: Iterable[int], edges: set[tuple[int, int]]) -> int:
    vertices = set(vertices)
    adjacency = {v: set() for v in vertices}
    for a, b in edges:
        adjacency[a].add(b); adjacency[b].add(a)
    count = 0
    while vertices:
        count += 1
        queue = [vertices.pop()]
        while queue:
            v = queue.pop()
            for u in adjacency[v] & vertices:
                vertices.remove(u); queue.append(u)
    return count


def min_fill_upper_bound(n: int, edges: set[tuple[int, int]]) -> int:
    adjacency = {i: set() for i in range(n)}
    for a, b in edges:
        adjacency[a].add(b); adjacency[b].add(a)
    width = 0
    remaining = set(range(n))
    while remaining:
        def key(v: int):
            neigh = adjacency[v] & remaining
            missing = sum(b not in adjacency[a] for a, b in itertools.combinations(neigh, 2))
            return missing, len(neigh), v
        v = min(remaining, key=key)
        neigh = adjacency[v] & remaining
        width = max(width, len(neigh))
        for a, b in itertools.combinations(neigh, 2):
            adjacency[a].add(b); adjacency[b].add(a)
        remaining.remove(v)
    return width


def structural_metrics(game: Game, value_name: str = "GC") -> dict:
    proofs = proof_sets(game)
    occurrences = defaultdict(int)
    for proof in proofs:
        for p in proof:
            occurrences[p] += 1
    overlaps = [len(a & b) for i, a in enumerate(proofs) for b in proofs[i+1:]]
    edges: set[tuple[int, int]] = set()
    for proof in proofs:
        for a, b in itertools.combinations(sorted(proof), 2):
            edges.add((a, b))
    components = study_components(game, value_name)
    unique_clauses = {tuple(sorted(clause)) for _, dnf, _ in components for clause in dnf}
    unique_dnfs = {tuple(tuple(sorted(c)) for c in dnf) for _, dnf, _ in components}
    stats_and_values = [(sufficient_statistics(game, mask), study_value(game, mask, value_name))
                        for mask in range(1 << game.n)]
    states = {item[0] for item in stats_and_values}
    poly = mobius_from_values([item[1] for item in stats_and_values], game.n)
    return {
        "game_id": game.game_id, "query_version": game.query_version, "n": game.n,
        "join_witnesses": len(proofs), "minimal_proof_count": len(set(proofs)),
        "variable_occurrences": sum(len(p) for p in proofs),
        "player_reuse_mean": sum(occurrences.values()) / game.n,
        "player_reuse_max": max(occurrences.values(), default=0),
        "overlapping_proof_pairs": sum(v > 0 for v in overlaps),
        "mean_pair_overlap": sum(overlaps) / len(overlaps) if overlaps else 0,
        "primal_edges": len(edges), "connected_components": _components(range(game.n), edges),
        "min_fill_treewidth_upper_bound": min_fill_upper_bound(game.n, edges),
        "joint_statistic_states": len(states), "g_coordinates": 6,
        "finite_threshold_components": len(components), "harsanyi_terms": len(poly),
        "max_harsanyi_degree": max((m.bit_count() for m in poly), default=0),
        "total_boolean_dnf_clauses": sum(len(dnf) for _, dnf, _ in components),
        "unique_dnf_clauses": len(unique_clauses), "unique_component_dnfs": len(unique_dnfs),
        "actual_shared_subexpressions": sum(len(dnf) for _, dnf, _ in components) - len(unique_clauses),
    }


class ReducedADD:
    """Exact reduced ordered ADD plus cardinality-conditioned Shapley DP."""
    def __init__(self, n: int, evaluator: Callable[[int], Fraction]):
        self.n = n
        self.nodes: list[tuple[int, int, int]] = []
        self.unique: dict[tuple[int, int, int], int] = {}
        self.terminals: dict[Fraction, int] = {}
        self.terminal_values: dict[int, Fraction] = {}

        def terminal(value: Fraction) -> int:
            if value not in self.terminals:
                node = -(len(self.terminals) + 1)
                self.terminals[value] = node
                self.terminal_values[node] = value
            return self.terminals[value]

        def build(level: int, mask: int) -> int:
            if level == n:
                return terminal(evaluator(mask))
            low = build(level + 1, mask)
            high = build(level + 1, mask | (1 << level))
            if low == high:
                return low
            key = (level, low, high)
            if key not in self.unique:
                self.unique[key] = len(self.nodes)
                self.nodes.append(key)
            return self.unique[key]

        self.root = build(0, 0)

    @staticmethod
    def _convolve_binomial(poly: tuple[Fraction, ...], count: int) -> tuple[Fraction, ...]:
        result = list(poly)
        for _ in range(count):
            result = [result[0]] + [result[i] + result[i-1] for i in range(1, len(result))] + [result[-1]]
        return tuple(result)

    @staticmethod
    def _add_poly(a: tuple[Fraction, ...], b: tuple[Fraction, ...], shift_b: int = 0) -> tuple[Fraction, ...]:
        size = max(len(a), len(b) + shift_b)
        out = [Fraction(0) for _ in range(size)]
        for i, v in enumerate(a): out[i] += v
        for i, v in enumerate(b): out[i + shift_b] += v
        return tuple(out)

    def conditioned_cardinality_sum(self, fixed: int, selected: int) -> tuple[Fraction, ...]:
        memo = {}
        def rec(node: int, level: int) -> tuple[Fraction, ...]:
            key = (node, level)
            if key in memo:
                return memo[key]
            if node < 0:
                free = self.n - level - int(level <= fixed < self.n)
                out = self._convolve_binomial((self.terminal_values[node],), free)
                memo[key] = out
                return out
            node_level, low, high = self.nodes[node]
            skipped = node_level - level - int(level <= fixed < node_level)
            if node_level == fixed:
                out = rec(high if selected else low, node_level + 1)
            else:
                out = self._add_poly(rec(low, node_level + 1), rec(high, node_level + 1), 1)
            out = self._convolve_binomial(out, skipped)
            memo[key] = out
            return out
        return rec(self.root, 0)

    def shapley(self) -> list[Fraction]:
        factorial = [math.factorial(i) for i in range(self.n + 1)]
        output = []
        for player in range(self.n):
            without = self.conditioned_cardinality_sum(player, 0)
            with_player = self.conditioned_cardinality_sum(player, 1)
            phi = Fraction(0)
            for k in range(self.n):
                phi += Fraction(factorial[k] * factorial[self.n-k-1], factorial[self.n]) * (with_player[k] - without[k])
            output.append(phi)
        return output

    def metrics(self) -> dict:
        return {"nonterminal_nodes": len(self.nodes), "terminal_nodes": len(self.terminals),
                "compiled_nodes": len(self.nodes) + len(self.terminals)}


def shared_expression_metrics(game: Game) -> list[dict]:
    rows = []
    seen_dnfs = set()
    seen_clauses = set()
    for value_name in VALUE_NAMES:
        components = study_components(game, value_name)
        raw_dnfs = [tuple(tuple(sorted(c)) for c in dnf) for _, dnf, _ in components]
        raw_clauses = [tuple(sorted(c)) for _, dnf, _ in components for c in dnf]
        new_dnfs = set(raw_dnfs) - seen_dnfs
        new_clauses = set(raw_clauses) - seen_clauses
        rows.append({"game_id": game.game_id, "value": value_name,
                     "raw_component_dnfs": len(raw_dnfs), "new_component_dnfs": len(new_dnfs),
                     "raw_clauses": len(raw_clauses), "new_clauses": len(new_clauses),
                     "reused_component_dnfs": len(raw_dnfs) - len(new_dnfs),
                     "reused_clauses": len(raw_clauses) - len(new_clauses)})
        seen_dnfs.update(raw_dnfs); seen_clauses.update(raw_clauses)
    return rows


@dataclass(frozen=True)
class TPCHLine:
    orderkey: int
    linenumber: int
    suppkey: int
    partkey: int
    nation: str
    region: str
    discounted_cents: int
    promo: bool


@dataclass(frozen=True)
class TPCHGame:
    game_id: str
    players: tuple[tuple[str, str], ...]  # (player_id, relation)
    lines: tuple[TPCHLine, ...]
    regions: tuple[str, str]
    nations: tuple[str, str, str, str]

    @property
    def n(self) -> int:
        return len(self.players)


def build_tpch_game(game_id: str, records: list[dict]) -> TPCHGame:
    lines = tuple(TPCHLine(**record) for record in records)
    player_rows = []
    for relation, values in (
        ("order", sorted({r.orderkey for r in lines})),
        ("lineitem", sorted({(r.orderkey, r.linenumber) for r in lines})),
        ("supplier", sorted({r.suppkey for r in lines})),
        ("part", sorted({r.partkey for r in lines})),
    ):
        for value in values:
            if relation == "lineitem":
                label = f"{value[0]}:{value[1]}"
            else:
                label = str(value)
            player_rows.append((f"{relation}:{label}", relation))
    regions = tuple(sorted({r.region for r in lines}))
    nations = tuple(sorted({r.nation for r in lines}))
    if len(regions) != 2 or len(nations) != 4:
        raise ValueError(("TPC-H sample must have exactly 2 regions and 4 nations", regions, nations))
    return TPCHGame(game_id, tuple(player_rows), lines, regions, nations)  # type: ignore[arg-type]


def tpch_active_lines(game: TPCHGame, mask: int) -> list[TPCHLine]:
    active = {pid for i, (pid, _relation) in enumerate(game.players) if mask & (1 << i)}
    output = []
    for line in game.lines:
        needed = {
            f"order:{line.orderkey}", f"lineitem:{line.orderkey}:{line.linenumber}",
            f"supplier:{line.suppkey}", f"part:{line.partkey}",
        }
        if needed <= active:
            output.append(line)
    return output


def tpch_report(game: TPCHGame, mask: int) -> dict[tuple[str, str], int | Fraction | None]:
    active = tpch_active_lines(game, mask)
    nodes = ("GLOBAL",) + game.regions + game.nations
    output = {}
    for node in nodes:
        rows = [r for r in active if node == "GLOBAL" or r.region == node or r.nation == node]
        suppliers = len({r.suppkey for r in rows})
        orders = len({r.orderkey for r in rows})
        revenue = sum(r.discounted_cents for r in rows)
        promo = sum(r.discounted_cents for r in rows if r.promo)
        output[(node, "active_suppliers")] = suppliers
        output[(node, "orders")] = orders
        output[(node, "discounted_revenue_cents")] = revenue
        output[(node, "promo_revenue_cents")] = promo
        output[(node, "promo_ratio")] = None if revenue == 0 else Fraction(promo, revenue)
    return output


def tpch_values(game: TPCHGame, mask: int) -> dict[str, Fraction]:
    report = tpch_report(game, mask)
    full = tpch_report(game, (1 << game.n) - 1)
    r1, r2 = game.regions
    rev = []
    ratios = []
    gates = []
    for region in (r1, r2):
        denom = int(full[(region, "discounted_revenue_cents")] or 0)
        numer = int(report[(region, "discounted_revenue_cents")] or 0)
        rev.append(Fraction(numer, denom) if denom else Fraction(0))
        ratios.append(report[(region, "promo_ratio")] or Fraction(0))
        gates.append(int(report[(region, "active_suppliers")] or 0) >= 1)
    additive = (rev[0] + rev[1]) / 2
    local = Fraction(int(gates[0]), 1) * ratios[0]
    cross = Fraction(int(gates[0] and gates[1]), 1) * (ratios[0] + ratios[1]) / 2
    return {"TPCH_ADD": additive, "TPCH_LOCAL": local, "TPCH_CROSS": cross}


def tpch_witness_dnfs(game: TPCHGame) -> list[DNF]:
    index = {pid: i for i, (pid, _relation) in enumerate(game.players)}
    result = []
    for line in game.lines:
        clause = frozenset({
            index[f"order:{line.orderkey}"], index[f"lineitem:{line.orderkey}:{line.linenumber}"],
            index[f"supplier:{line.suppkey}"], index[f"part:{line.partkey}"],
        })
        result.append((clause,))
    return result

