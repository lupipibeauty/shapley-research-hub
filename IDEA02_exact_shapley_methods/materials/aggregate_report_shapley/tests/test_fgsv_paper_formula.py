from __future__ import annotations

import numpy as np
import pytest

from aggregate_report_shapley.fgsv_paper_formula import (
    equation8_coefficient,
    paper_formula_fgsv_budget_capped,
    sample_equation11_consistent_pair,
)


class AdditiveUtility:
    def __init__(self, weights: list[float]):
        self.weights = np.asarray(weights, dtype=float)
        self.calls = 0

    def __call__(self, selection) -> float:
        self.calls += 1
        indexes = np.asarray(selection, dtype=int)
        return float(self.weights[indexes].sum()) if len(indexes) else 0.0


def test_equation8_missing_factor_for_n2_is_two() -> None:
    # p(s1=1)=1/2 and n/[s(n-s)]*(s1-E[s1]) = 2*(1/2), so coefficient=1/2.
    assert equation8_coefficient(n=2, s0=1, s=1, s1=1) == pytest.approx(0.5)


def test_n2_additive_game_is_analytic_and_exact() -> None:
    utility = AdditiveUtility([1.0, 0.0])
    result = paper_formula_fgsv_budget_capped(
        utility,
        n=2,
        group=[0],
        budget=4,
        rng=np.random.RandomState(7),
        threshold=10,
    )
    assert result["estimate"] == pytest.approx(1.0)
    assert utility.calls == 4
    assert result["padding_calls"] == 0


def test_n3_additive_game_exercises_large_branch() -> None:
    utility = AdditiveUtility([1.0, 2.0, 4.0])
    # threshold=2: s=1 uses Eq. (8), s=2 uses Eq. (9) and paired Eq. (11) repair.
    result = paper_formula_fgsv_budget_capped(
        utility,
        n=3,
        group=[0, 1],
        budget=7,
        rng=np.random.RandomState(11),
        threshold=2,
    )
    assert result["estimate"] == pytest.approx(3.0)
    assert utility.calls == 7
    assert result["padding_calls"] == 0


@pytest.mark.parametrize("s", [1, 2])
def test_consistent_pair_has_fixed_size_and_adjacent_intersections(s: int) -> None:
    group = np.asarray([0, 1], dtype=int)
    complement = np.asarray([2], dtype=int)
    upper, lower, k = sample_equation11_consistent_pair(
        n=3,
        group=group,
        complement=complement,
        s=s,
        rng=np.random.RandomState(19 + s),
    )
    assert len(upper) == len(lower) == s
    assert len(set(upper) & set(group)) == k + 1
    assert len(set(lower) & set(group)) == k
