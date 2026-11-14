WITH selected_geo(region_name, nation_name, want_promo) AS (
    VALUES ('AFRICA','ETHIOPIA',TRUE), ('AFRICA','MOROCCO',FALSE),
           ('AMERICA','ARGENTINA',TRUE), ('AMERICA','CANADA',FALSE)
), ranked AS (
    SELECT o.o_orderkey AS orderkey, l.l_linenumber AS linenumber,
           l.l_suppkey AS suppkey, l.l_partkey AS partkey,
           cn.n_name AS nation, rn.r_name AS region,
           CAST(ROUND(l.l_extendedprice * (1-l.l_discount) * 100) AS BIGINT) AS discounted_cents,
           starts_with(p.p_type, 'PROMO') AS promo,
           row_number() OVER (
               PARTITION BY rn.r_name, cn.n_name
               ORDER BY o.o_orderdate, o.o_orderkey, l.l_linenumber
           ) AS seq
    FROM orders o
    JOIN customer c ON c.c_custkey=o.o_custkey
    JOIN nation cn ON cn.n_nationkey=c.c_nationkey
    JOIN region rn ON rn.r_regionkey=cn.n_regionkey
    JOIN selected_geo g ON g.region_name=rn.r_name AND g.nation_name=cn.n_name
    JOIN lineitem l ON l.l_orderkey=o.o_orderkey
    JOIN supplier s ON s.s_suppkey=l.l_suppkey
    JOIN part p ON p.p_partkey=l.l_partkey
    WHERE l.l_suppkey=74
      AND starts_with(p.p_type, 'PROMO')=g.want_promo
)
SELECT orderkey, linenumber, suppkey, partkey, nation, region, discounted_cents, promo
FROM ranked WHERE seq=1 ORDER BY region, nation;

