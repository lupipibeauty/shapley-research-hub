from __future__ import annotations

import duckdb

from aggregate_report_shapley.d1 import D1_CELLS, D1_MEMBERSHIP, D1_RECORDS
from aggregate_report_shapley.database_loader import create_d1_database
from aggregate_report_shapley.report_query import query_all_d1_reports, query_d1_report
from aggregate_report_shapley.report_state import all_coalition_states, assert_same_state


def test_sql_matches_incremental_for_all_4096_coalitions() -> None:
    connection = duckdb.connect(":memory:")
    create_d1_database(connection)
    sql_states = query_all_d1_reports(connection)
    incremental = all_coalition_states(D1_RECORDS, D1_MEMBERSHIP, D1_CELLS)
    for mask in range(4096):
        assert_same_state(sql_states[mask], incremental[mask], D1_CELLS, context=f"mask={mask}")


def test_single_query_preserves_empty_coordinates() -> None:
    connection = duckdb.connect(":memory:")
    create_d1_database(connection)
    state = query_d1_report(connection, [])
    assert tuple(state.counts) == D1_CELLS
    assert all(count == 0 for count in state.counts.values())
    assert all(state.average(cell) is None for cell in D1_CELLS)

