WITH active_e AS (SELECT e.* FROM e JOIN active_players a USING (player_index)),
active_b AS (SELECT b.* FROM b JOIN active_players a USING (player_index)),
active_h AS (SELECT h.* FROM h JOIN active_players a USING (player_index)),
active_r AS (SELECT r2.* FROM r2 JOIN active_players a USING (player_index)),
eligible AS (
  SELECT DISTINCT b.sid,b.eid,r.city,b.industry,h.workers,d.province
  FROM active_b b JOIN active_e e USING(eid) JOIN active_h h USING(sid)
  JOIN active_r r USING(eid) JOIN d ON d.city=r.city
), expanded AS (
  SELECT 'NAT' node,* FROM eligible UNION ALL SELECT province node,* FROM eligible UNION ALL SELECT city node,* FROM eligible
), agg AS (
 SELECT node,COUNT(DISTINCT eid) enterprise_count,COUNT(DISTINCT sid) site_count,
        SUM(workers) workers,SUM(workers) FILTER(WHERE industry='manufacturing') mfg_workers
 FROM expanded GROUP BY node
)
SELECT n.node,COALESCE(a.enterprise_count,0) enterprise_count,COALESCE(a.site_count,0) site_count,
       COALESCE(a.workers,0) workers,COALESCE(a.mfg_workers,0) mfg_workers,
       CASE WHEN COALESCE(a.workers,0)=0 THEN NULL ELSE COALESCE(a.mfg_workers,0)::DOUBLE/a.workers END mfg_share
FROM nodes n LEFT JOIN agg a USING(node) ORDER BY n.ord;
