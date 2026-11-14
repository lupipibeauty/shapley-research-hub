WITH active_e AS (
  SELECT e.* FROM e JOIN active_players a USING (player_index)
), active_b AS (
  SELECT b.* FROM b JOIN active_players a USING (player_index)
), active_h AS (
  SELECT h.* FROM h JOIN active_players a USING (player_index)
), eligible AS (
  SELECT DISTINCT b.sid, b.eid, b.city, b.industry, h.workers, d.province
  FROM active_b b
  JOIN active_e e USING (eid)
  JOIN active_h h USING (sid)
  JOIN d USING (city)
), expanded AS (
  SELECT 'NAT' AS node, * FROM eligible
  UNION ALL SELECT province AS node, * FROM eligible
  UNION ALL SELECT city AS node, * FROM eligible
), agg AS (
  SELECT
    node,
    COUNT(DISTINCT eid) AS enterprise_count,
    COUNT(DISTINCT sid) AS site_count,
    SUM(workers) AS workers,
    SUM(workers) FILTER (WHERE industry='manufacturing') AS mfg_workers
  FROM expanded
  GROUP BY node
)
SELECT
  n.node,
  COALESCE(a.enterprise_count, 0) AS enterprise_count,
  COALESCE(a.site_count, 0) AS site_count,
  COALESCE(a.workers, 0) AS workers,
  COALESCE(a.mfg_workers, 0) AS mfg_workers,
  CASE
    WHEN COALESCE(a.workers, 0)=0 THEN NULL
    ELSE COALESCE(a.mfg_workers, 0)::DOUBLE/a.workers
  END AS mfg_share
FROM nodes n
LEFT JOIN agg a USING (node)
ORDER BY n.ord;
