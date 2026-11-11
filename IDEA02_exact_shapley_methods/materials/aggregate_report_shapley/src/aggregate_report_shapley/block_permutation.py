from __future__ import annotations

from fractions import Fraction
from itertools import permutations, product
from math import comb, factorial
from typing import Iterable, Iterator, Sequence


def _bits(mask: int) -> tuple[int, ...]:
    return tuple(index for index in range(mask.bit_length()) if mask & (1 << index))


def _subsets(items: Sequence[int]) -> Iterator[tuple[int, int]]:
    for selector in range(1 << len(items)):
        mask = 0
        for position, item in enumerate(items):
            if selector & (1 << position):
                mask |= 1 << item
        yield mask, selector.bit_count()


def _validate_blocks(blocks: Sequence[int], player_count: int) -> None:
    union = 0
    for block in blocks:
        if union & block:
            raise ValueError("blocks must be disjoint")
        union |= block
    if union != (1 << player_count) - 1:
        raise ValueError("blocks must partition all players")


def block_contiguous_value(
    values: Sequence[Fraction], blocks: Sequence[int], player_count: int
) -> list[Fraction]:
    """Exact average over permutations where every block is contiguous."""
    _validate_blocks(blocks, player_count)
    result = [Fraction(0) for _ in range(player_count)]
    for player in range(player_count):
        bit = 1 << player
        own_index = next(index for index, block in enumerate(blocks) if block & bit)
        own_players = tuple(p for p in _bits(blocks[own_index]) if p != player)
        other_indices = tuple(index for index in range(len(blocks)) if index != own_index)
        for block_selector in range(1 << len(other_indices)):
            prefix_blocks = 0
            preceding_block_count = 0
            for position, block_index in enumerate(other_indices):
                if block_selector & (1 << position):
                    prefix_blocks |= blocks[block_index]
                    preceding_block_count += 1
            block_weight = Fraction(
                1,
                len(blocks) * comb(len(blocks) - 1, preceding_block_count),
            )
            for within_mask, within_size in _subsets(own_players):
                within_weight = Fraction(
                    1,
                    blocks[own_index].bit_count()
                    * comb(blocks[own_index].bit_count() - 1, within_size),
                )
                prefix = prefix_blocks | within_mask
                result[player] += (
                    block_weight
                    * within_weight
                    * (values[prefix | bit] - values[prefix])
                )
    return result


def allowed_block_permutation_count(blocks: Sequence[int]) -> int:
    return factorial(len(blocks)) * product_int(factorial(block.bit_count()) for block in blocks)


def product_int(values: Iterable[int]) -> int:
    result = 1
    for value in values:
        result *= value
    return result


def enumerate_block_permutations(blocks: Sequence[int]) -> Iterator[tuple[int, ...]]:
    players = [tuple(_bits(block)) for block in blocks]
    internal = [tuple(permutations(group)) for group in players]
    for block_order in permutations(range(len(blocks))):
        for ordered_groups in product(*(internal[index] for index in block_order)):
            yield tuple(player for group in ordered_groups for player in group)


def permutation_average(
    values: Sequence[Fraction], permutations_iter: Iterable[Sequence[int]], player_count: int
) -> tuple[list[Fraction], int]:
    totals = [Fraction(0) for _ in range(player_count)]
    count = 0
    for ordering in permutations_iter:
        mask = 0
        for player in ordering:
            next_mask = mask | (1 << player)
            totals[player] += values[next_mask] - values[mask]
            mask = next_mask
        count += 1
    if count == 0:
        raise ValueError("at least one permutation is required")
    return [total / count for total in totals], count

