from __future__ import annotations

from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import duckdb

from aggregate_report_shapley.d1p import all_incremental_states, load_d1p_spec
from aggregate_report_shapley.d1p_sql import (
    create_d1p_database,
    query_all_sql_p,
    query_all_sql_u,
)
from aggregate_report_shapley.d1p_values import D1PValueSuite, count_closed_form
from aggregate_report_shapley.exact_shapley import (
    exact_shapley_decimal,
    exact_shapley_subset,
    shapley_via_mobius_decimal,
    shapley_via_mobius_fraction,
)


ROOT = Path(__file__).resolve().parents[1]


def _setup():
    spec = load_d1p_spec(ROOT / "config" / "d1p_design.yaml")
    states = all_incremental_states(spec)
    suite = D1PValueSuite(spec, states[-1], ROOT / "config" / "value_spec_v3_2.yaml")
    return spec, states, suite


def test_d1p_frozen_full_and_mask7_assertions() -> None:
    spec, states, _ = _setup()
    assert states[-1].counts == {
        "COUNTRY": [12, 6, 10, 6],
        "A": [4, 2, 3, 2],
        "B": [8, 4, 7, 4],
        "A1": [2, 1, 2, 1],
        "A2": [2, 1, 1, 1],
        "B1": [4, 2, 3, 2],
        "B2": [4, 2, 4, 2],
    }
    assert states[7].counts["COUNTRY"] == [3, 1, 3, 2]
    assert states[7].counts["A"] == [3, 1, 3, 2]
    assert states[7].counts["A1"] == [2, 1, 2, 1]
    assert states[7].counts["A2"] == [1, 0, 1, 1]
    assert states[7].counts["B"] == [0, 0, 0, 0]
    assert tuple(record.record_id for record in spec.records) == tuple(
        f"p{i}" for i in range(1, 13)
    )


def test_sql_p_sql_u_and_incremental_match_all_coalitions() -> None:
    spec, incremental, _ = _setup()
    connection = duckdb.connect(":memory:")
    create_d1p_database(connection, spec)
    sql_p = query_all_sql_p(connection, spec)
    sql_u = query_all_sql_u(connection, spec)
    for mask in range(1 << spec.player_count):
        expected = incremental[mask].canonical(spec.nodes)
        assert sql_p[mask].canonical(spec.nodes) == expected
        assert sql_u[mask].canonical(spec.nodes) == expected


def test_value_endpoints_and_monotonicity_all_edges() -> None:
    spec, states, suite = _setup()
    values = suite.all_values(states)
    for name, table in values.items():
        assert table[0] == 0, name
        assert table[-1] == 1000, name
        for mask, value in enumerate(table):
            for player in range(spec.player_count):
                bit = 1 << player
                if not mask & bit:
                    assert table[mask | bit] >= value, (name, mask, player)
    assert values["V2_lambda_0"] == values["V1"]


def test_exact_shapley_independent_oracles_and_closed_forms() -> None:
    spec, states, suite = _setup()
    values = suite.all_values(states)
    for name in ("V0", "V_count", "V1", "V2_lambda_0"):
        table = values[name]
        subset = exact_shapley_subset(table, spec.player_count)  # type: ignore[arg-type]
        mobius = shapley_via_mobius_fraction(table, spec.player_count)  # type: ignore[arg-type]
        assert subset == mobius, name
        assert sum(subset, Fraction()) == 1000, name
    assert exact_shapley_subset(values["V0"], spec.player_count) == [  # type: ignore[arg-type]
        Fraction(250, 3)
    ] * 12
    count_shapley = exact_shapley_subset(values["V_count"], spec.player_count)  # type: ignore[arg-type]
    assert count_shapley == count_closed_form(spec, suite)
    assert count_shapley[:4] == [Fraction(1000, 9)] * 4
    assert count_shapley[4:] == [Fraction(625, 9)] * 8

    decimal_table = values["V2_lambda_0_5"]
    subset_decimal = exact_shapley_decimal(decimal_table, spec.player_count)  # type: ignore[arg-type]
    mobius_decimal = shapley_via_mobius_decimal(decimal_table, spec.player_count)  # type: ignore[arg-type]
    assert max(abs(a - b) for a, b in zip(subset_decimal, mobius_decimal)) < Decimal("1e-70")
    with localcontext() as context:
        context.prec = 100
        assert abs(sum(subset_decimal, Decimal(0)) - Decimal(1000)) < Decimal("1e-70")

