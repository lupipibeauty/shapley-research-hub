from __future__ import annotations

from fractions import Fraction
from math import comb
from decimal import Decimal, localcontext
from typing import Sequence


def exact_shapley_subset(values: Sequence[Fraction], player_count: int) -> list[Fraction]:
    if len(values) != 1 << player_count:
        raise ValueError("values must contain one entry for every coalition")
    result = [Fraction(0) for _ in range(player_count)]
    full_mask = (1 << player_count) - 1
    for player in range(player_count):
        bit = 1 << player
        for mask in range(full_mask + 1):
            if mask & bit:
                continue
            size = mask.bit_count()
            weight = Fraction(1, player_count * comb(player_count - 1, size))
            result[player] += weight * (values[mask | bit] - values[mask])
    return result


def efficiency_error(allocation: Sequence[Fraction], values: Sequence[Fraction]) -> Fraction:
    return abs(sum(allocation, Fraction(0)) - (values[-1] - values[0]))


def exact_shapley_decimal(
    values: Sequence[Decimal], player_count: int, *, precision: int = 100
) -> list[Decimal]:
    if len(values) != 1 << player_count:
        raise ValueError("values must contain one entry for every coalition")
    with localcontext() as context:
        context.prec = precision
        result = [Decimal(0) for _ in range(player_count)]
        for player in range(player_count):
            bit = 1 << player
            for mask in range(1 << player_count):
                if mask & bit:
                    continue
                size = mask.bit_count()
                weight = Decimal(1) / Decimal(player_count * comb(player_count - 1, size))
                result[player] += weight * (values[mask | bit] - values[mask])
        return [+value for value in result]


def shapley_via_mobius_fraction(values: Sequence[Fraction], player_count: int) -> list[Fraction]:
    dividends = list(values)
    for player in range(player_count):
        bit = 1 << player
        for mask in range(1 << player_count):
            if mask & bit:
                dividends[mask] -= dividends[mask ^ bit]
    result = [Fraction() for _ in range(player_count)]
    for mask in range(1, 1 << player_count):
        share = dividends[mask] / mask.bit_count()
        for player in range(player_count):
            if mask & (1 << player):
                result[player] += share
    return result


def shapley_via_mobius_decimal(
    values: Sequence[Decimal], player_count: int, *, precision: int = 100
) -> list[Decimal]:
    with localcontext() as context:
        context.prec = precision
        dividends = list(values)
        for player in range(player_count):
            bit = 1 << player
            for mask in range(1 << player_count):
                if mask & bit:
                    dividends[mask] -= dividends[mask ^ bit]
        result = [Decimal(0) for _ in range(player_count)]
        for mask in range(1, 1 << player_count):
            share = dividends[mask] / Decimal(mask.bit_count())
            for player in range(player_count):
                if mask & (1 << player):
                    result[player] += share
        return [+value for value in result]

