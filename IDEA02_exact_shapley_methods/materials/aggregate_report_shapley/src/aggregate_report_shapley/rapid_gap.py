from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True, slots=True)
class RapidInstance:
    design: str
    n: int
    source_scopes: tuple[tuple[int, ...], ...]
    value_scopes: tuple[tuple[int, ...], ...]
    source_weights: tuple[float, ...]
    value_weights: tuple[float, ...]
    revenue: float = 1000.0


@dataclass(slots=True)
class Factor:
    scope: tuple[int, ...]
    table: dict[tuple[int, ...], np.ndarray]


def make_instance(design: str, n: int) -> RapidInstance:
    if design not in {"ALIGNED", "CROSSED"} or n not in {12, 16}:
        raise ValueError((design, n))
    groups = n // 4
    source = tuple(tuple(range(4 * g, 4 * g + 4)) for g in range(groups))
    if design == "ALIGNED":
        value = source
    elif n == 16:
        value = tuple(tuple(4 * r + c for r in range(4)) for c in range(4))
    else:
        buckets = [[] for _ in range(3)]
        for r in range(3):
            for c in range(4):
                buckets[(r + c) % 3].append(4 * r + c)
        value = tuple(tuple(bucket) for bucket in buckets)
    assert sorted(p for scope in value for p in scope) == list(range(n))
    return RapidInstance(
        design=design,
        n=n,
        source_scopes=source,
        value_scopes=value,
        source_weights=tuple(0.18 + 0.02 * g for g in range(groups)),
        value_weights=tuple(0.27 + 0.02 * g for g in range(groups)),
    )


def raw_product(instance: RapidInstance, mask: int) -> float:
    result = 1.0
    for scope, weight in zip(instance.source_scopes, instance.source_weights, strict=True):
        count = sum(bool(mask & (1 << p)) for p in scope)
        result *= 1.0 + weight * count / len(scope)
    for scope, weight in zip(instance.value_scopes, instance.value_weights, strict=True):
        count = sum(bool(mask & (1 << p)) for p in scope)
        result *= 1.0 + weight * count / len(scope)
    return result


def coalition_values(instance: RapidInstance) -> list[float]:
    raw = [raw_product(instance, mask) for mask in range(1 << instance.n)]
    lo, hi = raw[0], raw[-1]
    return [instance.revenue * (value - lo) / (hi - lo) for value in raw]


def exact_shapley(values: list[float], n: int) -> list[float]:
    result = [0.0] * n
    for player in range(n):
        bit = 1 << player
        for mask in range(1 << n):
            if mask & bit:
                continue
            k = mask.bit_count()
            result[player] += (values[mask | bit] - values[mask]) / (n * math.comb(n - 1, k))
    return result


def primal_graph(n: int, scopes: Iterable[tuple[int, ...]]) -> dict[int, set[int]]:
    graph = {p: set() for p in range(n)}
    for scope in scopes:
        for left, right in itertools.combinations(scope, 2):
            graph[left].add(right)
            graph[right].add(left)
    return graph


def min_fill_order(graph: dict[int, set[int]]) -> tuple[int, tuple[int, ...]]:
    work = {node: set(neighbors) for node, neighbors in graph.items()}
    width = 0
    order: list[int] = []
    while work:
        def key(node: int) -> tuple[int, int, int]:
            neighbors = list(work[node])
            missing = sum(b not in work[a] for a, b in itertools.combinations(neighbors, 2))
            return missing, len(neighbors), node
        node = min(work, key=key)
        neighbors = list(work[node])
        width = max(width, len(neighbors))
        for a, b in itertools.combinations(neighbors, 2):
            work[a].add(b); work[b].add(a)
        for neighbor in neighbors:
            work[neighbor].discard(node)
        del work[node]
        order.append(node)
    return width, tuple(order)


def exact_treewidth(graph: dict[int, set[int]]) -> int:
    """Exact elimination width by subset DP; intended only for n<=16.

    After eliminating S, v is adjacent to each non-eliminated u reachable from v
    through a path whose internal vertices lie in S. This makes the current
    degree a function of S alone and supports the standard 2^n subset DP.
    """
    nodes = tuple(sorted(graph))
    n = len(nodes)
    if nodes != tuple(range(n)):
        raise ValueError("exact_treewidth expects vertices 0..n-1")
    infinity = n + 1
    dp = [infinity] * (1 << n)
    dp[0] = 0
    for mask in range(1 << n):
        if dp[mask] == infinity:
            continue
        for v in range(n):
            bit = 1 << v
            if mask & bit:
                continue
            frontier = [u for u in graph[v] if mask & (1 << u)]
            visited = set(frontier)
            boundary = {u for u in graph[v] if not (mask & (1 << u)) and u != v}
            while frontier:
                current = frontier.pop()
                for u in graph[current]:
                    if u == v:
                        continue
                    if mask & (1 << u):
                        if u not in visited:
                            visited.add(u); frontier.append(u)
                    else:
                        boundary.add(u)
            width = len(boundary)
            nxt = mask | bit
            candidate = max(dp[mask], width)
            if candidate < dp[nxt]:
                dp[nxt] = candidate
    return dp[-1]


def local_factors(instance: RapidInstance) -> list[Factor]:
    factors: list[Factor] = []
    specs = list(zip(instance.source_scopes, instance.source_weights, strict=True))
    specs += list(zip(instance.value_scopes, instance.value_weights, strict=True))
    for scope, weight in specs:
        table = {}
        for assignment in itertools.product((0, 1), repeat=len(scope)):
            scalar = 1.0 + weight * sum(assignment) / len(scope)
            table[assignment] = np.asarray([scalar], dtype=float)
        factors.append(Factor(tuple(scope), table))
    return factors


def _restrict(factor: Factor, variable: int, value: int) -> Factor:
    if variable not in factor.scope:
        return factor
    index = factor.scope.index(variable)
    scope = factor.scope[:index] + factor.scope[index + 1 :]
    table = {assignment[:index] + assignment[index + 1 :]: poly for assignment, poly in factor.table.items() if assignment[index] == value}
    return Factor(scope, table)


def _multiply(items: list[Factor]) -> Factor:
    if not items:
        return Factor((), {(): np.asarray([1.0])})
    scope = tuple(sorted({v for item in items for v in item.scope}))
    positions = [{v: item.scope.index(v) for v in item.scope} for item in items]
    table: dict[tuple[int, ...], np.ndarray] = {}
    for assignment in itertools.product((0, 1), repeat=len(scope)):
        lookup = dict(zip(scope, assignment, strict=True))
        poly = np.asarray([1.0])
        for item, pos in zip(items, positions, strict=True):
            key = tuple(lookup[v] for v in item.scope)
            poly = np.convolve(poly, item.table[key])
        table[assignment] = poly
    return Factor(scope, table)


def _eliminate(factors: list[Factor], variable: int) -> tuple[list[Factor], int]:
    selected = [factor for factor in factors if variable in factor.scope]
    untouched = [factor for factor in factors if variable not in factor.scope]
    product = _multiply(selected)
    index = product.scope.index(variable)
    new_scope = product.scope[:index] + product.scope[index + 1 :]
    table: dict[tuple[int, ...], np.ndarray] = {}
    for assignment in itertools.product((0, 1), repeat=len(new_scope)):
        a0 = assignment[:index] + (0,) + assignment[index:]
        a1 = assignment[:index] + (1,) + assignment[index:]
        p0 = product.table[a0]
        p1 = np.pad(product.table[a1], (1, 0))
        p0 = np.pad(p0, (0, max(0, len(p1) - len(p0))))
        p1 = np.pad(p1, (0, max(0, len(p0) - len(p1))))
        table[assignment] = p0 + p1
    result = Factor(new_scope, table)
    entries = sum(len(poly) for poly in table.values())
    return untouched + [result], entries


def cardinality_partition(instance: RapidInstance, focal: int, focal_value: int, base_factors: list[Factor] | None = None) -> tuple[np.ndarray, dict[str, int]]:
    factors = [_restrict(factor, focal, focal_value) for factor in (base_factors or local_factors(instance))]
    graph = primal_graph(instance.n, instance.source_scopes + instance.value_scopes)
    graph.pop(focal)
    for neighbors in graph.values():
        neighbors.discard(focal)
    _, order = min_fill_order(graph)
    max_entries = 0
    writes = 0
    for variable in order:
        factors, entries = _eliminate(factors, variable)
        max_entries = max(max_entries, entries)
        writes += entries
    final = _multiply(factors)
    return final.table[()], {"max_intermediate_entries": max_entries, "factor_entry_writes": writes}


def shapley_variable_elimination(instance: RapidInstance, base_factors: list[Factor] | None = None) -> tuple[list[float], dict[str, int]]:
    base_factors = base_factors or local_factors(instance)
    empty = raw_product(instance, 0)
    full = raw_product(instance, (1 << instance.n) - 1)
    scale = instance.revenue / (full - empty)
    result: list[float] = []
    max_entries = writes = 0
    for focal in range(instance.n):
        z0, m0 = cardinality_partition(instance, focal, 0, base_factors)
        z1, m1 = cardinality_partition(instance, focal, 1, base_factors)
        value = 0.0
        for k in range(instance.n):
            value += (z1[k] - z0[k]) / (instance.n * math.comb(instance.n - 1, k))
        result.append(scale * value)
        max_entries = max(max_entries, m0["max_intermediate_entries"], m1["max_intermediate_entries"])
        writes += m0["factor_entry_writes"] + m1["factor_entry_writes"]
    return result, {"max_intermediate_entries": max_entries, "factor_entry_writes": writes}
