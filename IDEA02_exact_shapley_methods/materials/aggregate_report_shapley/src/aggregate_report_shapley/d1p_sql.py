from __future__ import annotations

import duckdb

from .d1p import D1PSpec, D1PState


_AGGREGATE_TEMPLATE = """
WITH selected AS (
    SELECT masks.mask, b.player_index, b.record_id, b.leaf_node_id,
           b.category_a_id, {present_expression} AS attribute_present,
           {category_b_expression} AS category_b_id
    FROM range({coalition_count}) AS masks(mask)
    JOIN ({base_relation}) AS b
      ON ((masks.mask >> b.player_index) & 1) = 1
    {optional_join}
), expanded AS (
    SELECT s.mask, nodes.node_id, s.category_a_id,
           s.attribute_present, s.category_b_id
    FROM selected s
    JOIN Hierarchy h USING (leaf_node_id)
    CROSS JOIN UNNEST([s.leaf_node_id, h.parent_node_id, h.root_node_id]) AS nodes(node_id)
)
SELECT mask, node_id,
       COUNT(*)::BIGINT AS total_count,
       SUM(CASE WHEN category_a_id = ? THEN 1 ELSE 0 END)::BIGINT AS category_a_target_count,
       SUM(CASE WHEN attribute_present THEN 1 ELSE 0 END)::BIGINT AS attribute_present_count,
       SUM(CASE WHEN attribute_present AND category_b_id = ? THEN 1 ELSE 0 END)::BIGINT AS category_b_target_count
FROM expanded
GROUP BY mask, node_id
ORDER BY mask, node_id
"""


def create_d1p_database(connection: duckdb.DuckDBPyConnection, spec: D1PSpec) -> None:
    connection.execute(
        "CREATE TABLE Hierarchy(leaf_node_id VARCHAR, parent_node_id VARCHAR, root_node_id VARCHAR)"
    )
    connection.executemany(
        "INSERT INTO Hierarchy VALUES (?, ?, ?)",
        [spec.ancestors[leaf] for leaf in sorted(spec.ancestors)],
    )
    for source in sorted({record.source for record in spec.records}):
        connection.execute(
            f"CREATE TABLE BasicSource_{source}(player_index INTEGER, record_id VARCHAR, leaf_node_id VARCHAR, category_a_id VARCHAR)"
        )
        connection.executemany(
            f"INSERT INTO BasicSource_{source} VALUES (?, ?, ?, ?)",
            [
                (r.player_index, r.record_id, r.leaf_node_id, r.category_a_id)
                for r in spec.records
                if r.source == source
            ],
        )
    connection.execute("CREATE TABLE OptionalAttribute(record_id VARCHAR, category_b_id VARCHAR)")
    optional_rows = [
        (r.record_id, r.category_b_id) for r in spec.records if r.attribute_present
    ]
    connection.executemany("INSERT INTO OptionalAttribute VALUES (?, ?)", optional_rows)
    connection.execute(
        "CREATE TABLE UnifiedFact(player_index INTEGER, record_id VARCHAR, leaf_node_id VARCHAR, category_a_id VARCHAR, attribute_present BOOLEAN, category_b_id VARCHAR)"
    )
    connection.executemany(
        "INSERT INTO UnifiedFact VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                r.player_index,
                r.record_id,
                r.leaf_node_id,
                r.category_a_id,
                r.attribute_present,
                r.category_b_id,
            )
            for r in spec.records
        ],
    )


def _rows_to_states(rows: list[tuple], spec: D1PSpec) -> list[D1PState]:
    states = [D1PState.empty(spec.nodes) for _ in range(1 << spec.player_count)]
    for mask, node, total, category_a, present, category_b in rows:
        states[int(mask)].counts[str(node)] = [
            int(total), int(category_a), int(present), int(category_b)
        ]
    return states


def query_all_sql_p(connection: duckdb.DuckDBPyConnection, spec: D1PSpec) -> list[D1PState]:
    sources = sorted({record.source for record in spec.records})
    union = " UNION ALL ".join(f"SELECT * FROM BasicSource_{source}" for source in sources)
    sql = _AGGREGATE_TEMPLATE.format(
        coalition_count=1 << spec.player_count,
        base_relation=union,
        present_expression="(o.record_id IS NOT NULL)",
        category_b_expression="o.category_b_id",
        optional_join="LEFT JOIN OptionalAttribute o USING (record_id)",
    )
    rows = connection.execute(
        sql, [spec.category_a_target, spec.category_b_target]
    ).fetchall()
    return _rows_to_states(rows, spec)


def query_all_sql_u(connection: duckdb.DuckDBPyConnection, spec: D1PSpec) -> list[D1PState]:
    sql = _AGGREGATE_TEMPLATE.format(
        coalition_count=1 << spec.player_count,
        base_relation="SELECT player_index, record_id, leaf_node_id, category_a_id, attribute_present, category_b_id FROM UnifiedFact",
        present_expression="b.attribute_present",
        category_b_expression="b.category_b_id",
        optional_join="",
    )
    rows = connection.execute(
        sql, [spec.category_a_target, spec.category_b_target]
    ).fetchall()
    return _rows_to_states(rows, spec)

