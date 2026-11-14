# 06 TPC-H 公开数据最小验证

## 冻结对象

使用现有 TPC-H SF0.1 DuckDB，SHA-256 为 `8a11caa72d66f2f95a8258aa6859266dfe3e8a0b7288cddee0904c13f9187b8e`。地理按 customer nation，固定 AFRICA 的 ETHIOPIA/MOROCCO 与 AMERICA 的 ARGENTINA/CANADA，输出 global、2 region、4 nation 共 7 个节点。

玩家是原生 `Order`、`Lineitem`、`Supplier`、`Part` 行；Customer/Nation/Region 为外生维表。一个交易见证仅在对应四类玩家同时存在时激活。没有把 JOIN 输出当玩家，也没有使用旧 GNN 标签。

金额冻结为 `ROUND(l_extendedprice*(1-l_discount)*100)` 的整数分，promo 由原始 `p_type` 的 `PROMO` 前缀决定。SQL 位于 `sql/tpch_natural_extract.sql` 与 `sql/tpch_pressure_extract.sql`。

## 两个样本

自然样本按预先固定地理、`o_orderdate≥1992-01-01`、每个 nation 最早的 order/line 选取，不看算法速度：4 订单、4 行、4 供应商、4 零件，N=16，四个见证互不共享玩家。

压力样本预先固定 supplier 74，并在每个 nation 按指定 promo/non-promo 状态选最早一行：4 订单、4 行、1 供应商、4 零件，N=13。六对见证均共享同一个供应商玩家，最大成对重叠为 1。它是结构压力样本，不代表 TPC-H 总体分布。

## 价值与精确结果

| 样本 | 价值 | 非零联盟 | 不同值 | 负边际 | 负 Shapley 玩家 |
|---|---|---:|---:|---:|---:|
| natural | ADD | 14911 | 15 | 0 | 0 |
| natural | LOCAL | 4096 | 3 | 1024 | 4 |
| natural | CROSS | 496 | 3 | 124 | 4 |
| supplier-74 | ADD | 1695 | 15 | 0 | 0 |
| supplier-74 | LOCAL | 512 | 3 | 192 | 3 |
| supplier-74 | CROSS | 176 | 8 | 90 | 6 |

共享供应商使自然主外键数据中确实出现“一个物理玩家支持跨地区多个见证”的现象；CROSS 的可达值从 3 增至 8，且负 Shapley 玩家从 4 增至 6。它说明合成研究所关心的来源共享和非单调比例价值并非纯人工现象。

## 边界

本轮没有对 TPC-H 运行算法性能排名，也没有执行 SF1。自然样本与压力样本的 N、供应商数和 promo 组成不同，不能把两者的联盟计数差异归因于“共享”单一因素。这里的状态是 `VERIFIED_STRUCTURAL_EXISTENCE`，而不是 `VERIFIED_COST_EFFECT`。

证据：`runs/SHARED_20261113_181253/raw/tpch_source_rows.csv`、`tpch_player_mapping.csv`、`tpch_structure_metrics.csv`、`tpch_value_metrics.csv` 与 `tpch_record_shapley.csv`。

