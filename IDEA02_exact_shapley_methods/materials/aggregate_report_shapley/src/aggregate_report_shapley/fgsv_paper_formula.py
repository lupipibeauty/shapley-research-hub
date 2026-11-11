"""Independent implementation of the internally consistent FGSV paper formulas.

This module deliberately does not import or call the official release implementation.
Equation (11) in the paper states ``|S| = s`` and then adds one element, which would
produce coalitions of size ``s + 1``.  To estimate the fixed-size difference required
by Equation (9) and Algorithm 1, the paired sampler below uses a base coalition of
size ``s - 1``.  Adding an in-group or out-group element then gives two coalitions of
size ``s`` with intersection sizes ``k + 1`` and ``k`` respectively.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

import numpy as np
from scipy.stats import hypergeom


class Utility(Protocol):
    calls: int

    def __call__(self, selection: Sequence[int] | np.ndarray) -> float: ...


@dataclass(frozen=True)
class FormulaSamplePlan:
    """Budget allocation corresponding to Algorithm 1's m1/m2 samples."""

    small_counts: dict[tuple[int, int], int]
    large_counts: dict[int, int]
    useful_calls: int
    padding_calls: int


def valid_intersections(n: int, s0: int, s: int) -> range:
    """All feasible values of |S intersect S0| for a size-s coalition."""

    lower = max(0, s0 + s - n)
    upper = min(s0, s)
    return range(lower, upper + 1)


def equation8_coefficient(n: int, s0: int, s: int, s1: int) -> float:
    """Coefficient of mu(s1/s; s,s0,n), including the hypergeometric mass."""

    probability = float(hypergeom.pmf(s1, n, s0, s))
    return probability * n / (s * (n - s)) * (s1 - s * s0 / n)


def make_budget_plan(
    *,
    n: int,
    s0: int,
    budget: int,
    threshold: int,
    rng: np.random.RandomState,
) -> FormulaSamplePlan:
    """Allocate nearly equal m1/m2 counts without exceeding a utility-call cap.

    One small-branch observation costs one utility call for every (s, s1)
    stratum.  One large-branch paired observation costs two calls.  Two calls are
    reserved for U([n]) and U(empty).  Complete cycles give every required term
    the same sample count; the randomized remainder prevents a fixed ordering bias.
    """

    if not (0 < s0 < n):
        raise ValueError("FGSV paper formula requires a nonempty proper group")
    if budget < 2:
        raise ValueError("FGSV needs at least two utility calls")

    components: list[tuple[str, int, int | None, int]] = []
    for s in range(1, n):
        if s < threshold:
            components.extend(("small", s, s1, 1) for s1 in valid_intersections(n, s0, s))
        else:
            components.append(("large", s, None, 2))

    cycle_cost = sum(component[3] for component in components)
    remaining = budget - 2
    complete_cycles = remaining // cycle_cost
    remaining -= complete_cycles * cycle_cost

    small_counts = {
        (s, int(s1)): complete_cycles
        for kind, s, s1, _ in components
        if kind == "small"
    }
    large_counts = {
        s: complete_cycles for kind, s, _, _ in components if kind == "large"
    }

    for index in rng.permutation(len(components)):
        kind, s, s1, cost = components[int(index)]
        if cost > remaining:
            continue
        if kind == "small":
            small_counts[(s, int(s1))] += 1
        else:
            large_counts[s] += 1
        remaining -= cost

    if any(count == 0 for count in (*small_counts.values(), *large_counts.values())):
        raise ValueError(
            "Budget is too small to sample every term required by Algorithm 1 at least once"
        )

    useful = budget - remaining
    return FormulaSamplePlan(
        small_counts=small_counts,
        large_counts=large_counts,
        useful_calls=useful,
        padding_calls=remaining,
    )


def sample_equation11_consistent_pair(
    *,
    n: int,
    group: np.ndarray,
    complement: np.ndarray,
    s: int,
    rng: np.random.RandomState,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Sample the paired difference required by Eq. (9) at k=floor(s*s0/n).

    Returns ``(upper, lower, k)`` where both coalitions have size ``s``, and
    their group intersection sizes are ``k+1`` and ``k``.
    """

    s0 = len(group)
    k = math.floor(s * s0 / n)
    inside_base_count = k
    outside_base_count = s - 1 - k
    if inside_base_count < 0 or outside_base_count < 0:
        raise ValueError("Invalid paired-sampling base size")

    inside_base = rng.choice(group, inside_base_count, replace=False)
    outside_base = rng.choice(complement, outside_base_count, replace=False)
    inside_available = np.setdiff1d(group, inside_base, assume_unique=False)
    outside_available = np.setdiff1d(complement, outside_base, assume_unique=False)
    if len(inside_available) == 0 or len(outside_available) == 0:
        raise ValueError(f"No valid paired sample for n={n}, s0={s0}, s={s}, k={k}")

    in_added = int(rng.choice(inside_available))
    out_added = int(rng.choice(outside_available))
    base = np.concatenate((inside_base, outside_base)).astype(int, copy=False)
    upper = np.concatenate((base, np.asarray([in_added], dtype=int)))
    lower = np.concatenate((base, np.asarray([out_added], dtype=int)))
    return upper, lower, k


def paper_formula_fgsv_budget_capped(
    utility: Utility,
    n: int,
    group: Sequence[int],
    budget: int,
    rng: np.random.RandomState,
    threshold: int = 10,
) -> dict[str, object]:
    """Estimate FGSV using Eq. (8), Eq. (9), and consistent paired sampling.

    Exact Shapley values are neither accepted nor used.  Inputs are only the utility
    oracle, player count, target group, call budget, random generator, and threshold.
    """

    group_array = np.asarray(sorted(set(int(index) for index in group)), dtype=int)
    if len(group_array) != len(group):
        raise ValueError("Group must contain unique player indices")
    if np.any(group_array < 0) or np.any(group_array >= n):
        raise ValueError("Group player index is out of range")
    complement = np.setdiff1d(np.arange(n, dtype=int), group_array)
    s0 = len(group_array)
    plan = make_budget_plan(
        n=n, s0=s0, budget=budget, threshold=threshold, rng=rng
    )

    starting_calls = utility.calls
    linear = s0 / n * (
        utility(np.arange(n, dtype=int)) - utility(np.array([], dtype=int))
    )
    terms = np.zeros(n - 1, dtype=float)
    sampled_sizes: Counter[int] = Counter()

    for s in range(1, min(threshold, n)):
        term = 0.0
        for s1 in valid_intersections(n, s0, s):
            count = plan.small_counts[(s, s1)]
            total = 0.0
            for _ in range(count):
                inside = rng.choice(group_array, s1, replace=False)
                outside = rng.choice(complement, s - s1, replace=False)
                coalition = np.concatenate((inside, outside))
                total += utility(coalition)
                sampled_sizes[s] += 1
            term += equation8_coefficient(n, s0, s, s1) * (total / count)
        terms[s - 1] = term

    alpha0 = s0 / n
    for s in range(max(1, threshold), n):
        count = plan.large_counts[s]
        difference_total = 0.0
        for _ in range(count):
            upper, lower, _ = sample_equation11_consistent_pair(
                n=n,
                group=group_array,
                complement=complement,
                s=s,
                rng=rng,
            )
            difference_total += utility(upper) - utility(lower)
            sampled_sizes[s] += 2
        delta_mu = difference_total / count
        terms[s - 1] = n / (n - 1) * alpha0 * (1 - alpha0) * delta_mu

    useful_calls = utility.calls - starting_calls
    if useful_calls != plan.useful_calls:
        raise AssertionError(
            f"Formula budget accounting mismatch: {useful_calls} != {plan.useful_calls}"
        )
    while utility.calls - starting_calls < budget:
        utility(np.array([], dtype=int))

    return {
        "estimate": float(linear + terms.sum()),
        "useful_calls": useful_calls,
        "padding_calls": budget - useful_calls,
        "small_sample_counts": {
            f"s={s},s1={s1}": count
            for (s, s1), count in sorted(plan.small_counts.items())
        },
        "large_pair_counts": {
            str(s): count for s, count in sorted(plan.large_counts.items())
        },
        "sampled_sizes": {str(s): count for s, count in sorted(sampled_sizes.items())},
        "terms": terms.tolist(),
        "paper_eq11_repair": "base_size_s_minus_1_to_target_fixed_size_s_delta_mu",
    }
