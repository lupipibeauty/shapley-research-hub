# IDEA-03-3-2：多统计坐标的共享数值状态

## 判定

`UNCLEAR_NEEDS_ONE_GATE`

## 研究问题

在同一联盟来源上，是否能用一个精确状态同时维护 COUNT、COUNT DISTINCT、SUM、比例及 NULL 语义，并直接服务完整报表 Shapley，而不是把每个坐标先展开成大量独立布尔阈值或 Möbius 分量？

## 最强已有工作

1. Amsterdamer、Deutch 与 Tannen（PODS 2011）：K-semimodule 与 tensor product 给出聚合 provenance 的一般语义，直接支持把来源注释与聚合载荷组合；其目标是正确 provenance，不是 coalition-size Shapley 状态。
2. Standke 与 Kimelfeld（PACMMOD 2025），PDF p. 8 Theorem 3.1、p. 10 Theorem 4.1、p. 11 Lemma 4.3、p. 12 Theorem 5.1：在 AggCQ 上分别给出 SUM/COUNT、MIN/MAX/COUNT DISTINCT、AVG/quantile 等 Shapley 边界。论文的输出是单个聚合查询，COUNT DISTINCT 通过存在性指标求和；没有一个同时服务完整异构报表的联合状态定理。
3. LMFAO（SIGMOD 2019）Section 3.5 和 F-IVM（Kara 等，VLDB Journal 2024，pp. 903--929）的 view tree/ring：多聚合共享关系扫描、视图与算术运算，证明 L1/L4 的批量聚合维护成熟；未把联盟大小维度和全玩家 Shapley 消息纳入状态。
4. 既有 Stage 2A：比例坐标经 Möbius/布尔分量展开后可精确求解，但这只证明一种归约可行，未证明该展开在表示大小上最优。

## 理论边界

- 向量积 monoid/semiring 可以把多个可合并聚合放入一个状态；这属于表达能力，不自动得到更小的状态空间。
- COUNT DISTINCT 需要对象身份或存在性状态；比例需要分子/分母以及分母为零时的 NULL 标志。把这些状态合并可能减少重复来源遍历，也可能因笛卡尔积导致状态爆炸。
- 对坐标可加的 \(G\)，Shapley 线性性允许逐坐标求和；但这不证明逐坐标布尔化是最优实现。

## 唯一 gate：GATE-A

在一个已冻结、可由全联盟 oracle 核验的 N≤16 完整报表实例上，固定同一 \((N,Q,G)\)，比较：

1. 现有布尔阈值/Möbius 分量路径；
2. 一个直接的精确联合状态 DP，只允许使用 `(coalition_size, distinct-identity state, count, sum, numerator, denominator, null_flag)` 中实际需要的分量。

必须报告：状态数、峰值 frontier、构造/求解时间、输出前时间、显式输出时间和逐玩家误差。准入条件不是“更快一次”，而是联合状态在至少两个结构规模上避免分量数乘法，且保持完全相同的 \((N,Q,G)\)。若状态乘积不小于分解路径，则该分支降为 `ENGINEERING_ONLY` 或被归约覆盖。
