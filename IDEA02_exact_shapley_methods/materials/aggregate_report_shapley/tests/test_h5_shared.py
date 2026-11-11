from __future__ import annotations

import math
import unittest

from aggregate_report_shapley.h5_scale import ScaleConfig, generate_instance, make_value_function, record_delta
from aggregate_report_shapley.h5_shared import (
    S3SharedForward,
    S4PrefixSuffix,
    S5TypeMultiOutput,
    S6ReverseMultilinearAD,
    StateGame,
    efficiency_error,
    exact_b0,
    gauss_legendre_unit_interval,
    max_abs_error,
    s0_per_focus_b2,
    s1_per_focus_b3,
    s2_per_focus_b4,
)


def scale_game(n: int = 8) -> StateGame:
    config = ScaleConfig(
        config_id="TEST_SHARED",
        group="TEST",
        n=n,
        leaves=2,
        dimensions=4,
        profile="balanced_templates",
        family_map=(0, 1, 2, 3),
        score_modes=("v2",),
        exact_payments_expected=True,
    )
    instance = generate_instance(config, 7301)
    return StateGame(
        game_id="TEST_SHARED",
        player_ids=tuple(f"p{i + 1}" for i in range(n)),
        deltas=tuple(record_delta(record, config.leaves, config.dimensions) for record in instance.records),
        value=make_value_function(instance, "v2"),
        player_leaves=tuple(record.leaf for record in instance.records),
        leaf_count=config.leaves,
        leaf_width=config.dimensions,
    )


class H5SharedTests(unittest.TestCase):
    def test_quadrature_integrates_degree_fifteen(self) -> None:
        nodes, weights = gauss_legendre_unit_interval(8)
        estimate = sum(weight * node**15 for node, weight in zip(nodes, weights, strict=True))
        self.assertAlmostEqual(estimate, 1.0 / 16.0, places=13)

    def test_all_shared_methods_match_full_coalition_truth(self) -> None:
        game = scale_game()
        truth, _ = exact_b0(game)
        for function in (s0_per_focus_b2, s1_per_focus_b3, s2_per_focus_b4):
            result, _ = function(game, range(game.n), state_cap=20_000)
            allocation = [result[player] for player in range(game.n)]
            self.assertLessEqual(max_abs_error(allocation, truth), 1e-10)
        for constructor in (S3SharedForward, S4PrefixSuffix, S5TypeMultiOutput, S6ReverseMultilinearAD):
            solver = constructor(game, state_cap=20_000)
            allocation = solver.solve_all()
            self.assertLessEqual(max_abs_error(allocation, truth), 1e-10)
            self.assertLessEqual(efficiency_error(game, allocation), 1e-10)

    def test_nonlinear_terminal_value_does_not_need_derivative(self) -> None:
        deltas = ((1, 0), (1, 1), (1, 0), (1, 1))

        def nonlinear(state: tuple[int, ...]) -> float:
            return math.sqrt(state[0] * state[1]) if state[0] and state[1] else 0.0

        game = StateGame(
            game_id="NONDIFFERENTIABLE_AT_ZERO",
            player_ids=("p1", "p2", "p3", "p4"),
            deltas=deltas,
            value=nonlinear,
            player_leaves=(0, 0, 0, 0),
            leaf_count=1,
            leaf_width=2,
        )
        truth, _ = exact_b0(game)
        reverse = S6ReverseMultilinearAD(game, state_cap=100).solve_all()
        self.assertLessEqual(max_abs_error(reverse, truth), 1e-12)

    def test_type_cache_reuses_identical_players_without_double_counting(self) -> None:
        game = scale_game()
        solver = S5TypeMultiOutput(game, state_cap=20_000)
        allocation = solver.solve_all()
        diagnostics = solver.diagnostics()
        self.assertAlmostEqual(sum(allocation), sum(exact_b0(game)[0]), places=12)
        self.assertGreaterEqual(int(diagnostics["result_cache_hits"]), 1)


if __name__ == "__main__":
    unittest.main()
