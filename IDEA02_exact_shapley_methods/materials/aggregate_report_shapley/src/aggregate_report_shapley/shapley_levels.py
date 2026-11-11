from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import permutations, product
from typing import Iterator, Sequence

from .block_permutation import permutation_average


@dataclass(frozen=True, slots=True)
class HierarchyNode:
    children: tuple["HierarchyNode | int", ...]


def hierarchy_permutations(node: HierarchyNode | int) -> Iterator[tuple[int, ...]]:
    if isinstance(node, int):
        yield (node,)
        return
    child_permutations = {
        id(child): tuple(hierarchy_permutations(child)) for child in node.children
    }
    for child_order in permutations(node.children):
        for sequences in product(*(child_permutations[id(child)] for child in child_order)):
            yield tuple(player for sequence in sequences for player in sequence)


def d1_hierarchy_tree() -> HierarchyNode:
    city_s1 = HierarchyNode((0, 1))
    city_s2 = HierarchyNode((2, 3))
    city_l1 = HierarchyNode((4, 5, 6, 7))
    city_l2 = HierarchyNode((8, 9, 10, 11))
    region_s = HierarchyNode((city_s1, city_s2))
    region_l = HierarchyNode((city_l1, city_l2))
    return HierarchyNode((region_s, region_l))


def shapley_levels_by_permutations(
    values: Sequence[Fraction], player_count: int
) -> tuple[list[Fraction], int]:
    return permutation_average(values, hierarchy_permutations(d1_hierarchy_tree()), player_count)


def harsanyi_dividends(values: Sequence[Fraction]) -> list[Fraction]:
    dividends = [Fraction(0) for _ in values]
    dividends[0] = values[0]
    for mask in range(1, len(values)):
        subtotal = Fraction(0)
        subset = (mask - 1) & mask
        while subset:
            subtotal += dividends[subset]
            subset = (subset - 1) & mask
        subtotal += dividends[0]
        dividends[mask] = values[mask] - subtotal
    return dividends


def shapley_from_dividends(dividends: Sequence[Fraction], player_count: int) -> list[Fraction]:
    result = [Fraction(0) for _ in range(player_count)]
    for mask in range(1, len(dividends)):
        if dividends[mask] == 0:
            continue
        share = dividends[mask] / mask.bit_count()
        for player in range(player_count):
            if mask & (1 << player):
                result[player] += share
    return result


def shapley_levels_from_dividends(
    values: Sequence[Fraction],
    levels: Sequence[Sequence[int]],
    player_count: int,
) -> list[Fraction]:
    """Besner/Calvo dividend formula, Eq. (4)-(5), on complete coalitions."""
    dividends = harsanyi_dividends(values)
    result = [Fraction(0) for _ in range(player_count)]
    for coalition in range(1, len(values)):
        dividend = dividends[coalition]
        if dividend == 0:
            continue
        for player in range(player_count):
            bit = 1 << player
            if not coalition & bit:
                continue
            coefficient = Fraction(1)
            for level_index in range(len(levels) - 1):
                parent = next(
                    component
                    for component in levels[level_index + 1]
                    if component & bit
                )
                touched_children = sum(
                    1
                    for component in levels[level_index]
                    if component & parent == component and component & coalition
                )
                if touched_children == 0:
                    raise AssertionError("player coalition must touch its hierarchy path")
                coefficient /= touched_children
            result[player] += coefficient * dividend
    return result

