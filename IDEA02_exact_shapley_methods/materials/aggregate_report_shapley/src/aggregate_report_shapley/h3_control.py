from __future__ import annotations

import itertools
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class Fact:
    player: int
    relation: str
    key1: str
    key2: str = ""


@dataclass(frozen=True, slots=True)
class Grounding:
    grounding_id: str
    clause: frozenset[int]
    output_key: str


@dataclass(frozen=True, slots=True)
class ControlInstance:
    family: str
    n: int
    sharing: str
    seed: int
    r_facts: tuple[Fact, ...]
    s_facts: tuple[Fact, ...]
    t_facts: tuple[Fact, ...]
    groundings: tuple[Grounding, ...]


def _counts(n: int) -> tuple[int, int, int]:
    r = max(2, n // 4)
    t = r
    return r, t, n - r - t


def _edge_pattern(r: int, t: int, s: int, sharing: str, seed: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    # Randomized coverage backbone: every R/T fact is effective, while seeds
    # alter actual key incidences rather than merely permuting S-player labels.
    y_order = list(range(t)); rng.shuffle(y_order)
    edges = [(i % r, y_order[i % t]) for i in range(max(r, t))]
    x_degree = [sum(x == i for x, _ in edges) for i in range(r)]
    y_degree = [sum(y == i for _, y in edges) for i in range(t)]
    hub_x, hub_y = rng.randrange(r), rng.randrange(t)
    while len(edges) < s:
        if sharing == "low":
            min_x = min(x_degree); min_y = min(y_degree)
            x = rng.choice([i for i, d in enumerate(x_degree) if d == min_x])
            y = rng.choice([i for i, d in enumerate(y_degree) if d == min_y])
        elif sharing == "medium":
            x = hub_x if rng.random() < 0.55 else rng.randrange(r)
            y = hub_y if rng.random() < 0.35 else rng.randrange(t)
        elif sharing == "high":
            x = hub_x if rng.random() < 0.8 else rng.randrange(r)
            y = hub_y if rng.random() < 0.65 else rng.randrange(t)
        else:
            raise ValueError(sharing)
        edges.append((x, y)); x_degree[x] += 1; y_degree[y] += 1
    return edges[:s]


def generate_instance(family: str, n: int, sharing: str, seed: int) -> ControlInstance:
    if family not in ("H", "NH"):
        raise ValueError(family)
    r_count, t_count, s_count = _counts(n)
    edges = _edge_pattern(r_count, t_count, s_count, sharing, seed)
    r_facts = tuple(Fact(i, "R", f"x{i}") for i in range(r_count))
    s_start = r_count
    s_facts = tuple(
        Fact(s_start + j, "S", f"x{x}", f"y{y}")
        for j, (x, y) in enumerate(edges)
    )
    t_start = r_count + s_count
    t_facts = tuple(
        Fact(t_start + i, "T", f"x{i}" if family == "H" else f"y{i}")
        for i in range(t_count)
    )
    r_by_x = {fact.key1: fact for fact in r_facts}
    t_by_key = {fact.key1: fact for fact in t_facts}
    groundings = []
    for j, s_fact in enumerate(s_facts):
        r_fact = r_by_x[s_fact.key1]
        t_key = s_fact.key1 if family == "H" else s_fact.key2
        t_fact = t_by_key[t_key]
        groundings.append(
            Grounding(f"g{j}", frozenset({r_fact.player, s_fact.player, t_fact.player}), s_fact.key1)
        )
    return ControlInstance(family, n, sharing, seed, r_facts, s_facts, t_facts, tuple(groundings))


def active_groundings(instance: ControlInstance, mask: int) -> list[Grounding]:
    return [g for g in instance.groundings if all(mask & (1 << p) for p in g.clause)]


def query_values(instance: ControlInstance, mask: int) -> dict[str, float]:
    active = active_groundings(instance, mask)
    per_key: dict[str, int] = defaultdict(int)
    for grounding in active:
        per_key[grounding.output_key] += 1
    return {
        "BAG": float(len(active)),
        "DISTINCT": float(len(per_key)),
        "HAVING2": float(sum(count >= 2 for count in per_key.values())),
        "HAVING3": float(sum(count >= 3 for count in per_key.values())),
    }


def exact_shapley(values: list[float], n: int) -> list[float]:
    result = [0.0] * n
    for player in range(n):
        bit = 1 << player
        for mask in range(1 << n):
            if mask & bit:
                continue
            size = mask.bit_count()
            result[player] += (values[mask | bit] - values[mask]) / (n * math.comb(n - 1, size))
    return result


def bag_closed_form(instance: ControlInstance) -> list[float]:
    result = [0.0] * instance.n
    for grounding in instance.groundings:
        players = set(grounding.clause)
        for player in players:
            result[player] += 1.0 / len(players)
    return result


def evidence_deltas(instance: ControlInstance) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(int(player in grounding.clause) for grounding in instance.groundings)
        for player in range(instance.n)
    )


def query_from_evidence(instance: ControlInstance, state: tuple[int, ...], query: str) -> float:
    active = [
        grounding
        for grounding, count in zip(instance.groundings, state, strict=True)
        if count == len(grounding.clause)
    ]
    per_key: dict[str, int] = defaultdict(int)
    for grounding in active:
        per_key[grounding.output_key] += 1
    if query == "BAG":
        return float(len(active))
    if query == "DISTINCT":
        return float(len(per_key))
    threshold = 2 if query == "HAVING2" else 3
    return float(sum(count >= threshold for count in per_key.values()))


def minimal_witnesses(instance: ControlInstance, query: str) -> list[tuple[list[frozenset[str]], float, str]]:
    by_key: dict[str, list[Grounding]] = defaultdict(list)
    for grounding in instance.groundings:
        by_key[grounding.output_key].append(grounding)
    player_name = lambda p: f"p{p+1}"
    if query == "BAG":
        return [([frozenset(player_name(p) for p in g.clause)], 1.0, g.grounding_id) for g in instance.groundings]
    result = []
    threshold = None if query == "DISTINCT" else 2 if query == "HAVING2" else 3
    for key, items in sorted(by_key.items()):
        if threshold is None:
            clauses = {frozenset(player_name(p) for p in g.clause) for g in items}
        else:
            candidates = {
                frozenset(player_name(p) for g in combo for p in g.clause)
                for combo in itertools.combinations(items, threshold)
            }
            clauses = {c for c in candidates if not any(other < c for other in candidates)}
        if clauses:
            result.append((sorted(clauses, key=lambda c: (len(c), sorted(c))), 1.0, key))
    return result


def source_value(components, selected: set[str]) -> float:
    return sum(weight for dnf, weight, _ in components if any(clause <= selected for clause in dnf))


def old_base_state(instance: ControlInstance, mask: int) -> tuple[int, int, int]:
    return tuple(
        sum(1 for fact in facts if mask & (1 << fact.player))
        for facts in (instance.r_facts, instance.s_facts, instance.t_facts)
    )


def reachable_states(instance: ControlInstance) -> tuple[int, int]:
    base = set()
    evidence = set()
    deltas = evidence_deltas(instance)
    for mask in range(1 << instance.n):
        base.add(old_base_state(instance, mask))
        evidence.add(
            tuple(sum(delta[k] for p, delta in enumerate(deltas) if mask & (1 << p)) for k in range(len(instance.groundings)))
        )
    return len(base), len(evidence)


def min_fill_width(instance: ControlInstance) -> int:
    graph = {p: set() for p in range(instance.n)}
    for grounding in instance.groundings:
        for left in grounding.clause:
            graph[left].update(set(grounding.clause) - {left})
    width = 0
    while graph:
        def fill_cost(node):
            neighbors = list(graph[node])
            missing = sum(neighbors[j] not in graph[neighbors[i]] for i in range(len(neighbors)) for j in range(i + 1, len(neighbors)))
            return missing, len(neighbors), node
        node = min(graph, key=fill_cost)
        neighbors = list(graph[node]); width = max(width, len(neighbors))
        for a, b in itertools.combinations(neighbors, 2):
            graph[a].add(b); graph[b].add(a)
        for neighbor in neighbors:
            graph[neighbor].discard(node)
        del graph[node]
    return width


def joint_values(raw: dict[str, float], full: dict[str, float]) -> dict[str, float]:
    def cov(key):
        return 0.0 if full[key] == 0 else raw[key] / full[key]
    coords = [cov("BAG"), cov("DISTINCT"), cov("HAVING2"), cov("HAVING3")]
    g1 = 1000.0 * sum(coords) / 4
    geometric = 0.0 if any(v <= 0 for v in coords) else math.prod(coords) ** 0.25
    g2 = 1000.0 * (0.5 * sum(coords) / 4 + 0.5 * geometric)
    return {"G1": g1, "G2": g2}

