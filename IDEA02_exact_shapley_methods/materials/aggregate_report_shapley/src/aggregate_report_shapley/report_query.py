from __future__ import annotations

from collections.abc import Iterable

import duckdb

from .d1 import D1_CELLS
from .model import cell_key
from .report_state import ReportState


_GROUPING_SQL = """
SELECT
    {mask_projection}
    region_id,
    city_id,
    category_id,
    GROUPING(region_id) AS g_region,
    GROUPING(city_id) AS g_city,
    GROUPING(category_id) AS g_category,
    COUNT(*)::BIGINT AS n,
    SUM(amount)::BIGINT AS total_amount
FROM selected
GROUP BY {mask_grouping} GROUPING SETS (
    (),
    (region_id),
    (region_id, city_id),
    (category_id),
    (region_id, category_id)
)
"""


def _decode_cell(
    region_id: str | None,
    city_id: str | None,
    category_id: str | None,
    g_region: int,
    g_city: int,
    g_category: int,
) -> str:
    pattern = (g_region, g_city, g_category)
    if pattern == (1, 1, 1):
        return cell_key("all", "ALL")
    if pattern == (0, 1, 1):
        return cell_key("region", str(region_id))
    if pattern == (0, 0, 1):
        return cell_key("city", str(city_id))
    if pattern == (1, 1, 0):
        return cell_key("category", str(category_id))
    if pattern == (0, 1, 0):
        return cell_key("region_category", str(region_id), str(category_id))
    raise ValueError(f"unexpected grouping pattern: {pattern}")


def query_d1_report(
    connection: duckdb.DuckDBPyConnection, record_ids: Iterable[str]
) -> ReportState:
    selected_ids = list(record_ids)
    rows = connection.execute(
        "WITH selected AS ("
        "SELECT r.region_id, f.city_id, f.category_id, f.amount "
        "FROM Fact f JOIN City c USING (city_id) JOIN Region r USING (region_id) "
        "WHERE f.record_id IN (SELECT * FROM UNNEST(?::VARCHAR[]))"
        ") "
        + _GROUPING_SQL.format(mask_projection="", mask_grouping=""),
        [selected_ids],
    ).fetchall()
    state = ReportState.empty(D1_CELLS)
    for region, city, category, gr, gc, gcat, count, total in rows:
        cell = _decode_cell(region, city, category, gr, gc, gcat)
        state.counts[cell] = int(count)
        state.sums[cell] = 0 if total is None else int(total)
    return state


def query_all_d1_reports(connection: duckdb.DuckDBPyConnection) -> list[ReportState]:
    rows = connection.execute(
        """
        WITH selected AS (
            SELECT masks.mask, r.region_id, f.city_id, f.category_id, f.amount
            FROM range(4096) AS masks(mask)
            JOIN Fact f ON ((masks.mask >> f.player_index) & 1) = 1
            JOIN City c USING (city_id)
            JOIN Region r USING (region_id)
        )
        """
        + _GROUPING_SQL.format(mask_projection="mask,", mask_grouping="mask,"),
    ).fetchall()
    states = [ReportState.empty(D1_CELLS) for _ in range(4096)]
    for mask, region, city, category, gr, gc, gcat, count, total in rows:
        cell = _decode_cell(region, city, category, gr, gc, gcat)
        state = states[int(mask)]
        state.counts[cell] = int(count)
        state.sums[cell] = int(total)
    return states

