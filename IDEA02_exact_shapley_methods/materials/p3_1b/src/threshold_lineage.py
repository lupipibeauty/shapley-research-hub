"""P3-1B: derive threshold games from fixture-level JOIN witnesses only."""
from __future__ import annotations

import itertools
import json
import math
from collections import defaultdict
from fractions import Fraction
from pathlib import Path


def load_fixture(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def entity_witnesses(fixture: dict) -> tuple[dict[str, str], dict[str, list[frozenset[int]]]]:
    """Construct e AND (OR link-and-valid-attribute) witnesses from base facts."""
    entities = {r["entity_id"]: r for r in fixture["entities"]}
    attrs = {r["attribute_id"]: r for r in fixture["attributes"] if r["valid"]}
    witnesses: dict[str, list[frozenset[int]]] = defaultdict(list)
    for link in fixture["links"]:
        entity = entities.get(link["entity_id"])
        attr = attrs.get(link["attribute_id"])
        if entity is None or attr is None:
            continue
        witnesses[entity["entity_id"]].append(frozenset((entity["player_index"], link["player_index"], attr["player_index"])))
    return {e: r["group_id"] for e, r in entities.items()}, dict(witnesses)


def _minimal(sets: list[frozenset[int]]) -> list[frozenset[int]]:
    accepted: list[frozenset[int]] = []
    for candidate in sorted(set(sets), key=lambda x: (len(x), tuple(sorted(x)))):
        if not any(previous <= candidate for previous in accepted):
            accepted.append(candidate)
    return accepted


def minimal_winning_coalitions(group_of: dict[str, str], witnesses: dict[str, list[frozenset[int]]], threshold: int) -> list[frozenset[int]]:
    """Build minimal winners of H_t without consulting coalition truth."""
    by_group: dict[str, list[str]] = defaultdict(list)
    for entity, group in group_of.items():
        if witnesses.get(entity):
            by_group[group].append(entity)
    group_terms: list[list[frozenset[int]]] = []
    for group in ("A", "B"):
        terms: list[frozenset[int]] = []
        for entities in itertools.combinations(sorted(by_group[group]), threshold):
            for selected in itertools.product(*(witnesses[e] for e in entities)):
                terms.append(frozenset().union(*selected))
        group_terms.append(_minimal(terms))
    return _minimal([left | right for left in group_terms[0] for right in group_terms[1]])


def coalition_wins(mask: int, winners: list[frozenset[int]]) -> int:
    return int(any(all(mask & (1 << player) for player in coalition) for coalition in winners))


def exact_shapley_from_winners(n: int, winners: list[frozenset[int]]) -> list[Fraction]:
    """Exact standard Shapley via the simple-game DNF, without an oracle table."""
    fact = [math.factorial(i) for i in range(n + 1)]
    phi: list[Fraction] = []
    for player in range(n):
        value = Fraction()
        bit = 1 << player
        for coalition in range(1 << n):
            if coalition & bit:
                continue
            k = coalition.bit_count()
            marginal = coalition_wins(coalition | bit, winners) - coalition_wins(coalition, winners)
            value += Fraction(fact[k] * fact[n - k - 1], fact[n]) * marginal
        phi.append(value)
    return phi


def winner_rows(winners: list[frozenset[int]], player_ids: dict[int, str], threshold: int) -> list[dict]:
    return [{"threshold": threshold, "winner_id": f"H{threshold}_W{j:02d}",
             "player_indices": "|".join(map(str, sorted(c))),
             "player_ids": "|".join(player_ids[i] for i in sorted(c)), "size": len(c)}
            for j, c in enumerate(winners, 1)]
