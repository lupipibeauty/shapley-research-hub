from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class GameMetrics:
    share_l1: float
    owner_l1: float
    mae_share: float
    p95_abs_share: float
    max_abs_share: float
    high_value_mae: float
    spearman: float
    top3_overlap: float
    ndcg3: float
    zero_pay: float
    efficiency_error: float


def _rankdata(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(indexed):
        end = position + 1
        while end < len(indexed) and math.isclose(
            indexed[end][1], indexed[position][1], rel_tol=0.0, abs_tol=1e-15
        ):
            end += 1
        average_rank = (position + 1 + end) / 2.0
        for offset in range(position, end):
            ranks[indexed[offset][0]] = average_rank
        position = end
    return ranks


def spearman(predicted: Sequence[float], target: Sequence[float]) -> float:
    if len(predicted) != len(target) or len(predicted) < 2:
        return float("nan")
    ranks_pred = _rankdata(predicted)
    ranks_true = _rankdata(target)
    mean_pred = sum(ranks_pred) / len(ranks_pred)
    mean_true = sum(ranks_true) / len(ranks_true)
    numerator = sum(
        (left - mean_pred) * (right - mean_true)
        for left, right in zip(ranks_pred, ranks_true)
    )
    left_norm = math.sqrt(sum((item - mean_pred) ** 2 for item in ranks_pred))
    right_norm = math.sqrt(sum((item - mean_true) ** 2 for item in ranks_true))
    denominator = left_norm * right_norm
    return 0.0 if denominator <= 1e-15 else numerator / denominator


def owner_shares(
    shares: Sequence[float],
    owners: Sequence[str],
) -> dict[str, float]:
    if len(shares) != len(owners):
        raise ValueError("shares and owners must have the same length")
    result: dict[str, float] = defaultdict(float)
    for share, owner in zip(shares, owners):
        result[owner] += float(share)
    return dict(result)


def ndcg_at_k(
    predicted: Sequence[float],
    target: Sequence[float],
    k: int,
) -> float:
    if len(predicted) != len(target) or len(predicted) == 0:
        raise ValueError("Predicted and target shares must be non-empty and aligned")
    k = min(k, len(predicted))
    predicted_order = sorted(
        range(len(predicted)),
        key=lambda index: predicted[index],
        reverse=True,
    )[:k]
    target_order = sorted(
        range(len(target)),
        key=lambda index: target[index],
        reverse=True,
    )[:k]

    def dcg(order: Sequence[int]) -> float:
        return sum(
            float(target[index]) / math.log2(rank + 2)
            for rank, index in enumerate(order)
        )

    ideal = dcg(target_order)
    return 0.0 if ideal <= 1e-15 else dcg(predicted_order) / ideal


def evaluate_game(
    predicted_share: Sequence[float],
    target_share: Sequence[float],
    owners: Sequence[str],
    *,
    top_k: int = 3,
) -> GameMetrics:
    if len(predicted_share) != len(target_share):
        raise ValueError("Predicted and target shares must have the same length")
    if len(predicted_share) != len(owners):
        raise ValueError("Owner list must match the player count")
    if len(predicted_share) == 0:
        raise ValueError("At least one player is required")
    absolute_errors = sorted(
        abs(float(pred) - float(target))
        for pred, target in zip(predicted_share, target_share)
    )
    share_l1 = 0.5 * sum(absolute_errors)
    mae_share = sum(absolute_errors) / len(absolute_errors)
    p95_index = min(
        len(absolute_errors) - 1,
        int(round(0.95 * (len(absolute_errors) - 1))),
    )
    high_value_count = max(1, math.ceil(0.25 * len(target_share)))
    high_value_indices = sorted(
        range(len(target_share)),
        key=lambda index: target_share[index],
        reverse=True,
    )[:high_value_count]
    high_value_mae = sum(
        abs(float(predicted_share[index]) - float(target_share[index]))
        for index in high_value_indices
    ) / high_value_count
    predicted_owner = owner_shares(predicted_share, owners)
    target_owner = owner_shares(target_share, owners)
    owner_keys = sorted(set(predicted_owner) | set(target_owner))
    owner_l1 = 0.5 * sum(
        abs(predicted_owner.get(key, 0.0) - target_owner.get(key, 0.0))
        for key in owner_keys
    )
    k = min(top_k, len(predicted_share))
    pred_top = set(sorted(range(len(predicted_share)), key=lambda i: predicted_share[i], reverse=True)[:k])
    true_top = set(sorted(range(len(target_share)), key=lambda i: target_share[i], reverse=True)[:k])
    top_overlap = len(pred_top & true_top) / k if k else float("nan")
    zero_pay = sum(
        float(pred) for pred, target in zip(predicted_share, target_share) if target <= 1e-12
    )
    efficiency_error = abs(sum(float(item) for item in predicted_share) - 1.0)
    return GameMetrics(
        share_l1=float(share_l1),
        owner_l1=float(owner_l1),
        mae_share=float(mae_share),
        p95_abs_share=float(absolute_errors[p95_index]),
        max_abs_share=float(absolute_errors[-1]),
        high_value_mae=float(high_value_mae),
        spearman=float(spearman(predicted_share, target_share)),
        top3_overlap=float(top_overlap),
        ndcg3=float(ndcg_at_k(predicted_share, target_share, top_k)),
        zero_pay=float(zero_pay),
        efficiency_error=float(efficiency_error),
    )


def mean_metrics(rows: Iterable[GameMetrics]) -> dict[str, float]:
    collected = list(rows)
    if not collected:
        raise ValueError("No metric rows supplied")
    fields = (
        "share_l1",
        "owner_l1",
        "mae_share",
        "p95_abs_share",
        "max_abs_share",
        "high_value_mae",
        "spearman",
        "top3_overlap",
        "ndcg3",
        "zero_pay",
        "efficiency_error",
    )
    return {
        field: sum(getattr(row, field) for row in collected) / len(collected)
        for field in fields
    }


def bootstrap_mean_ci(
    values: Sequence[float],
    *,
    seed: int = 20261110,
    samples: int = 10_000,
    confidence: float = 0.95,
) -> tuple[float, float]:
    if not values:
        raise ValueError("At least one value is required")
    if samples <= 0:
        raise ValueError("samples must be positive")
    try:
        import numpy as np

        array = np.asarray(values, dtype=float)
        rng = np.random.default_rng(seed)
        indices = rng.integers(0, len(array), size=(samples, len(array)))
        means = array[indices].mean(axis=1)
        mean_values = np.sort(means).tolist()
    except ImportError:
        import random

        rng = random.Random(seed)
        mean_values = []
        for _ in range(samples):
            draw = [values[rng.randrange(len(values))] for _ in values]
            mean_values.append(sum(draw) / len(draw))
        mean_values.sort()
    alpha = 1.0 - confidence
    lower_index = max(0, int(math.floor(alpha / 2 * (samples - 1))))
    upper_index = min(samples - 1, int(math.ceil((1.0 - alpha / 2) * (samples - 1))))
    return mean_values[lower_index], mean_values[upper_index]


def paired_bootstrap_interval(
    differences: Sequence[float],
    *,
    seed: int = 20261110,
    samples: int = 10_000,
    confidence: float = 0.95,
) -> tuple[float, float]:
    return bootstrap_mean_ci(
        differences,
        seed=seed,
        samples=samples,
        confidence=confidence,
    )
