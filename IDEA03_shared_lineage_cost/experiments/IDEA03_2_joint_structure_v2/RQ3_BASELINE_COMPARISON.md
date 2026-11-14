# RQ3 精确基线比较

> 2026-11-13 补充诊断更新：后续已完成 `SPARSE_HARSANYI_PROVENANCE` 和 `OFFICIAL_LEXASHAP_BOOLEAN_COMPONENTS` 的同一 N/Q/G 适配，并在 N=10–64 通过。当前状态以 `PREVIOUS_EXPLORATION_DIAGNOSIS.md` 为准；下表保留 E0–E2 阶段的原始边界并加入新增基线。

## 1. 实际执行状态

| 方法 | 当前冻结输入状态 | 证据 |
|---|---|---|
| DuckDB/Python 全联盟 oracle | VERIFIED（N=10、16、20） | 完整价值表、分配和误差 CSV |
| H3-S6 evidence-state | VERIFIED（N<=20）；RESOURCE_LIMIT（N=24） | 与 oracle 同目标核验；N=24 frontier 证据 |
| H3-S6 两坐标分别编译 | VERIFIED（一个 N=20 High/cross-add） | 线性合并与 oracle 核验 |
| P3 历史 MTBDD | INPUT_UNSUPPORTED | 历史对象不是本轮 E/B/H 物理玩家与35坐标游戏 |
| 稀疏 Harsanyi provenance | VERIFIED（N=10–64） | 从 SQL lineage 直接 inclusion-exclusion，不先枚举玩家联盟；N≤20 与 oracle 一致 |
| 官方 LExaShap Boolean 分量 | VERIFIED（N=10–64） | 将数值 G 严格分解为加权 Boolean DNF 分量；调用冻结官方 `DNFCircuit` |
| Abramovich 完整作者流水线 | ENV_BLOCKED | 本轮适配复用了官方核心电路，不等于恢复完整 SQL 前端/环境 |
| M3 变量排序 | REPORTED_ONLY | M3 仍是设计记录，没有可恢复的 BDD 运行证据 |
| 通用 BDD/d-DNNF | INPUT_UNSUPPORTED | 本轮没有已核验的同目标编译器适配 |

## 2. 可比较边界

全联盟 oracle 与 H3-S6 都计算同一玩家、查询和价值函数，可用于 exactness 比较。它们的内部“联盟数”“state 数”“BDD 节点数”不是同一单位，报告没有直接横向比较这些计数。

H3-S6 的 source、transform、compile、solve 计时按实际 API 边界记录。B0 的 compile 为0是因为它没有知识编译阶段，不是人为填充后参与对数比；报告中的交互只在四格均有正、实测阶段值时计算比率。

## 3. 已获得的成熟方法反证

H3-S6 在 N=20 的 direct shared representation 比同一实例的 separate-linear 编译更快，同时保持精确。这说明“共同来源必然造成重复计算”的说法不成立，至少一个现有共享状态框架能复用来源表达。

补充诊断已经证明 Boolean 分量与 Harsanyi 分解能够高效处理当前游戏，因此不能再把当前 N=24 写成游戏内在困难。MTBDD、通用 d-DNNF 和真正利用图宽的变量消去仍未适配，故仍不能对所有成熟精确算法作性能排名。

## 4. 不能作为证据的比较

- 不使用旧 P3、H5 或作者程序的历史慢速直接宣布新瓶颈。
- 不把 `INPUT_UNSUPPORTED` 当作算法失败。
- 不把 N=24 的 S6 状态上限外推为所有精确算法都指数失败。
- 不把 E2 未执行的 solver 时间填0后计算对数交互。

