# 00 历史复用与本轮边界

## 研究对象

本轮只审计本地 TPC-H SF0.1 上的 Q9 来源结构，判断它在两套预先冻结的物理玩家边界下是否产生 F0 没有覆盖的真实非星形 provenance，以及是否具备后续完整统计产品兼容性。

## 直接继承而不重跑的结论

- 阶段2A：官方 LExaShap 已完成正 DNF 与冻结价值的精确适配，不重复 correctness。
- 阶段2B-0：F0 是企业中心星形来源；incidence/primal treewidth 为1/2；合理企业分量顺序可把最大因子压至16；最终判断为 `MOVE_TO_REAL_NONSTAR_PROVENANCE`。
- 历史 TPC-H supplier74：4条 witness 最多只共享1个 Supplier 玩家，只作低重叠历史背景。
- 历史 GNN TPC-H：玩家含 Order、Customer、Lineitem、Supplier、Nation，不含本轮关键的 PARTSUPP 桥接事实。
- 历史 H3-J2：使用合成 PARTSUPP/LINEITEM fixture 和 owner 绑定，不等同于公开 TPC-H 物理元组来源。

## 数据与SQL

- 数据库：`tmp/researchlab_v2/workspace/BRBD_v1/runs/R1_luo/tpch_sf01/tpch_sf01.duckdb`
- 本地作者Q9：`aggregate_report_shapley/external/abramovich/source/LExaBan-LExaShap-main/Queries/TPC-H/9.sql`
- 本轮等价witness查询：`sql/q9_witness_extract.sql`

本地作者Q9在标准Q9语义上加入 `p_partkey % 64 = 0` 作为实验缩减，并在最外层加入无排序的 `LIMIT 10`。本轮保留全部JOIN条件、`green`过滤和模64过滤，保留 `nation × order_year` 分组语义；不把外层展示用 `LIMIT 10` 用于裁剪来源总体，因为它不改变组内witness定义，且历史402条初检针对完整合格基础行。该口径在运行前固定。

## 禁止边界

不重新生成数据，不修改外键或JOIN，不枚举联盟，不计算Shapley，不运行算法性能比较，不修改G，不扩大到SF1/JOB/TPC-DS，不执行Git操作。

## 方法流程说明

本轮的“先冻结单位与边界、再提取证据、最后判断适用性”流程参考了 Scientific Agent Skills 的实验设计与科学批判性审计程序：Kassis, T., Agarwal, V., He, Y., Patel, S., & Brueckner, A. M. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. arXiv:2609.00065. https://doi.org/10.48550/arXiv.2609.00065 。本轮未联网复核其后续版本信息。
