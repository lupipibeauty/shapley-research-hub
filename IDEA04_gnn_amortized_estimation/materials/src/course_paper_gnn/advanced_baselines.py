from __future__ import annotations

import argparse
import csv
import json
import random
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path

from .data import load_games, split_games
from .metrics import evaluate_game
from .schema import PlayerRecord
from .tpch import utility_from_mask


class CachedUtility:
    """Memoized coalition-value oracle with observable query counts."""

    def __init__(
        self,
        players: Sequence[PlayerRecord],
        value_type: str,
    ) -> None:
        self.players = players
        self.value_type = value_type
        self.cache: dict[int, float] = {}
        self.calls = 0

    def __call__(self, mask: int) -> float:
        value = self.cache.get(mask)
        if value is None:
            value = utility_from_mask(
                self.players,
                mask,
                self.value_type,
            )
            self.cache[mask] = value
            self.calls += 1
        return value


def _sample_paths(
    players: Sequence[PlayerRecord],
    oracle: Callable[[int], float],
    *,
    seed: int,
    nominal_steps: int,
) -> tuple[list[list[int]], list[list[float]], list[list[int]]]:
    """Sample permutation paths and materialize their full value trajectories."""

    if nominal_steps <= 0:
        raise ValueError("nominal_steps must be positive")
    player_count = len(players)
    permutation_count = max(1, nominal_steps // player_count)
    rng = random.Random(seed)
    paths: list[list[int]] = []
    values: list[list[float]] = []
    orders: list[list[int]] = []
    for _ in range(permutation_count):
        order = list(range(player_count))
        rng.shuffle(order)
        orders.append(order)
        mask = 0
        masks = [mask]
        path_values = [oracle(mask)]
        for player_index in order:
            mask |= 1 << player_index
            masks.append(mask)
            path_values.append(oracle(mask))
        paths.append(masks)
        values.append(path_values)
    return paths, values, orders


def _normalize_nonnegative(values: Sequence[float]) -> list[float]:
    clipped = [max(0.0, float(value)) for value in values]
    total = sum(clipped)
    if total <= 1e-15:
        return [1.0 / len(clipped)] * len(clipped)
    return [value / total for value in clipped]


def cached_permutation_shapley(
    players: Sequence[PlayerRecord],
    value_type: str,
    *,
    seed: int,
    nominal_steps: int,
) -> tuple[list[float], int, int]:
    """Permutation MC with repeated coalition states served from a cache."""

    oracle = CachedUtility(players, value_type)
    _, path_values, orders = _sample_paths(
        players,
        oracle,
        seed=seed,
        nominal_steps=nominal_steps,
    )
    totals = [0.0] * len(players)
    for path_index, order in enumerate(orders):
        for position, player_index in enumerate(order):
            totals[player_index] += (
                path_values[path_index][position + 1]
                - path_values[path_index][position]
            )
    nominal_evaluations = sum(len(values) for values in path_values)
    return (
        _normalize_nonnegative(totals),
        oracle.calls,
        nominal_evaluations,
    )


def _fit_additive_control_variate(
    masks: Sequence[int],
    values: Sequence[float],
    additive_player_values: Sequence[float],
) -> tuple[float, float]:
    """Fit V(S) ~= intercept + beta * sum_i(a_i * 1[i in S])."""

    proxy_values = [
        sum(
            float(additive_player_values[index])
            for index in range(len(additive_player_values))
            if mask & (1 << index)
        )
        for mask in masks
    ]
    mean_x = sum(proxy_values) / len(proxy_values)
    mean_y = sum(values) / len(values)
    covariance = sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(proxy_values, values)
    )
    variance = sum((x_value - mean_x) ** 2 for x_value in proxy_values)
    if variance <= 1e-15:
        return 0.0, mean_y
    beta = covariance / variance
    intercept = mean_y - beta * mean_x
    return beta, intercept


def regression_msr_shapley(
    players: Sequence[PlayerRecord],
    value_type: str,
    base_share: Sequence[float],
    *,
    seed: int,
    nominal_steps: int,
) -> tuple[list[float], int, int, dict[str, float]]:
    """Regression control-variate MSR with residual permutation sampling.

    The additive proxy and its fitted affine correction are solved analytically.
    Only the residual game is estimated from permutation marginal contributions.
    Coalition queries are cached, matching a shared-SQL-cache simulation budget.
    """

    if len(players) != len(base_share):
        raise ValueError("base_share must align with players")
    oracle = CachedUtility(players, value_type)
    paths, _, orders = _sample_paths(
        players,
        oracle,
        seed=seed,
        nominal_steps=nominal_steps,
    )
    flat_masks = list(oracle.cache)
    flat_values = [oracle.cache[mask] for mask in flat_masks]
    full_value = oracle((1 << len(players)) - 1)
    additive_player_values = [
        float(base_share[index]) * full_value
        for index in range(len(players))
    ]
    beta, intercept = _fit_additive_control_variate(
        flat_masks,
        flat_values,
        additive_player_values,
    )

    residual_cache = {
        mask: value
        - intercept
        - beta
        * sum(
            float(additive_player_values[index])
            for index in range(len(additive_player_values))
            if mask & (1 << index)
        )
        for mask, value in zip(flat_masks, flat_values)
    }
    residual_totals = [0.0] * len(players)
    for path_index, order in enumerate(orders):
        masks = paths[path_index]
        for position, player_index in enumerate(order):
            residual_totals[player_index] += (
                residual_cache[masks[position + 1]]
                - residual_cache[masks[position]]
            )

    estimate = [
        beta * float(additive_player_values[index]) + residual_totals[index]
        for index in range(len(players))
    ]
    prediction = _normalize_nonnegative(estimate)
    diagnostics = {
        "proxy_beta": float(beta),
        "proxy_intercept": float(intercept),
        "proxy_weight_sum": float(sum(base_share)),
        "clipping_mass": float(
            sum(max(0.0, -value) for value in estimate)
        ),
    }
    nominal_evaluations = sum(len(path) for path in paths)
    return prediction, oracle.calls, nominal_evaluations, diagnostics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run cache-aware permutation MC and regression control-variate MSR"
        )
    )
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--split", default="in_distribution")
    parser.add_argument("--budgets", default="64,256,1024")
    parser.add_argument("--seeds", default="20261107,20261108,20261109")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite output directory: {args.output}")
    games = split_games(load_games(args.data), args.split)
    if not games:
        raise RuntimeError(f"No games in split {args.split}")
    budgets = [int(item) for item in args.budgets.split(",") if item.strip()]
    seeds = [int(item) for item in args.seeds.split(",") if item.strip()]

    rows: list[dict] = []
    for seed in seeds:
        for game in games:
            owners = [player.owner_id for player in game.players]
            base_metric = evaluate_game(
                game.base_share,
                game.shapley_share,
                owners,
            )
            rows.append(
                {
                    "method": "additive_proxy",
                    "budget": 0,
                    "utility_calls": 0,
                    "nominal_evaluations": 0,
                    "cache_hit_rate": 0.0,
                    "proxy_beta": 1.0,
                    "proxy_intercept": 0.0,
                    "proxy_weight_sum": 1.0,
                    "clipping_mass": 0.0,
                    "seed": seed,
                    "game_id": game.game_id,
                    "split": game.split,
                    "condition": "/".join(game.condition.values()),
                    **asdict(base_metric),
                }
            )
            for budget in budgets:
                mc_prediction, mc_calls, mc_nominal = cached_permutation_shapley(
                    game.players,
                    game.condition["value_function"],
                    seed=seed,
                    nominal_steps=budget,
                )
                mc_metric = evaluate_game(
                    mc_prediction,
                    game.shapley_share,
                    owners,
                )
                rows.append(
                    {
                        "method": "cached_permutation_mc",
                        "budget": budget,
                        "utility_calls": mc_calls,
                        "nominal_evaluations": mc_nominal,
                        "cache_hit_rate": (
                            1.0 - mc_calls / mc_nominal if mc_nominal else 0.0
                        ),
                        "proxy_beta": "",
                        "proxy_intercept": "",
                        "proxy_weight_sum": "",
                        "clipping_mass": "",
                        "seed": seed,
                        "game_id": game.game_id,
                        "split": game.split,
                        "condition": "/".join(game.condition.values()),
                        **asdict(mc_metric),
                    }
                )
                (
                    prediction,
                    calls,
                    nominal_evaluations,
                    diagnostics,
                ) = regression_msr_shapley(
                    game.players,
                    game.condition["value_function"],
                    game.base_share,
                    seed=seed,
                    nominal_steps=budget,
                )
                metric = evaluate_game(
                    prediction,
                    game.shapley_share,
                    owners,
                )
                rows.append(
                    {
                        "method": "regression_msr",
                        "budget": budget,
                        "utility_calls": calls,
                        "nominal_evaluations": nominal_evaluations,
                        "cache_hit_rate": (
                            1.0 - calls / nominal_evaluations
                            if nominal_evaluations
                            else 0.0
                        ),
                        **diagnostics,
                        "seed": seed,
                        "game_id": game.game_id,
                        "split": game.split,
                        "condition": "/".join(game.condition.values()),
                        **asdict(metric),
                    }
                )

    args.output.mkdir(parents=True)
    with (args.output / "per_game_metrics.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {
        "data": str(args.data),
        "split": args.split,
        "budgets": budgets,
        "seeds": seeds,
        "games": len(games),
        "rows": len(rows),
        "regression_msr_definition": (
            "affine additive control variate fitted from sampled coalition values; "
            "residual estimated by permutation MC; same cached coalition budget"
        ),
    }
    (args.output / "run_config.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
