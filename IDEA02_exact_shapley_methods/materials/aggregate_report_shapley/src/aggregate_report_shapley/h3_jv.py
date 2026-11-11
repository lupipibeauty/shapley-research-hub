from __future__ import annotations

import math
import random
from dataclasses import dataclass
from fractions import Fraction
from typing import Callable, Iterable


PLAYERS = tuple(f"p{i}" for i in range(1, 13))
LEAVES = ("A1", "A2", "B1", "B2")
NODES = LEAVES + ("PA", "PB", "NAT")
METRICS = ("bag_count", "distinct_count", "amount_sum", "target_count", "target_distinct_count")
PARENTS = {"A1": "PA", "A2": "PA", "B1": "PB", "B2": "PB"}
REVENUE = 1000.0
LAMBDA = 0.5


@dataclass(frozen=True, slots=True)
class Fact:
    record_id: str
    player: str
    leaf: str
    category: str
    amount: int
    entity_key: str = ""
    event_key: str = ""


@dataclass(frozen=True, slots=True)
class RelationFact:
    record_id: str
    player: str
    entity_key: str
    event_key: str
    weight: int


@dataclass(frozen=True, slots=True)
class Grounding:
    grounding_id: str
    clause: frozenset[int]
    leaf: str
    category: str
    amount: int
    business_key: str
    branch: str


@dataclass(frozen=True, slots=True)
class JVInstance:
    seed: int
    basic: tuple[Fact, ...]
    events: tuple[Fact, ...]
    relations: tuple[RelationFact, ...]
    j0_facts: tuple[Fact, ...]


def ancestors(leaf: str) -> tuple[str, str, str]:
    return leaf, PARENTS[leaf], "NAT"


def generate_instance(seed: int = 7301) -> JVInstance:
    # Dihedral permutations preserve alternating target/non-target event categories.
    base = [0, 1, 2, 3]
    selector = abs(seed) % 8
    shift = selector % 4
    order = base[shift:] + base[:shift]
    if selector >= 4:
        order = [order[0], order[3], order[2], order[1]]

    basic = tuple(
        Fact(f"b{i+1}", PLAYERS[i], LEAVES[i], "C1" if i % 2 else "C2", 1 + (i % 2), entity_key=f"x{i+1}")
        for i in range(4)
    )
    events = tuple(
        Fact(f"e{i+1}", PLAYERS[4 + i], LEAVES[i], "C1" if i % 2 == 0 else "C2", 1 + ((i + 1) % 2), event_key=f"y{i+1}")
        for i in range(4)
    )
    relations: list[RelationFact] = []
    for i in range(4):
        for edge_no, event_index in enumerate((order[i], order[(i + 1) % 4]), start=1):
            relations.append(
                RelationFact(
                    f"s{i+1}_{edge_no}", PLAYERS[8 + i], f"x{i+1}", f"y{event_index+1}", 1
                )
            )
    relation_facts = tuple(
        Fact(f"sp{i+1}", PLAYERS[8 + i], LEAVES[i], "C1" if i % 2 == 0 else "C2", 1 + (i % 2))
        for i in range(4)
    )
    return JVInstance(seed, basic, events, tuple(relations), basic + events + relation_facts)


def player_index(player: str) -> int:
    return PLAYERS.index(player)


def groundings(instance: JVInstance, join_id: str) -> tuple[Grounding, ...]:
    if join_id == "J0":
        return tuple(
            Grounding(
                f"J0_{fact.record_id}", frozenset({player_index(fact.player)}), fact.leaf,
                fact.category, fact.amount, f"I_{fact.record_id}", "INDEPENDENT"
            )
            for fact in instance.j0_facts
        )
    basic_by_x = {fact.entity_key: fact for fact in instance.basic}
    event_by_y = {fact.event_key: fact for fact in instance.events}
    result: list[Grounding] = []
    if join_id == "J1":
        for rel in instance.relations:
            basic = basic_by_x[rel.entity_key]
            event = event_by_y[rel.event_key]
            result.append(
                Grounding(
                    f"J1_BS_{rel.record_id}",
                    frozenset({player_index(basic.player), player_index(rel.player)}),
                    basic.leaf, basic.category, basic.amount + rel.weight,
                    f"X_{rel.entity_key}", "BASIC_RELATION",
                )
            )
            result.append(
                Grounding(
                    f"J1_SE_{rel.record_id}",
                    frozenset({player_index(rel.player), player_index(event.player)}),
                    event.leaf, event.category, event.amount + rel.weight,
                    f"Y_{rel.event_key}", "RELATION_EVENT",
                )
            )
        return tuple(result)
    if join_id == "J2":
        for rel in instance.relations:
            basic = basic_by_x[rel.entity_key]
            event = event_by_y[rel.event_key]
            result.append(
                Grounding(
                    f"J2_{rel.record_id}",
                    frozenset(
                        {player_index(basic.player), player_index(rel.player), player_index(event.player)}
                    ),
                    basic.leaf, event.category, basic.amount + event.amount + rel.weight,
                    f"Y_{rel.event_key}", "BASIC_RELATION_EVENT",
                )
            )
        return tuple(result)
    raise ValueError(join_id)


def empty_report() -> dict[tuple[str, str], int]:
    return {(node, metric): 0 for node in NODES for metric in METRICS}


def report_from_active(items: Iterable[Grounding]) -> dict[tuple[str, str], int]:
    active = tuple(items)
    report = empty_report()
    for node in NODES:
        local = [item for item in active if node in ancestors(item.leaf)]
        report[(node, "bag_count")] = len(local)
        report[(node, "distinct_count")] = len({item.business_key for item in local})
        report[(node, "amount_sum")] = sum(item.amount for item in local)
        target = [item for item in local if item.category == "C1"]
        report[(node, "target_count")] = len(target)
        report[(node, "target_distinct_count")] = len({item.business_key for item in target})
    return report


def report_for_mask(items: tuple[Grounding, ...], mask: int) -> dict[tuple[str, str], int]:
    return report_from_active(
        item for item in items if all(mask & (1 << player) for player in item.clause)
    )


def report_signature(report: dict[tuple[str, str], int]) -> tuple[int, ...]:
    return tuple(report[(node, metric)] for node in NODES for metric in METRICS)


def score_ratio(target: int, total: int, full_target: int, full_total: int) -> float:
    if full_total == 0:
        return 0.0
    return total / full_total - abs(target * full_total - total * full_target) / (full_total**2)


def make_value_functions(
    full: dict[tuple[str, str], int],
) -> dict[str, Callable[[dict[tuple[str, str], int]], float]]:
    def coverage(current: int, reference: int) -> float:
        return 0.0 if reference == 0 else current / reference

    def g0(report: dict[tuple[str, str], int]) -> float:
        scores = [coverage(report[key], full[key]) for key in full]
        return REVENUE * sum(scores) / len(scores)

    def coordinate_scores(report: dict[tuple[str, str], int]) -> list[float]:
        scores: list[float] = []
        for node in NODES:
            for metric in METRICS[:4]:
                scores.append(coverage(report[(node, metric)], full[(node, metric)]))
            scores.append(
                score_ratio(
                    report[(node, "target_count")], report[(node, "bag_count")],
                    full[(node, "target_count")], full[(node, "bag_count")],
                )
            )
        return scores

    def g1(report: dict[tuple[str, str], int]) -> float:
        scores = coordinate_scores(report)
        return REVENUE * sum(scores) / len(scores)

    def g2(report: dict[tuple[str, str], int]) -> float:
        families = []
        families.append(sum(coverage(report[(n, "bag_count")], full[(n, "bag_count")]) for n in NODES) / 7)
        families.append(sum(coverage(report[(n, "distinct_count")], full[(n, "distinct_count")]) for n in NODES) / 7)
        families.append(sum(coverage(report[(n, "amount_sum")], full[(n, "amount_sum")]) for n in NODES) / 7)
        families.append(
            sum(
                score_ratio(
                    report[(n, "target_count")], report[(n, "bag_count")],
                    full[(n, "target_count")], full[(n, "bag_count")],
                )
                for n in NODES
            ) / 7
        )
        arithmetic = sum(families) / 4
        geometric = 0.0 if any(value <= 0 for value in families) else math.prod(families) ** 0.25
        return REVENUE * ((1 - LAMBDA) * arithmetic + LAMBDA * geometric)

    return {"G0": g0, "G1": g1, "G2": g2}


def exact_shapley(values: list[float], n: int = 12) -> list[float]:
    result = [0.0] * n
    for player in range(n):
        bit = 1 << player
        for mask in range(1 << n):
            if mask & bit:
                continue
            size = mask.bit_count()
            result[player] += (values[mask | bit] - values[mask]) / (n * math.comb(n - 1, size))
    return result


def evidence_deltas(items: tuple[Grounding, ...]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(player in item.clause) for item in items) for player in range(12))


def report_from_evidence_state(
    items: tuple[Grounding, ...], state: tuple[int, ...]
) -> dict[tuple[str, str], int]:
    return report_from_active(
        item for item, selected_count in zip(items, state, strict=True) if selected_count == len(item.clause)
    )


def old_d1p_state(instance: JVInstance, mask: int) -> tuple[int, ...]:
    state = [0] * 16
    for index, fact in enumerate(instance.j0_facts):
        if mask & (1 << index):
            offset = LEAVES.index(fact.leaf) * 4
            state[offset] += 1
            state[offset + 1] += int(fact.category == "C1")
            state[offset + 2] += fact.amount
            state[offset + 3] += 0
    return tuple(state)


def lineage_components(
    items: tuple[Grounding, ...], full: dict[tuple[str, str], int]
) -> list[tuple[list[frozenset[str]], Fraction, str, str]]:
    """Exact additive G0 output-unit components for Abramovich/Luo audits."""
    components: list[tuple[list[frozenset[str]], Fraction, str, str]] = []
    coordinate_weight = Fraction(1000, 35)
    for node in NODES:
        local = [item for item in items if node in ancestors(item.leaf)]
        for item in local:
            clause = frozenset(PLAYERS[player] for player in item.clause)
            components.append(([clause], coordinate_weight / full[(node, "bag_count")], node, "bag_count"))
            components.append(
                ([clause], coordinate_weight * item.amount / full[(node, "amount_sum")], node, "amount_sum")
            )
            if item.category == "C1":
                components.append(
                    ([clause], coordinate_weight / full[(node, "target_count")], node, "target_count")
                )
        for metric, eligible in (
            ("distinct_count", local),
            ("target_distinct_count", [item for item in local if item.category == "C1"]),
        ):
            by_key: dict[str, list[frozenset[str]]] = {}
            for item in eligible:
                by_key.setdefault(item.business_key, []).append(
                    frozenset(PLAYERS[player] for player in item.clause)
                )
            for dnf in by_key.values():
                components.append((dnf, coordinate_weight / full[(node, metric)], node, metric))
    return components

