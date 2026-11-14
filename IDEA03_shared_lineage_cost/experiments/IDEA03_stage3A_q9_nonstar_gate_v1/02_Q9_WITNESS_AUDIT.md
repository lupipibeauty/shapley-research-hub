# 02 Q9真实witness审计

## 提取口径

`sql/q9_witness_extract.sql`保留本地作者Q9的六表JOIN条件、`p_name LIKE '%green%'`和 `p_partkey % 64 = 0` 过滤。外层 `nation × order_year` 分组通过在每条基础行保存组键实现；无排序的展示用 `LIMIT 10` 不用于截断来源总体。

每条记录保存真实物理键：PART、SUPPLIER、PARTSUPP复合键、LINEITEM复合键和ORDERS主键，同时保存nation、regionkey、year、quantity、revenue、supply cost和profit。JOIN输出行仅作为witness，不是玩家。

## 数量核验

| 指标 | 初检预期 | 正式结果 | 状态 |
|---|---:|---:|---|
| witness总数 | 402 | 402 | MATCH |
| 不同 `(partkey,suppkey)` | 52 | 52 | MATCH |
| 单一PARTSUPP最大witness数 | 14 | 14 | MATCH |

正式明细见 `results/q9_witnesses.csv`，核验表见 `results/precheck_validation.csv`。

## 物理事实检查

- 402个LINEITEM玩家均由 `(l_orderkey,l_linenumber)` 标识；
- PARTSUPP玩家由数据库复合键 `(ps_partkey,ps_suppkey)` 标识；
- ORDERS、PART、SUPPLIER均使用各自主键；
- 未生成虚拟外键、owner绑定或人工桥表；
- 数据库以DuckDB `read_only=True`打开。

例如 `PART=7168、SUPPLIER=683` 的不同交易行共享真实的PART、SUPPLIER和PARTSUPP记录；这不是把多条行事后打包产生的共享。

## 与历史TPC-H实验的区别

历史supplier74样本只有4条witness，最多共享一个Supplier；GNN数据没有PARTSUPP玩家；H3-J2的共享来自合成owner映射。本轮首次在现有SF0.1物理元组上同时保留PART、SUPPLIER、PARTSUPP、LINEITEM和ORDERS的Q9来源边界。
