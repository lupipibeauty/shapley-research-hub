-- Q9 provenance witness extraction for the locally archived Abramovich query.
-- JOIN predicates and WHERE filters are unchanged. The outer GROUP BY is represented
-- by emitting nation/order_year on every base witness. The author-instrumentation
-- LIMIT 10 is not used to truncate the full source population.
SELECT
    l.l_orderkey AS orderkey,
    l.l_linenumber AS linenumber,
    l.l_partkey AS partkey,
    l.l_suppkey AS suppkey,
    n.n_nationkey AS nationkey,
    n.n_name AS nation,
    n.n_regionkey AS regionkey,
    EXTRACT(year FROM o.o_orderdate) AS order_year,
    l.l_quantity AS quantity,
    l.l_extendedprice * (1 - l.l_discount) AS revenue,
    ps.ps_supplycost * l.l_quantity AS supply_cost,
    l.l_extendedprice * (1 - l.l_discount) - ps.ps_supplycost * l.l_quantity AS profit
FROM part AS p
JOIN lineitem AS l
  ON p.p_partkey = l.l_partkey
JOIN partsupp AS ps
  ON ps.ps_partkey = l.l_partkey
 AND ps.ps_suppkey = l.l_suppkey
JOIN supplier AS s
  ON s.s_suppkey = l.l_suppkey
JOIN orders AS o
  ON o.o_orderkey = l.l_orderkey
JOIN nation AS n
  ON n.n_nationkey = s.s_nationkey
WHERE p.p_name LIKE '%green%'
  AND p.p_partkey % 64 = 0
ORDER BY n.n_name, order_year, l.l_partkey, l.l_suppkey,
         l.l_orderkey, l.l_linenumber;
