# 01 历史 E1 在冻结新 G 下的增量核验

## Material Passport

- 阶段：IDEA-03 阶段1，实验1。
- 新计算对象：历史 E1 第一组 concentrated/dispersed 在冻结 `v_fid_main` 与 `v_gap_PA_PB_mfg_share` 下的联盟游戏。
- 历史复用：`SHARED_20261113_175706`、`SHARED_20261113_180500`。
- 状态：`VERIFIED + NEGATIVE_CONTROL`。
- 未执行：旧 GC、旧390次 SQL 掩码、旧 ROADD/LExaShap、E1 第2/3组。

## 1. 历史复用清单

| 内容 | 本轮处理 | 依据 |
|---|---|---|
| G1=GR、k=2 GC unanimity | 直接继承，不重算 | `SHARED_20261113_181356` |
| E1 三组6个夹具及390次 SQL/Python 掩码 | 直接复用冻结第一组输入；不重跑 SQL | `SHARED_20261113_175706` |
| GC 的392个 Harsanyi 项、108/63 DNF 子句 | 直接继承，不重新研究 | `e1_structure_metrics.csv` |
| ROADD exactness、LExaShap 完整分量缓存 | 直接继承，不重跑 | `SHARED_20261113_180500` |
| TPC-H supplier74 | 仅作结构背景，不重构 | `SHARED_20261113_181253` |
| 冻结 G、NULL、权重和尺度 | 原样读取 | 阶段0配置 SHA-256 `e05c7a...f591` |
| 本轮新增 | 两个旧 E1 夹具的全联盟新 G、exact Shapley、Harsanyi 与坐标差异 | 本目录 `results/old_e1_*` |

直接复用的函数包括 `build_controlled_f2`、`report_python`、`mobius_from_values`、`poly_shapley` 以及阶段0的固定损失和坐标权重函数。全联盟真值仅用于 N=16 oracle 与表示审计，没有作为结构化求解器输入。

## 2. 实际结果

| 夹具 | G | 完整35坐标状态 | G 状态 | 非零联盟 | `v(N)` | 非零 Harsanyi | 最高阶 |
|---|---|---:|---:|---:|---:|---:|---:|
| concentrated | `v_fid` | 16 | 16 | 22,687 | 5/6 | 483 | 16 |
| dispersed | `v_fid` | 100 | 49 | 22,687 | 1 | 483 | 16 |
| concentrated | `v_gap` | 16 | 9 | 2,401 | 1 | 441 | 16 |
| dispersed | `v_gap` | 100 | 9 | 2,401 | 1 | 441 | 16 |

`v_fid` 的两个联盟表有22,687个掩码不同，16名玩家的 Shapley 均发生变化；排序后的 Shapley 多重集也不同，因此差异不是玩家重命名。最大单玩家绝对变化约为 `0.03413`。

`v_gap` 则逐联盟完全相同，Shapley 向量和多重集也完全相同，故标记为 `NEGATIVE_CONTROL`。原因是 gap 只读取省级制造业就业比例；省内 A1/A2 或 B1/B2 的 R2 分散在省级 OR 后仍是同一激活条件。

## 3. 哪些坐标造成主保真度差异

满联盟有16个坐标不同：

- 全国：`workers`、`mfg_workers`；
- PA、PB：各自的 `workers`、`mfg_workers`；
- A2、B2：五个坐标全部不同。

此外，部分满联盟数值相同的坐标，其联盟来源游戏仍不同。例如 A1/B1 的 enterprise/site/worker/ratio，以及全国和省级比例。总计27个坐标的分量游戏按固定玩家 ID 不同。

根因不是评分公式改变，而是 F2 的 entity-city 链接：dispersed 模式让同一企业的全部场所在同省两个城市出现。`COUNT DISTINCT` 在全国/省级可消除部分重复，但 `SUM(workers)` 与条件 SUM 会累计城市展开后的多行。阶段0的完整35坐标保真度读取这些变化，而旧 GC 只读取省级门槛和比例，因而没有捕捉到。

不同夹具分别用自己的满联盟 `Y*` 与固定规则生成尺度。因此“同一评分规则”不等于“同一个参照向量”；concentrated 的两个空城市使其 `v_fid(N)=5/6`，dispersed 为1。结果没有跨夹具强行共用目标。

## 4. 自核一

1. **主保真度是否不同？** 是，联盟表、Shapley 向量和多重集均不同。
2. **gap 是否相同？** 是，逐联盟精确相同。
3. **哪些城市坐标导致？** 核心是 A2/B2 新激活的五类坐标；同时 entity-city 展开改变全国、省级 SUM 及若干来源分量。
4. **是否只是玩家重命名？** 否，排序后的 Shapley 多重集不同。
5. **新 G 捕捉到什么？** 城市分布、层级 SUM 重复及完整报表缺失/定义状态；旧省级 GC 不读取这些信息。
6. **是否足以解释旧状态差异？** 是。35坐标状态16→100、主 G 状态16→49，已经完整解释为何城市分散对完整产品有效、对省级 gap/GC 无效。

因此按预注册停止条件，不再重复计算 E1 第2、3组。

原始证据：`results/old_e1_value_metrics.csv`、`old_e1_coordinate_comparison.csv`、`equivalence_checks_experiment1.csv`、`old_e1_shapley.csv`。
