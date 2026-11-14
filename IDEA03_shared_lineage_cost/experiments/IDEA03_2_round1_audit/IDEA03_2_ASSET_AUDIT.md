# IDEA-03-2 第一轮：历史实验资产审计

审计日期：2026-11-13  
审计范围：`shapley-research-hub` 中与 IDEA-03、P3、D1-P、AB、H3、H5、M3 及作者算法复现有关的已归档材料；外部输入为 2026-11-07《研究进展和实验探索》PDF。  
本轮行为：只读核验和实验设计；未运行实验，未修改冻结代码、配置或结果，未提交 Git。

## 1. 证据口径

- `VERIFIED`：仓库内同时存在可对应的代码/配置与原始 CSV、JSON 或日志，关键状态可由这些文件直接核对。
- `REPORTED_ONLY`：只有汇报、报告或后续总结，仓库内缺少相应原始运行产物。
- `MISSING`：要求核对的代码、配置或运行产物在仓库中未找到。
- `ENV_BLOCKED`：代码或适配记录存在，但依赖、作者源码、服务或平台条件不完整，无法仅凭当前仓库复跑。

这里的 `VERIFIED` 表示“归档证据可相互对应”，不表示本轮重新运行复现。Git 提交也只是 2026-11 的迁移归档提交，不是历史实验发生时的原始提交。

## 2. Git 与外部材料边界

| 代号 | 归档提交 | 内容 | 边界 |
|---|---|---|---|
| C0 | `c37503bfbffb290b1f7e7603002e5cd6173621b6` | `research/IDEAS.md` 等迁移基线 | 不是旧实验的真实历史提交 |
| C1 | `4f13ab824141e244ff437583eedf35d0d060edc4` | IDEA-03 目录 | 仅说明迁入时间 |
| C2 | `1434a4705e6241f395b9c9b30207af74493a1170` | P3-0、P3-1B、P3-1C | 仅说明归档时间 |
| C3 | `6f9921919f48d4f5615db73d4d6140ff175d03d5` | D1-P、AB、H3、H5、BRBD 小型材料 | 外部作者源码、虚拟环境和大数据库未完整迁入 |

2026-11-07 汇报 PDF 不在仓库中。本轮从用户提供路径读取，SHA-256 为 `05619B62A36D96726394EEBBC7FEBB0D53D1720B75FB09D96D94B34352FF92E7`。PDF 第 21–23 页提出 A/B/C/D 四格计划和先基线、后算法判断的顺序；它是研究计划来源，不替代运行证据。PDF 中关于 M3 节点数、耗时等数字与第二轮原始核验冲突，故仍按 `REPORTED_ONLY` 处理。

## 3. 历史实验资产矩阵

下表中的路径均相对于仓库根目录。`联盟输出` 指完整联盟 SQL/价值表；`oracle` 指可核对的精确 Shapley 真值；`计时/内存` 指原始或汇总性能记录。

| 实验 | 玩家、schema 与 SQL 语义 | 报表/价值与目标 | 代码、配置与运行入口 | 原始证据 | 证据状态 | 对 IDEA-03-2 的可复用边界 |
|---|---|---|---|---|---|---|
| D1-P 设计修订（M3 身份） | 12 个 `logical_record_bundle`；4 个叶节点、7 个汇总节点；不是 E/B/H 物理事实 | 35 坐标；V0、V-count、V1、V2 设计 | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/config/d1p_design.yaml`；`config/protocol_v4_0.yaml`；`docs/experiment_log.md` | 配置明确 `design_only_not_implemented`，S2–S5 为 `NOT_RUN` | `VERIFIED`（仅设计状态）；运行结果 `MISSING` | 只能复用层次报表、价值版本和审计字段；不能把逻辑包直接当物理记录玩家 |
| D1-P S0/S1 精确真值 | 12 个逻辑记录包；SQL-P、SQL-U、共享状态三条路径 | 7 节点×5 指标；5 个价值版本；精确记录 Shapley | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/experiments/run_s0_s1_v4.py` | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/S1/verification_summary.json`；同目录 `run_s0_s1.log`；4096 联盟、24576 条加边/价值；三条路径一致 | `VERIFIED` | 可复用全联盟核验、独立 oracle、效率/边际检查框架；玩家语义与新游戏不同 |
| AB-N1/N2/J1/N3-L/N4-DP/J2 | D1-P 或独立 6 玩家控制；手工 SQL→grounding/source expression | COUNT/SUM、bag、DISTINCT、HAVING、线性坐标及比例坐标 | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/experiments/run_abramovich_native_sql_minimal.py`、同目录 `run_ab_n2_ab_j1_2026_10_31.py`、`run_ab_n3_l_n4_dp_2026_10_31.py`、`run_ab_j2_2026_10_31.py` | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/AB_N2_AB_J1_2026_10_31/manifest.json`、`validation.json`，以及同级 AB-J2、AB-N3/N4 目录 CSV/JSON；AB-N2 有 86016 联盟-组件核对；J2 为 64 联盟 | `VERIFIED`；仅当前 hub 独立复跑作者后端为 `ENV_BLOCKED` | 可复用手工 lineage/DNF 核验与成本分段；不是通用 SQL 编译器，联合整表价值未由作者算法直接支持 |
| H5-V2 联合状态 | 12 个 D1-P 逻辑玩家；玩家贡献可表示为固定 16 维增量 | 35 坐标，V2 非线性终端价值 | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/experiments/run_h5_v2_joint_state_2026_10_31.py` | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/H5_V2_JOINT_STATE_2026_10_31/summary.json`、同目录 `correctness_validation.csv`、`algorithm_costs.csv`；4096 联盟、3840 状态 | `VERIFIED` | 可复用终端价值、状态充分性和数值核验思路；不直接支持 JOIN 见证的合取激活 |
| H5-SCALE | 生成的可加增量状态游戏，N/结构变化 | V2 联合价值 | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/experiments/run_h5_scale_2026_11_01.py` | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/H5_SCALE_2026_11_01/summary.json`、同目录性能/状态增长 CSV；16 配置×5 实例 | `VERIFIED` | 可复用多实例、状态上限和失败记录方式；生成器不是 E/B/H 查询游戏 |
| H5-R | `StateGame` 要求联盟状态等于玩家固定 `delta` 之和；D1-P V1/V2 与 N12/N16 控制 | 任意 `value(state)`；S0–S6、前后缀、类型 VE、反向多线性 AD | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/src/aggregate_report_shapley/h5_shared.py`；`IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/experiments/run_h5_r_shared_all_players_2026_11_01.py` | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/H5_R_2026_11_01/summary.json`、同目录 `game_manifest.csv`、`raw_performance.csv`、`method_boundary_records.csv` | `VERIFIED` | 核心接口对“可加状态”通用；新 E/B/H JOIN 的见证需 E∧B∧H，不能用每玩家固定 delta 直接表达。可复用计时、缓存、Shapley 权重与验证外壳，求解器不能直接接入 |
| H3-JV | 12 个玩家；J0 单事实、J1 两表 JOIN 联集、J2 三表 JOIN；全 4096 联盟 DuckDB SQL | 7 节点×5 指标；G0 线性、G1 坐标可加、G2 家族联合几何价值 | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/experiments/run_h3_jv_2026_11_01.py` | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/H3_JV/summary.json`、同目录 `alliance_sql_report.csv`、`alliance_values.csv`、`exact_record_shapley.csv`、性能与状态 CSV；36864 次 SQL 联盟输出；每 JOIN 5 个复现实例 | `VERIFIED` | 已交叉检验 JOIN 结构×价值复杂度，是最接近的先例；但 J0/J1/J2 不是“同一 E/B/H schema 下跨地区复用低/高”的配对操纵 |
| H3-CONTROL | 一事实一玩家；H/NH 查询族×N=8/10/12×共享 low/medium/high，5 个结构实例 | BAG、DISTINCT、HAVING2/3；G1/G2 只在 N=12、高共享代表实例补测 | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/experiments/run_h3_control_2026_11_02.py` | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/H3_CONTROL/summary.json`、同目录 `structure_summary.csv`、`performance_summary.csv`、`joint_value_performance.csv` | `VERIFIED` | 已控制共享程度和查询结构；没有在 low/high 每格都配 additive/joint，因此未完成本轮四格 |
| P3-0 | 13 个物理事实玩家：4 Entity、6 Link、3 Attribute；两组 DISTINCT 查询 | G0=sum、G1=min；1000 收益池 | `IDEA02_exact_shapley_methods/materials/p3_0/run_p3_0.py`；`fixtures/anchor_13_players.json`；`queries/two_group_distinct.sql` | `results/P3_0_manifest.json`、`anchor_truth.csv`、`record_shapley.csv`；8192 联盟；SQL/Python/MTBDD 一致 | `VERIFIED` | 物理玩家、JOIN 来源和精确 oracle 可作实现模板；schema、指标、地区层次均与 E/B/H/D 不同，不能直接扩展而不建新 fixture |
| P3-1B | 同一 13 玩家；JOIN witness 最小获胜联盟 | H1/H2 阈值分解 | `IDEA02_exact_shapley_methods/materials/p3_1b/run_p3_1b.py` | `IDEA02_exact_shapley_methods/materials/p3_1b/results/P3_1B_manifest.json`、同目录 `minimal_winning_coalitions.csv`、`oracle_validation.csv`；H1=9、H2=4 | `VERIFIED` | 可复用 witness/DNF 正确性检查；是准备/验证任务，不是新整表联合价值算法 |
| P3-1C R1/R2/C2 | R1 作者算法原例；R2 同一 P3 H1/H2；C2 层次/DISTINCT SQL 语义 | R2 将 H1/H2 分别编译后组合；C2 为语义反例 | `IDEA02_exact_shapley_methods/materials/p3_1c/run_p3_1c.py`；同目录 `config/environment_manifest.json` | `IDEA02_exact_shapley_methods/materials/p3_1c/P3_1C_manifest.json`、同目录 R1/R2/C2 summary、SQL CSV、成本 CSV | R1/R2/C2 `VERIFIED`；Luo simple-game 与 ProvSQL `ENV_BLOCKED` | R2 证明作者 LExaShap 可在布尔阈值归约后同目标核对；不等于直接支持联合数值终端价值 |
| P3 原生 MTBDD | P3 13 玩家固定顺序 | G1 精确向量 | `IDEA02_exact_shapley_methods/materials/p3_0/src` 与 `IDEA02_exact_shapley_methods/materials/p3_0/run_p3_0.py` | `IDEA02_exact_shapley_methods/materials/p3_0/results/P3_0_manifest.json`；`IDEA02_exact_shapley_methods/materials/p3_1c/results/r2/r2_summary.json` 记录 367 非终端、9 终端节点 | `VERIFIED`（P3 固定目标） | 不是通用变量排序实验；不能回填为 M3，也未形成 E/B/H/D 适配器 |
| M3 变量排序/BDD 性能 | 报告声称 15/24/35 玩家结果，但无可对应的冻结输入 | 不可核实 | 未找到相应运行脚本、配置或专属目录 | 未找到节点数、排序、编译、求解的原始 CSV/JSON/log | `REPORTED_ONLY`；原始证据 `MISSING` | 不得作为已实现基线或性能先验 |
| 通用 d-DNNF 编译 | 目标应为任意 E/B/H lineage | 未冻结 | 仓库中未找到通用 d-DNNF 编译/求导入口 | 无同目标原始运行结果 | `MISSING` | 只能列为候选方法；作者实现核验前不能列作已实现基线 |
| 变量消去 | H5-R S5 是固定增量状态上的类型因子 VE；H3 使用 JOIN evidence state | D1-P/H3 既有目标 | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/src/aggregate_report_shapley/h5_shared.py`、`IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/experiments/run_h3_jv_2026_11_01.py` | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/H5_R_2026_11_01/performance_summary.csv` 与 `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/H3_JV/algorithm_performance_summary.csv` | 既有目标 `VERIFIED`；新游戏适配 `MISSING` | 可复用状态/因子接口概念；新 E/B/H lineage 的因子化与顺序尚未实现 |
| Luo 独立效用 | 官方 world 已跨平台复现；D1-P V-count 与 H3-J2 加性子游戏有适配 | 独立输出效用；不直接覆盖 V1/V2 联合价值 | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/experiments/run_r1_luo_d1p_v4.py`；`IDEA02_exact_shapley_methods/materials/brbd/scripts` | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/R0/luo_official_reproduction_windows_gnu.json`、`IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/R1/luo_d1p_adaptation.json`；`IDEA02_exact_shapley_methods/materials/brbd/protocol/stage_status.json` | 已归档运行 `VERIFIED`；当前 hub 缺作者 checkout/数据，重跑 `ENV_BLOCKED` | 只能在证明相同玩家与相同 v(S) 的可加子目标上进入基线；联合价值不能直接套用 |
| Abramovich/LExaShap | Boolean DNF/d-tree 后端，手工 grounding 前端 | 线性组合或布尔阈值归约 | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/experiments/run_abramovich_native_sql_minimal.py`、`IDEA02_exact_shapley_methods/materials/p3_1c/run_p3_1c.py`、`IDEA02_exact_shapley_methods/materials/brbd/scripts/run_abramovich_academic_r1.py` | AB/P3 manifests 与结果；`IDEA02_exact_shapley_methods/materials/brbd/protocol/stage_status.json` | 小型同目标适配 `VERIFIED`；完整外部源码未迁入，重跑 `ENV_BLOCKED` | 适合布尔/线性分量；新整表联合 G 是否可精确归约必须逐式证明 |
| Faithful GSV/FGSV | 所有者/组贡献近似；D1-P 和 SOU 固定游戏，多预算多种子 | 近似组值，不是本轮物理记录精确基线 | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/experiments/run_fgsv_r2_3.py`、同目录 `run_fgsv_r2_4.py`、`run_fgsv_r2_5.py` | `IDEA02_exact_shapley_methods/materials/aggregate_report_shapley/outputs/v4_0/R2_3`、`R2_4`、`R2_5` 的 raw/summary/audit；R2-4 公式消融、R2-5 误差与成本 | `VERIFIED`（既有近似实验） | 玩家层级、估计目标和精确算法不同；只能作为明确标注的近似/组值对照，不能替代记录级 exact oracle |

## 4. 研究目标一致性结论

### 4.1 D1-P 不能直接充当本轮玩家游戏

D1-P 的活动玩家是 `logical_record_bundle`，每个包在现有实现中被压成固定的报告状态增量。本轮要求 E、B、H 的每条物理事实独立加入或退出，查询见证需同时满足 E、B、H 三条事实存在。两者的联盟空间、dummy/symmetry 关系和边际贡献均不同。因此不能转换标签后复用 D1-P 数据；可复用的仅是全国—中层—叶层报表骨架、坐标价值函数、全联盟核验和结果格式。

### 4.2 P3 可提供模板，但不能直接扩表

P3-0 已冻结 13 个物理玩家和 JOIN 来源，证明了“物理事实→联盟 SQL→精确 oracle→MTBDD/作者算法核对”的完整小规模链路。不过其 Entity/Link/Attribute 与两组 DISTINCT 语义不等于 E/B/H/D 企业报表。新实验应新建独立 fixture 和 manifest；P3 冻结对象保持不变。

### 4.3 H5-R 不是新 `(N,Q,G)` 的即插即用求解器

`StateGame` 支持任意终端 `value(state)`，但要求 `state(S)=Σ_{i∈S} delta_i`。E/B/H 查询的一个见证只有在三类事实共同出现时才激活，通常不存在与联盟无关的单玩家固定 `delta_i`。H3-JV 通过“见证就绪状态”补足了这一点，但该构造是特定 lineage 的状态化，不是 H5-R 现成入口。可以复用 S0–S6 的权重、缓存、计时与验证框架；必须先为新 lineage 构建并证明充分的状态适配器。

### 4.4 M3 仍是设计阶段

`docs/experiment_log.md`、`d1p_design.yaml` 和第二轮核验一致表明 M3 是设计修订，未执行 BDD/变量排序性能实验。本轮再次未发现独立 M3 原始产物。P3 的 367/9 节点 MTBDD 结果属于 P3，不属于 M3。

### 4.5 原有精确算法对非可加整表价值的支持边界

- 全联盟子集公式与 H3 的 JOIN evidence-state 方法对已冻结小规模游戏可直接得到 exact oracle。
- Abramovich/LExaShap 已验证的是 Boolean DNF/阈值或可线性组合分量；对任意联合数值 G 没有直接接口证据。
- Luo 独立效用对加性输出归约有证据；对跨坐标联合价值假设不满足。
- H5-R 可处理“可加状态 + 非线性终端 G”，但新 JOIN 查询不满足现成的可加状态前提。
- 通用 d-DNNF、新游戏 MTBDD、通用变量消去均没有已核验实现。

### 4.6 是否已经做过“跨地区重复 × 非可加价值”联合检验

没有。H3-JV 已完整交叉 JOIN 结构 J0/J1/J2 与 G0/G1/G2；H3-CONTROL 已交叉结构族、共享 low/medium/high 与 N，但 G1/G2 只在 N=12、高共享代表实例上运行。两者都没有在固定 E/B/H/D schema、固定物理玩家数和固定地区边际下，以低/高跨地区企业复用配对四格。新实验的合理定位是对这一特定缺口的受控确认，不是从未研究过 JOIN 或联合价值。

## 5. 依赖与可复现性边界

历史 manifests 一致记录的主要环境是 Windows、Python 3.11.6、DuckDB 1.5.6；部分 FGSV 分析还记录 NumPy 2.4.6、pandas 3.1.0、SciPy 1.17.1。仓库没有一个可覆盖全部实验的统一锁文件，BRBD 只保留环境说明。作者源码 checkout、Cargo vendor、ProvSQL、虚拟环境和大型原始数据库未完整迁入。因此：

- 归档结果本身可审计；
- 纯 Python/DuckDB 自有代码预计可在重建环境后复跑，但本轮未验证；
- Abramovich/Luo/ProvSQL 的某些路径仅凭 hub 不能复跑，应标 `ENV_BLOCKED`；
- 不得用旧机器上的绝对耗时直接宣布算法优劣或创新缺口。

## 6. 本轮关键判断

1. 可以在不改动冻结对象的前提下，新建独立 E/B/H/D fixture。
2. 本轮最可靠的真值方案仍是小 N 全联盟 DuckDB SQL + 独立 Python lineage evaluator + 精确子集 Shapley 三方核对。
3. 当前没有一个作者算法已经对新游戏达到“相同玩家、相同 Q、相同 G、端到端可运行”的基线资格。
4. H3-JV/H3-CONTROL 显著缩小了研究缺口；新四格实验首先是研究目标一致性和结构效应确认，不应预设会产生新算法问题。
5. M3 报告数字、通用 d-DNNF 和新游戏变量排序均缺原始证据，不能进入已实现列表。
