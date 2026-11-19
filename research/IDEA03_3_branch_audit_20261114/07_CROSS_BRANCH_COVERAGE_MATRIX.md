# 跨分支覆盖矩阵

| 工作 | 原始对象/玩家 | 输出 | L1 | L2 | L3 | L4 | L5 | 对本题的覆盖 |
|---|---|---|---:|---:|---:|---:|---:|---|
| Green et al. 2007 | K-relations；元组变量 | 查询答案 provenance |  | ✓ | ✓ |  |  | 表示层 |
| Amsterdamer et al. 2011 | 聚合查询；元组注释 | 聚合 provenance |  | ✓ | ✓ | ✓语义 |  | 表示/语义层 |
| Livshits et al. 2020 | Boolean/self-join-free CQ；endogenous tuples | 单查询全部元组 Shapley |  | ✓ | ✓ | 按查询 | ✓单根 | 单根直接覆盖 |
| Standke--Kimelfeld 2025 | 单个 AggCQ；endogenous tuples | 单聚合查询全部元组 Shapley |  | ✓ | ✓ | ✓单聚合 | ✓单根 | 单聚合直接覆盖 |
| Abramovich et al. 2025 | 单个 lineage/d-tree；变量 | 单根全部变量 Shapley/Banzhaf |  | ✓ | ✓ | 部分聚合 | ✓单根 | 单根直接覆盖 |
| ProvSQL 2019--2026 | 单个 provenance token；元组变量 | 单 token 全变量 Shapley | ✓ | ✓ | ✓ | Boolean root | ✓单根 | 单根系统实现 |
| Kara--Olteanu--Suciu 2024 | Boolean formula/CQ；变量/元组 | 单 Boolean 输出 Shapley |  | ✓ | ✓ | Boolean | ✓单根 | Boolean 归约覆盖 |
| LMFAO 2019 | 批量 group-by aggregates；无玩家 | 多聚合值 | ✓ |  | ✓views | ✓ |  | L1/L4，非归因 |
| F-IVM 2024 | 动态关系数据库；无玩家 | 多查询/聚合维护 | ✓ |  | ✓view tree | ✓ |  | L1/L4，非归因 |
| Baur--Strassen 1983 | straight-line scalar function；输入变量 | 单标量值及全部一阶偏导 |  |  | ✓circuit |  | ✓普通单根梯度 | 不能替代 coalition-size 多根消息 |
| Ieong--Shoham 2005 | MC-net 玩家规则 | 全玩家 Shapley |  |  | ✓规则 | 局部因子 | ✓加法分解 | 3-5 归约覆盖 |
| Igarashi et al. 2018 | 一般合作博弈；玩家依赖图 | 全玩家 Shapley |  |  |  |  | ✓FPT by degree | 玩家图相邻覆盖 |

## 分支结论

| 分支 | 状态 | 核心理由 | gate |
|---|---|---|---|
| 3-1 partial provenance | `REPRESENTATION_ONLY` | 公共表示成熟，多根 Shapley 未直接覆盖 | 无；并入 3-3 |
| 3-2 numeric state | `UNCLEAR_NEEDS_ONE_GATE` | 多聚合状态成熟，但 coalition-size 精确联合状态未证实 | GATE-A |
| 3-3 multi-output gradient | `UNCLEAR_NEEDS_ONE_GATE` | 单根 all-player 成熟；多根显式 Jacobian仍有 MN 下界与内部复用疑问 | GATE-B |
| 3-4 multi-G | `SURVIVES_AUDIT` | 可加子类归约覆盖；非可加 multi-G 无同题直接算法 | 不另设；依赖 A/B |
| 3-5 interaction sparsity | `REDUCTION_COVERED` | 显式局部因子由 Shapley 线性性精确分解 | 无 |

## 论文正文定位与代码状态

| 论文 | 年份/venue | 核心定位 | 代码状态 |
|---|---|---|---|
| Green et al., *Provenance Semirings* | 2007/PODS | PDF pp.2--5，Defs.3.1--3.2, Prop.3.5, Thm.4.3 | 非算法系统论文 |
| Amsterdamer et al., *Provenance for Aggregate Queries* | 2011/PODS | 聚合 provenance 的 semimodule/tensor product 章节 | 本地 PDF；无本轮执行 |
| Livshits et al., *The Shapley Value of Tuples in Query Answering* | 2020/ICDT | PDF p.9 Thm.9；pp.10--11 Thm.11/Alg.1；p.14 Thm.13/Cor.15/Prop.16 | 历史复现档案存在 |
| Standke & Kimelfeld, aggregate queries | 2025/PACMMOD | pp.8--12 Thms.3.1,4.1,5.1; Lem.4.3 | 理论论文；本轮未执行 |
| Abramovich et al., *Advancing Fact Attribution...* | 2025/PVLDB 18(11) | 扩展稿 pp.6--9 Algs.1--3, Thm.3.6 | 作者代码已在 Stage2A/3B1 使用 |
| Kara, Olteanu & Suciu, *From Shapley Value to Model Counting...* | 2024/PODS | p.5 Prop.2.3；pp.6--7 Thm.3.1；p.11 Thm.4.1；pp.14--16 Thm.5.1 | 本地 PDF 指针损坏，页码来自保存的全文提取；需后续视觉复核 |
| Schleich et al., LMFAO | 2019/SIGMOD | PDF Section3.5, pp.6--7；Fig.4 | 公开系统；未适配 Shapley |
| Ieong & Shoham, MC-nets | 2005/EC | PDF p.5 Prop.5 | 论文算法；无需本轮执行 |
| Igarashi et al., bounded dependency | 2018/AAAI | 印刷 p.1067 Thm.8 | 理论算法；需给定 dependency graph/oracle |

`Kara et al. 2024` 的 PDF 视觉预检状态为 `UNAVAILABLE`，不能把保存的文本定位写成已视觉验收。
