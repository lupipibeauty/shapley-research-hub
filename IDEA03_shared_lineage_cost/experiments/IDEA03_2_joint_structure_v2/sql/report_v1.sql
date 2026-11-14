-- IDEA03-2 RQ3 V2: full E/B/H JOIN semantics.
-- SQL keeps mfg_share NULL when workers=0; value scoring handles NULL separately.
WITH masks AS (
    SELECT range::UBIGINT AS mask FROM range($coalition_count)
),
witness AS (
    SELECT
        e.eid,
        b.sid,
        b.city,
        b.industry,
        h.workers,
        d.province,
        ((1::UBIGINT << e.player_index)
         | (1::UBIGINT << b.player_index)
         | (1::UBIGINT << h.player_index)) AS required_mask
    FROM E e
    JOIN B b USING (eid)
    JOIN H h USING (sid)
    JOIN D d USING (city)
    WHERE h.year = $year
),
selected AS (
    SELECT m.mask, w.*
    FROM masks m
    JOIN witness w ON (m.mask & w.required_mask) = w.required_mask
),
expanded AS (
    SELECT mask, 'NAT' AS node, * EXCLUDE(mask, province) FROM selected
    UNION ALL
    SELECT mask, province AS node, * EXCLUDE(mask, province) FROM selected
    UNION ALL
    SELECT mask, city AS node, * EXCLUDE(mask, province) FROM selected
),
nodes(node, node_order) AS (
    VALUES ('NAT',0),('PA',1),('PB',2),('A1',3),('A2',4),('B1',5),('B2',6)
),
agg AS (
    SELECT
        mask,
        node,
        COUNT(DISTINCT eid)::BIGINT AS enterprise_count,
        COUNT(DISTINCT sid)::BIGINT AS site_count,
        SUM(workers)::BIGINT AS workers,
        SUM(workers) FILTER (WHERE industry='manufacturing')::BIGINT AS mfg_workers
    FROM expanded
    GROUP BY mask,node
)
SELECT
    m.mask,
    n.node,
    COALESCE(a.enterprise_count,0)::BIGINT AS enterprise_count,
    COALESCE(a.site_count,0)::BIGINT AS site_count,
    COALESCE(a.workers,0)::BIGINT AS workers,
    COALESCE(a.mfg_workers,0)::BIGINT AS mfg_workers,
    CASE WHEN COALESCE(a.workers,0)=0 THEN NULL
         ELSE COALESCE(a.mfg_workers,0)::DOUBLE/a.workers END AS mfg_share
FROM masks m
CROSS JOIN nodes n
LEFT JOIN agg a USING(mask,node)
ORDER BY m.mask,n.node_order;

