from __future__ import annotations

from pathlib import Path

import yaml

from aggregate_report_shapley.d1 import D1_CELLS, D1_MEMBERSHIP, D1_RECORDS
from aggregate_report_shapley.report_state import all_coalition_states


ROOT = Path(__file__).resolve().parents[1]


def test_d1_fixed_properties() -> None:
    assert len(D1_RECORDS) == 12
    assert len(D1_CELLS) == 13
    assert all(len(membership) == 5 for membership in D1_MEMBERSHIP)
    assert len({record.record_id for record in D1_RECORDS}) == 12
    assert sum(record.amount for record in D1_RECORDS if record.category_id == "X") == 90
    assert sum(record.amount for record in D1_RECORDS if record.category_id == "Y") == 90


def test_yaml_matches_code_fixture() -> None:
    config = yaml.safe_load((ROOT / "config" / "d1_exact.yaml").read_text(encoding="utf-8"))
    configured = [
        (
            row["record_id"],
            row["region_id"],
            row["city_id"],
            row["category_id"],
            row["amount"],
        )
        for row in config["records"]
    ]
    actual = [
        (
            record.record_id,
            record.region_id,
            record.city_id,
            record.category_id,
            record.amount,
        )
        for record in D1_RECORDS
    ]
    assert configured == actual


def test_all_coalitions_have_fixed_coordinates() -> None:
    states = all_coalition_states(D1_RECORDS, D1_MEMBERSHIP, D1_CELLS)
    assert len(states) == 4096
    assert all(tuple(state.counts) == D1_CELLS for state in states)
    assert all(value == 0 for value in states[0].counts.values())
    assert states[-1].counts["all:ALL"] == 12
    assert states[-1].sums["all:ALL"] == 180

