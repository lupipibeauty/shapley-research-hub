from __future__ import annotations

import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from aggregate_report_shapley.h5_scale import generate_instance  # noqa: E402
from run_h5_scale_2026_11_01 import OUT, SEEDS, configs  # noqa: E402


def main() -> None:
    rows = []
    for config in configs():
        for seed in SEEDS:
            instance = generate_instance(config, seed)
            for dimension in range(config.dimensions):
                expected_effective = (
                    config.group.startswith("G1_")
                    or config.group.startswith("G2_")
                    or dimension in set(config.family_map)
                )
                full_total = sum(
                    instance.full_state[leaf * config.dimensions + dimension]
                    for leaf in range(config.leaves)
                )
                affected_players = sum(record.increments[dimension] != 0 for record in instance.records)
                rows.append(
                    {
                        "config_id": config.config_id,
                        "seed": seed,
                        "dimension": dimension,
                        "full_total": full_total,
                        "affected_player_count": affected_players,
                        "used_by_score_family": dimension in set(config.family_map),
                        "expected_effective_in_this_control": expected_effective,
                        "effective_dimension_gate": (not expected_effective)
                        or (full_total > 0 and affected_players > 0 and dimension in set(config.family_map)),
                    }
                )
    path = OUT / "generator_effectiveness_audit.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if not all(row["effective_dimension_gate"] for row in rows):
        raise AssertionError("存在无实际统计作用的维度")
    print(f"PASS: {len(rows)} dimension-instance rows")


if __name__ == "__main__":
    main()
