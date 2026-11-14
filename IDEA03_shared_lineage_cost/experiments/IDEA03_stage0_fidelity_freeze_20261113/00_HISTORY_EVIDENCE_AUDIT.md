# IDEA-03 阶段0：历史证据回溯

日期：2026-11-13  
阶段状态：`STAGE0_COMPLETED`  
审计边界：只读核对历史档案，并为新价值函数做 N=12 的数学核验；没有重跑历史完整实验，没有进入阶段1。

## 1. 证据标签

- `VERIFIED`：代码、配置与原始结果可以对应，或存在精确数学证明并有运行记录。
- `LOCAL_OBSERVATION`：在冻结夹具上观察成立，不能外推为一般结论。
- `MATHEMATICAL_CONJECTURE`：有结构解释，但尚无完整证明或区分性实验。
- `INCOMPLETE`：缺实现、缺同目标适配、缺原文核验或缺可复现实验。
- `RESOURCE_LIMIT`：实际运行受资源/预算停止；不等价于问题本身困难。

## 2. 指定历史命题核验

| 命题 | 结论 | 标签 | 原始证据 |
|---|---|---|---|
| 历史 G1 与 GR 在 `k=1` 下恒等 | 五个冻结 F0/F1/F2 游戏的全部联盟均无反例。原因是 `r=M/W>0` 必有制造业 JOIN 见证，从而企业数门槛 `C>=1` 自动满足；`r=0` 时门控前后均为0。 | `VERIFIED`，限冻结语义 | `IDEA03_2_shared_compilation_tpch_v1/runs/SHARED_20261113_181356/raw/historical_g1_redundancy.csv`；`src/study.py:177-195` |
| `k=2` 的 E0 GC | `E0_F0_K2_N12` 的 4096 个联盟中 GC 仅满联盟非零，是 unanimity game；GR/GL 非零联盟分别为960/127，故新夹具本身并未整体退化。 | `VERIFIED` | `.../SHARED_20261113_181356/raw/e0_value_metrics.csv`、`e0_threshold_examples.csv`、`e0_sql_validation.csv` |
| F0/F1/F2 联合状态与 Harsanyi 规模 | 五个游戏的六维联合统计状态数均为16；G2 的非零 Harsanyi 项分别为 F0=8、F1-balanced=48、F1-concentrated=44、F2-balanced=72、F2-concentrated=56。联合统计状态不变不意味着来源表示不变。 | `VERIFIED`；规模差异仅是这些夹具的局部观察 | `IDEA03_2_joint_value_deepening_v1/runs/DEEP_20261113_155744/raw/joint_state_counts.csv`、`component_metrics.csv` |
| 同省集中/分散为何没有改变省级 GC 来源表示 | E1 的重连仅在各省内部把同一实体的 R2 链接分配到一个或两个城市；省级对城市做 OR 后，实体—省资格 DNF 不变。因此两类游戏的 Harsanyi=392、总 DNF 子句=108、唯一子句=63、共享子表达式=45 完全相同；变化只出现在城市分辨率，使联合状态16变49。该操纵没有形成跨省共同来源。 | `VERIFIED`，并说明原控制变量不足 | `.../SHARED_20261113_175706/raw/e1_fixture_configs.csv`、`e1_structure_metrics.csv`；`src/study.py:71-108` |
| 共享 ROADD 精确性 | Reduced ADD 的基数条件 DP 在 E0 与第一组 E1 集中/分散夹具上逐玩家等于 oracle，最大误差为0。 | `VERIFIED`，但不是可扩展来源编译器 | `.../SHARED_20261113_180500/raw/e2_exact_solver_comparison.csv`、`src/study.py:367-452` |
| 共享 ROADD 的限制 | 当前编译从完整 `2^N` 真值表递归建立 ADD；它可以验证共享表示与求解公式，却不能作为阶段1“不枚举联盟”的结构化基线。 | `VERIFIED` 的实现边界 | `IDEA03_2_shared_compilation_tpch_v1/05_EXACT_SOLVER_COMPARISON.md`；`src/study.py` 的 `ReducedADD.from_values` 路径 |
| 官方 LExaShap 适配与缓存 | 历史 GR/GL/GC 已拆成 Boolean 分量调用官方实现；B1 每分量编译，B3 仅对完全相同的 canonical DNF 做精确缓存。两者最大误差 `2.78e-17`。B3 的 warm reuse 不能当成冷启动重复实验。 | `VERIFIED`，只覆盖历史分量；新保真度尚未适配 | `.../SHARED_20261113_180500/raw/e2_exact_solver_comparison.csv`；`04_SHARED_COMPILATION_ANALYSIS.md`、`05_EXACT_SOLVER_COMPARISON.md` |
| TPC-H SF0.1 跨地区供应商共享 | 自然 N=16 样本有4个 supplier、共享证明对0；压力夹具 N=13 固定 supplier 74，1个 supplier 跨4个国家/2个地区，4个 line witness 产生6个共享证明对。它证明真实数据中可构造该结构，不证明成本交互。 | `VERIFIED` 的结构存在性；成本效应 `INCOMPLETE` | `.../SHARED_20261113_181253/raw/tpch_games.csv`、`tpch_source_rows.csv`、`tpch_structure_metrics.csv` |
| canonical 与资源停止记录 | E0/E1/E2/TPC-H 分阶段 canonical 分别为 `181356/175706/180500/181253`。`164908` 是 wrapper 中断后的非原子残留；`175906` 是全六夹具重复重编译超出预算。二者均未被成功运行覆盖。 | `VERIFIED` | `IDEA03_2_shared_compilation_tpch_v1/CANONICAL_STAGE_MAP.json`、`RUN_REGISTRY.md`、两个 `ABORTED_RESOURCE.json` |

## 3. 其他关键历史边界

### D1-P 与 H5/H5-R

D1-P 的12名玩家是逻辑 `record_id` 包；一个玩家可同时绑定基础表和可选属性行。H5/H5-R 沿用该玩家与16维叶级充分状态，证明了 B2/B3/S0--S6 在冻结 D1-P V1/V2 上的正确性。它们没有自动覆盖 E/B/H 每条物理事实独立参与的 JOIN 游戏。

证据：

- `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/docs/model_spec_d1p.md`
- `.../docs/H5_V2数学结构与充分性证明.md`
- `.../docs/H5_R_共享经典精确算法正确性说明.md`
- `.../outputs/v4_0/H5_R_2026_11_01/summary.json`

档案冲突：`config/d1p_design.yaml` 与早期模型说明仍写有 `design_only_not_implemented`，但后续代码、测试、4096 联盟结果和 R2 exact targets 均存在。这是陈旧状态字段，不应据此否定后续已执行证据，也不能静默修改历史文件。

### P3

P3 是13个物理事实玩家（4 Entity、6 Link、3 Attribute），输出两个分组的 `COUNT DISTINCT`，并非7节点35坐标报表。原生 MTBDD 及 P3-1C 的 Abramovich/LExaShap H1/H2 适配均已通过同目标 oracle；它可以作为 Boolean DISTINCT 来源的算法证据，不能直接替代冻结保真度游戏。

证据：`p3_0/fixtures/anchor_13_players.json`、`p3_0/results/P3_0_manifest.json`、`p3_1c/results/r2/r2_summary.json`。

### H3-JV

H3-JV 的 p9--p12 是“每两条物理 relation edge 绑定成一个逻辑玩家”的记录包。J0/J1/J2 共9个 `(Q,G)` 单元、36,864 次 SQL 联盟求值均通过，但其玩家绑定也不同于 E/B/H 物理事实游戏。历史 `n=16` 扩展明确为用户暂停，没有执行。

证据：`aggregate_report_shapley/docs/H3_JV_数据模型与玩家映射.md`、`outputs/v4_0/H3_JV/summary.json`。

## 4. 仍未完成的事项

1. F1/F2 的65个边界/抽样 SQL 校验不是全联盟 SQL 穷举；不能写成与 E0 同等级的完整 SQL oracle。
2. 同省集中/分散不是跨省共享的合格反事实；它只能说明城市细分状态可能增加而省级来源表达不变。
3. TPC-H 压力夹具没有与低共享样本做保持其他因素不变的配对成本实验。
4. LMFAO 在本地只有类别性引用，没有保存原文精读、实现适配或同目标结果；本轮按 `CURRENT_EVIDENCE_INSUFFICIENT` 处理。
5. 共享 ROADD 的精确性已证实，但“从 SQL lineage 直接编译而不读真值表”尚未实现。

## 5. 阶段0判断

历史证据支持把后续问题从“价值函数是否更难”转向来源表示和多分量复用；不支持把某次 `RESOURCE_LIMIT`、真值表 ROADD 或陈旧程序的慢速直接解释为新复杂性下界。
