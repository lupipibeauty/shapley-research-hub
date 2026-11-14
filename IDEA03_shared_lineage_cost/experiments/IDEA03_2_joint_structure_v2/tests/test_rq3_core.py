from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rq3_core import (  # noqa: E402
    compare_pair,
    generate_fixture,
    metric_arrays,
    metric_arrays_witness_states,
    paired_references,
    report_python,
    validate_sql_sample,
    value_arrays,
)


class RQ3CoreTests(unittest.TestCase):
    def make_pair(self, n: int, e: int, b: int, seed: int):
        kwargs = dict(pair_id=f"T_N{n}", seed=seed, e_count=e, b_count=b, h_count=b, year=2025)
        return (
            generate_fixture(structure="low", **kwargs),
            generate_fixture(structure="high", **kwargs),
        )

    def test_minimal_n20_controls_and_province_change(self):
        low, high = self.make_pair(20, 4, 8, 9201)
        check = compare_pair(low, high)
        self.assertTrue(check["province_enterprise_changed"])
        self.assertEqual(check["PA_enterprise_low"], 2)
        self.assertEqual(check["PB_enterprise_low"], 2)
        self.assertEqual(check["PA_enterprise_high"], 4)
        self.assertEqual(check["PB_enterprise_high"], 4)

    def test_n16_high_is_not_degenerate(self):
        low, high = self.make_pair(16, 4, 6, 9161)
        check = compare_pair(low, high)
        self.assertTrue(check["province_enterprise_changed"])
        self.assertGreater(len(high.rewiring), 0)

    def test_empty_skeleton_and_null_share(self):
        low, _high = self.make_pair(10, 2, 4, 9101)
        report = report_python(low, 0)
        self.assertEqual(len(report), 35)
        self.assertIsNone(report[("NAT", "mfg_share")])
        self.assertEqual(report[("A1", "workers")], 0)

    def test_lambda_zero_strictly_equals_additive(self):
        low, high = self.make_pair(10, 2, 4, 9101)
        low_arrays, _ = metric_arrays(low)
        high_arrays, _ = metric_arrays(high)
        refs = paired_references(low_arrays, high_arrays)
        for arrays in (low_arrays, high_arrays):
            values = value_arrays(arrays, refs, 1000.0, 0.0)
            self.assertTrue(np.array_equal(values["local_add"], values["local_joint"]))
            self.assertTrue(np.array_equal(values["cross_add"], values["cross_joint"]))

    def test_sampled_sql_binds_only_remaining_parameters(self):
        low, _high = self.make_pair(10, 2, 4, 9101)
        row, samples = validate_sql_sample(low, ROOT / "sql" / "report_v1.sql", [0, 1, (1 << 10) - 1])
        self.assertEqual(row["status"], "VERIFIED")
        self.assertEqual(row["coalitions"], 3)
        self.assertEqual(len(samples), 3 * 7)

    def test_witness_state_compression_covers_exact_report_states(self):
        low, _high = self.make_pair(10, 2, 4, 9101)
        coalition_arrays, _ = metric_arrays(low)
        witness_arrays, phase = metric_arrays_witness_states(low)
        coalition_states = set(zip(*(array.tolist() for array in coalition_arrays.values()), strict=True))
        witness_states = set(zip(*(array.tolist() for array in witness_arrays.values()), strict=True))
        self.assertEqual(coalition_states, witness_states)
        self.assertEqual(phase["player_coalitions_enumerated"], 0)
        self.assertEqual(phase["report_states_enumerated"], 16)


if __name__ == "__main__":
    unittest.main()
