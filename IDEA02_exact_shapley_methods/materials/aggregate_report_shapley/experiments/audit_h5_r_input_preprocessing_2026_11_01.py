from __future__ import annotations

import csv
import statistics
import sys
import time
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aggregate_report_shapley.d1p import load_d1p_spec, state_for_mask  # noqa: E402
from aggregate_report_shapley.d1p_values import D1PValueSuite  # noqa: E402
from aggregate_report_shapley.h5_scale import (  # noqa: E402
    ScaleConfig,
    generate_instance,
    make_value_function,
    record_delta,
)


CONFIG = ROOT / "config" / "d1p_design.yaml"
VALUE_CONFIG = ROOT / "config" / "value_spec_v3_2.yaml"
OUT = ROOT / "outputs" / "v4_0" / "H5_R_2026_11_01"


def compile_d1p() -> tuple[int, int]:
    spec = load_d1p_spec(CONFIG)
    suite = D1PValueSuite(spec, state_for_mask(spec.full_mask, spec), VALUE_CONFIG)
    deltas = []
    leaves = ("A1", "A2", "B1", "B2")
    for item in spec.records:
        delta = [0] * 16
        offset = leaves.index(item.leaf_node_id) * 4
        delta[offset : offset + 4] = [
            1,
            int(item.category_a_id == spec.category_a_target),
            int(item.attribute_present),
            int(item.attribute_present and item.category_b_id == spec.category_b_target),
        ]
        deltas.append(tuple(delta))
    # Force construction of both frozen value evaluators without reading any payment.
    _ = suite.v1(state_for_mask(0, spec))
    _ = suite.v2_decimal(state_for_mask(0, spec), Fraction(1, 2), precision=110)
    return len(spec.records), len(set(deltas))


def compile_scale(n: int) -> tuple[int, int]:
    config = ScaleConfig(
        config_id=f"G1_N{n}_L4_D4_ORIGINAL_FAMILIES",
        group="H5_R_SCALE_CONTROL",
        n=n,
        leaves=4,
        dimensions=4,
        profile="balanced_templates",
        family_map=(0, 1, 2, 3),
        score_modes=("v2",),
        exact_payments_expected=True,
    )
    instance = generate_instance(config, 7301)
    deltas = tuple(record_delta(record, 4, 4) for record in instance.records)
    _ = make_value_function(instance, "v2")
    return len(instance.records), len(set(deltas))


def main() -> None:
    raw: list[dict[str, object]] = []
    targets = (
        ("D1P_V1_V2_SHARED_INPUT", compile_d1p),
        ("SCALE_N12_V2", lambda: compile_scale(12)),
        ("SCALE_N16_V2", lambda: compile_scale(16)),
    )
    for target, call in targets:
        for repeat in range(3):
            started = time.perf_counter()
            players, types = call()
            elapsed = time.perf_counter() - started
            raw.append(
                {
                    "input_target": target,
                    "repeat": repeat,
                    "compile_seconds": elapsed,
                    "player_count": players,
                    "unique_delta_types": types,
                    "scope": "load/generate frozen input, compile deltas and value evaluator; excludes Shapley solve",
                }
            )
    summary: list[dict[str, object]] = []
    for target, _call in targets:
        subset = [float(row["compile_seconds"]) for row in raw if row["input_target"] == target]
        summary.append(
            {
                "input_target": target,
                "repeats": len(subset),
                "compile_seconds_median": statistics.median(subset),
                "compile_seconds_min": min(subset),
                "compile_seconds_max": max(subset),
                "timing_scope": "same frozen input repeated timing; descriptive only",
            }
        )
    for name, data in (("input_preprocessing_raw.csv", raw), ("input_preprocessing_summary.csv", summary)):
        with (OUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)


if __name__ == "__main__":
    main()
