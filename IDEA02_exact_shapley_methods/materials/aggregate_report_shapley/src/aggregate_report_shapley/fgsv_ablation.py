"""Sequential ablations of the released FGSV estimator for R2-4.

The release source is never imported or modified.  A0 copies its mathematical
operations, with the sole engineering change that a requested call budget is
not exceeded.  A1--A3 each change exactly one previously audited choice.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

import numpy as np

from .fgsv_paper_formula import sample_equation11_consistent_pair, valid_intersections


STAGES = (
    "A0_RELEASE_LOGIC_CAPPED",
    "A1_ADD_NORMALIZATION",
    "A2_FLOOR_INDEX",
    "A3_FIXED_SIZE_FORWARD_DIFFERENCE",
)


def _hypergeom_probability(n: int, s0: int, s: int, s1: int) -> float:
    return math.comb(s0, s1) * math.comb(n - s0, s - s1) / math.comb(n, s)


def _official_pair(
    *, n: int, group: np.ndarray, complement: np.ndarray, s: int,
    expected: int, rng: np.random.RandomState,
) -> tuple[np.ndarray, np.ndarray, bool]:
    low = max(0, len(group) + s - n)
    high = min(len(group), s)
    if expected + 1 <= high and expected - 1 >= low:
        inside = rng.choice(group, expected + 1, replace=False)
        outside = rng.choice(complement, s - expected + 1, replace=False)
        return (np.concatenate((inside, outside[: s - expected - 1])),
                np.concatenate((inside[: expected - 1], outside)), True)
    if expected + 1 <= high:
        inside = rng.choice(group, expected + 1, replace=False)
        outside = rng.choice(complement, s - expected, replace=False)
        return (np.concatenate((inside, outside[: s - expected - 1])),
                np.concatenate((inside[:expected], outside)), False)
    if expected - 1 >= low:
        inside = rng.choice(group, expected, replace=False)
        outside = rng.choice(complement, s - expected + 1, replace=False)
        return (np.concatenate((inside, outside[: s - expected])),
                np.concatenate((inside[: expected - 1], outside)), False)
    raise ValueError(f"No released-code pair for n={n}, s0={len(group)}, s={s}")


def fgsv_sequential_ablation(
    utility, n: int, group: Sequence[int], budget: int,
    rng: np.random.RandomState, threshold: int = 10,
    stage: str = STAGES[0],
) -> dict[str, object]:
    """Run A0--A3 under a strict utility-call cap.

    This retains the release's random-size scheduling.  Consequently A1--A3
    are an ordered ablation path, not factorial main effects.
    """
    if stage not in STAGES:
        raise ValueError(stage)
    level = STAGES.index(stage)
    group = np.asarray(sorted(set(int(x) for x in group)), dtype=int)
    complement = np.setdiff1d(np.arange(n, dtype=int), group)
    s0 = len(group)
    if not 0 < s0 < n or budget < 2:
        raise ValueError("FGSV requires a nonempty proper group and budget >= 2")
    started = utility.calls
    linear = s0 / n * (utility(np.arange(n, dtype=int)) - utility(np.array([], dtype=int)))
    terms = np.zeros(n - 1)
    counts = np.zeros(n - 1, dtype=int)
    sampled = Counter()
    while utility.calls - started < budget:
        remaining = budget - (utility.calls - started)
        candidates = []
        for s in range(1, n):
            cost = len(valid_intersections(n, s0, s)) if s < threshold else 2
            if cost <= remaining:
                candidates.append(s)
        if not candidates:
            break
        s = int(candidates[int(rng.randint(len(candidates)))])
        if s < threshold:
            observed = 0.0
            for s1 in valid_intersections(n, s0, s):
                inside = rng.choice(group, s1, replace=False)
                outside = rng.choice(complement, s - s1, replace=False)
                value = utility(np.concatenate((inside, outside)))
                coefficient = _hypergeom_probability(n, s0, s, s1) * (s1 - s * s0 / n)
                if level >= 1:
                    coefficient *= n / (s * (n - s))
                observed += coefficient * value
                sampled[s] += 1
        else:
            expected = math.floor(s0 * s / n) if level >= 2 else round(s0 * s / n)
            if level >= 3:
                upper, lower, _ = sample_equation11_consistent_pair(
                    n=n, group=group, complement=complement, s=s, rng=rng)
                divisor = 1.0
            else:
                upper, lower, central = _official_pair(
                    n=n, group=group, complement=complement, s=s,
                    expected=expected, rng=rng)
                divisor = 2.0 if central else 1.0
            observed = s0 / n * (1 - s0 / n) * (utility(upper) - utility(lower)) / divisor
            if level >= 1:
                observed *= n / (n - 1)
            sampled[s] += 2
        index = s - 1
        counts[index] += 1
        terms[index] += (observed - terms[index]) / counts[index]
    useful = utility.calls - started
    while utility.calls - started < budget:
        utility(np.array([], dtype=int))
    return {
        "estimate": float(linear + terms.sum()), "useful_calls": useful,
        "padding_calls": budget - useful, "terms": terms.tolist(),
        "size_update_counts": counts.tolist(),
        "sampled_sizes": {str(k): v for k, v in sorted(sampled.items())},
        "stage": stage,
    }
