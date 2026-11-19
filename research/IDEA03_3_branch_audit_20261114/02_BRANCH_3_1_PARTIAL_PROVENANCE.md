# IDEA-03-3-1：完整报表输出间的部分 provenance 共享

## 判定

`REPRESENTATION_ONLY`

## 研究问题

不同报表坐标的来源表达式只部分相同而非完全相同，能否把公共 witness、公共子公式或公共编译节点只构造一次，并进一步减少全部玩家 Shapley 的重复计算？

## 最强已有工作

1. Green、Karvounarakis 与 Tannen（PODS 2007），PDF pp. 2--5，Definitions 3.1--3.2、Proposition 3.5、Theorem 4.3：K-relations 与通用 \(\mathbb N[X]\) provenance 提供组合查询的符号来源语义及同态交换性质。研究对象是查询答案的 provenance，不是玩家 Shapley。
2. Amsterdamer、Deutch 与 Tannen（PODS 2011），PDF 中聚合 provenance 的 K-semimodule/tensor-product 构造：覆盖聚合值的来源语义和 set/bag 兼容性，不提供全玩家、多根 Shapley 算法。
3. Schleich 等（SIGMOD 2019）LMFAO，PDF pp. 1、5--7，Section 3.5：多个 directional views 共用扫描和 multi-output operator，说明多输出共享执行是成熟思想；玩家、联盟价值和 Shapley 均不在论文对象中。
4. Abramovich 等（PVLDB 2025），扩展稿 PDF pp. 6--9，Algorithms 1--3；Theorem 3.6：给定单个 d-tree，可对一个根计算全部变量 Banzhaf/Shapley。GROUP BY 被处理为逐组 lineage，未给出跨组公共子 DAG 的联合反向算法。

## 与本题的关系

上述文献直接覆盖了 L2/L3 的“公共表达可以共享表示”，但没有直接覆盖 L5 的“多个报表根共享 coalition-size Shapley 消息”。Stage 2A 也仅验证 complete DNF 缓存。因此本分支不能标为 `DIRECTLY_COVERED`，也尚不足以标为 `SURVIVES_AUDIT`：表示层原则已成熟，真正未决部分应交给 3-3 的多根归因 gate，而不是另开一个 provenance 工程。

## 关闭/保留边界

- 关闭为独立创新的部分：只做 hash-consing、公共子式消除、共享扫描或共享 DAG。
- 保留为依赖条件的部分：公共子 DAG 是否能被 L5 的多根 coalition-size 反向计算实际利用。
- 本分支不单独设置 gate，避免与 3-3 重复。
