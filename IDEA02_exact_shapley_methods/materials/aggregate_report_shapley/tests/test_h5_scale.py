from __future__ import annotations

import unittest

from aggregate_report_shapley.h5_scale import (
    ScaleConfig,
    b0_full_enumeration,
    b2_state_dp,
    b3_leaf_factor,
    b4_type_variable_elimination,
    b5_shared_linear_closed_form,
    exact_efficiency_error,
    generate_instance,
    make_value_function,
    max_abs_error,
    record_delta,
    structural_state_count,
)


class H5ScaleTests(unittest.TestCase):
    def config(self, **changes) -> ScaleConfig:
        values = dict(
            config_id="TEST",
            group="TEST",
            n=8,
            leaves=2,
            dimensions=4,
            profile="balanced_templates",
            family_map=(0, 1, 2, 3),
            score_modes=("v2",),
            exact_payments_expected=True,
        )
        values.update(changes)
        return ScaleConfig(**values)

    def test_generator_is_seed_deterministic(self) -> None:
        left = generate_instance(self.config(), 7301)
        right = generate_instance(self.config(), 7301)
        self.assertEqual(left.records, right.records)
        self.assertEqual(left.full_state, right.full_state)

    def test_all_four_exact_methods_match_small_truth(self) -> None:
        instance = generate_instance(self.config(), 7301)
        truth, _ = b0_full_enumeration(instance, "v2")
        for solver in (b2_state_dp, b3_leaf_factor, b4_type_variable_elimination):
            estimate, _ = solver(instance, "v2", state_cap=10_000)
            self.assertLessEqual(max_abs_error(estimate, truth), 1e-10)
            self.assertLessEqual(exact_efficiency_error(instance, "v2", estimate), 1e-10)

    def test_reachable_states_never_exceed_coalitions(self) -> None:
        instance = generate_instance(self.config(n=12, leaves=4), 7303)
        diagnostics = structural_state_count(instance, enumeration_cap=100_000)
        self.assertEqual(diagnostics["state_count_status"], "EXACT")
        self.assertLessEqual(diagnostics["actual_reachable_states"], 2**instance.n)

    def test_extra_attributes_have_real_value_effect(self) -> None:
        config = self.config(dimensions=6, family_map=tuple(range(6)), profile="diverse_effective")
        instance = generate_instance(config, 7301)
        value = make_value_function(instance, "additive")
        candidates = [index for index, record in enumerate(instance.records) if record.increments[5] == 1]
        self.assertTrue(candidates)
        self.assertGreater(
            value(record_delta(instance.records[candidates[0]], instance.config.leaves, instance.config.dimensions)),
            0.0,
        )

    def test_shared_additive_and_geometric_collapse_to_same_game(self) -> None:
        instance = generate_instance(self.config(family_map=(0, 0, 0, 0)), 7301)
        additive = make_value_function(instance, "additive")
        geometric = make_value_function(instance, "geometric")
        for mask in range(1 << instance.n):
            state = tuple(
                sum(
                    record_delta(instance.records[index], instance.config.leaves, instance.config.dimensions)[position]
                    for index in range(instance.n)
                    if mask & (1 << index)
                )
                for position in range(instance.config.leaves * instance.config.dimensions)
            )
            self.assertAlmostEqual(additive(state), geometric(state), places=12)

    def test_large_shared_closed_form_matches_symmetry(self) -> None:
        instance = generate_instance(
            self.config(n=100, leaves=4, family_map=(0, 0, 0, 0)),
            7301,
        )
        allocation, _ = b5_shared_linear_closed_form(instance, "geometric")
        self.assertLessEqual(max_abs_error(allocation, [1.0 / instance.n] * instance.n), 1e-12)
        self.assertLessEqual(exact_efficiency_error(instance, "geometric", allocation), 1e-12)


if __name__ == "__main__":
    unittest.main()
