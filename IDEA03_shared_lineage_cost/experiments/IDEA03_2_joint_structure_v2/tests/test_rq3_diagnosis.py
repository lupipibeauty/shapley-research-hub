from __future__ import annotations

import sys
import unittest
from fractions import Fraction
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rq3_core import exact_shapley, generate_fixture, metric_arrays, paired_references, value_arrays
from rq3_diagnosis import (
    component_value,
    lineage_structure_row,
    official_lexashap_boolean,
    paired_full_references,
    poly_shapley,
    poly_value,
    value_components,
    value_from_report,
    value_polynomials,
)


class DiagnosisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        kwargs = dict(pair_id="TEST_N10", seed=9101, e_count=2, b_count=4, h_count=4, year=2025)
        cls.low = generate_fixture(structure="low", **kwargs)
        cls.high = generate_fixture(structure="high", **kwargs)
        cls.refs = paired_full_references(cls.low, cls.high)

    def test_lineage_is_enterprise_forest_with_primal_width_two(self):
        for fixture in (self.low, self.high):
            row = lineage_structure_row(fixture)
            self.assertTrue(row["incidence_is_forest"])
            self.assertEqual(row["incidence_treewidth_exact"], 1)
            self.assertEqual(row["primal_treewidth_exact"], 2)
            self.assertEqual(row["h3_terminal_states_closed_form"], 196)

    def test_sparse_polynomial_reconstructs_all_n10_values(self):
        for fixture in (self.low, self.high):
            values, _ = value_polynomials(fixture, self.refs, Fraction(1000), Fraction(1, 2))
            components = value_components(fixture, self.refs, Fraction(1000), Fraction(1, 2))
            for value_name, poly in values.items():
                for mask in range(1 << fixture.n):
                    expected = value_from_report(fixture, mask, value_name, self.refs, Fraction(1000), Fraction(1, 2))
                    self.assertEqual(poly_value(poly, mask), expected)
                    self.assertEqual(component_value(components[value_name], mask), expected)

    def test_sparse_shapley_matches_full_oracle(self):
        arrays_low, _ = metric_arrays(self.low)
        arrays_high, _ = metric_arrays(self.high)
        float_refs = paired_references(arrays_low, arrays_high)
        for fixture, arrays in ((self.low, arrays_low), (self.high, arrays_high)):
            exact_values = value_arrays(arrays, float_refs, 1000.0, 0.5)
            polys, _ = value_polynomials(fixture, self.refs, Fraction(1000), Fraction(1, 2))
            for value_name, poly in polys.items():
                sparse = np.asarray([float(value) for value in poly_shapley(poly, fixture.n)])
                oracle = exact_shapley(exact_values[value_name], fixture.n)
                self.assertLess(float(np.max(np.abs(sparse - oracle))), 1e-9)

    def test_official_lexashap_boolean_component(self):
        dnf = (frozenset({0, 1}), frozenset({0, 2}))
        official = official_lexashap_boolean(dnf)
        expected = {0: Fraction(2, 3), 1: Fraction(1, 6), 2: Fraction(1, 6)}
        for player, value in expected.items():
            self.assertAlmostEqual(official[player], float(value), places=12)


if __name__ == "__main__":
    unittest.main()
