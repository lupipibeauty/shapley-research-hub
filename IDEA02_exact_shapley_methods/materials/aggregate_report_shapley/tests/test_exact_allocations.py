from __future__ import annotations

from fractions import Fraction

from aggregate_report_shapley.block_permutation import (
    allowed_block_permutation_count,
    block_contiguous_value,
    enumerate_block_permutations,
    permutation_average,
)
from aggregate_report_shapley.d1 import (
    D1_CELLS,
    D1_CITY_BLOCKS,
    D1_LEVELS,
    D1_MEMBERSHIP,
    D1_RECORDS,
    D1_REGION_BLOCKS,
)
from aggregate_report_shapley.exact_shapley import efficiency_error, exact_shapley_subset
from aggregate_report_shapley.report_state import all_coalition_states
from aggregate_report_shapley.shapley_levels import (
    harsanyi_dividends,
    shapley_from_dividends,
    shapley_levels_by_permutations,
    shapley_levels_from_dividends,
)
from aggregate_report_shapley.value_functions import D1ValueSuite


def value_tables() -> dict[str, list[Fraction]]:
    states = all_coalition_states(D1_RECORDS, D1_MEMBERSHIP, D1_CELLS)
    return D1ValueSuite(states[-1]).all_values(states)


def test_exact_standard_shapley_has_independent_dividend_check() -> None:
    for name, values in value_tables().items():
        subset = exact_shapley_subset(values, 12)
        dividend = shapley_from_dividends(harsanyi_dividends(values), 12)
        assert subset == dividend, name
        assert efficiency_error(subset, values) == 0


def test_v0_is_equal_under_every_allocation_rule() -> None:
    values = value_tables()["V0"]
    expected = [Fraction(25, 3)] * 12
    assert exact_shapley_subset(values, 12) == expected
    assert block_contiguous_value(values, D1_CITY_BLOCKS, 12) == expected
    assert block_contiguous_value(values, D1_REGION_BLOCKS, 12) == expected
    assert shapley_levels_from_dividends(values, D1_LEVELS, 12) == expected


def test_block_counts_and_city_formula_enumeration() -> None:
    assert allowed_block_permutation_count(D1_REGION_BLOCKS) == 1_935_360
    assert allowed_block_permutation_count(D1_CITY_BLOCKS) == 55_296
    values = value_tables()["V1"]
    formula = block_contiguous_value(values, D1_CITY_BLOCKS, 12)
    enumerated, count = permutation_average(values, enumerate_block_permutations(D1_CITY_BLOCKS), 12)
    assert count == 55_296
    assert formula == enumerated


def test_shapley_levels_permutations_equal_dividend_formula() -> None:
    for name in ("V1", "V2"):
        values = value_tables()[name]
        enumerated, count = shapley_levels_by_permutations(values, 12)
        dividends = shapley_levels_from_dividends(values, D1_LEVELS, 12)
        assert count == 18_432
        assert enumerated == dividends, name
        assert efficiency_error(enumerated, values) == 0

