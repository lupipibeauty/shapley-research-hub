# IDEA-03-2 联合结构实验设计 V1

状态：`DESIGN_ONLY_NOT_EXECUTED`  
日期：2026-11-13  
目标：在固定的 E/B/H/D 物理事实游戏中，受控检验“跨地区来源复用”与“整表价值联合性”对记录级 Shapley 分配、表示规模和端到端成本的影响。本文档不是新算法设计，也不把实验用数值函数解释为新的经济价值理论。

## 1. 研究问题与可证伪假设

### RQ1：分配效应

在玩家数、各表行数、每个企业的场所度数、地区/行业边际和满联盟总量尽量配对时，将企业记录从单地区使用重连为跨地区复用，是否系统性改变 E/B/H 三类玩家的归一化 Shapley 份额？

### RQ2：价值交互

整表坐标可加价值与跨坐标联合价值是否会改变上述共享效应？主要交互量为

\[
\Delta_{\mathrm{int}}(T)
=\bigl[T(H,J)-T(L,J)\bigr]
-\bigl[T(H,A)-T(L,A)\bigr],
\]

其中 `L/H` 是低/高跨地区复用，`A/J` 是坐标可加/联合价值，`T` 可取玩家份额差异、关系层份额、状态数、节点数、时间或内存。

### RQ3：计算效应

在同一玩家、同一 Q、同一 G 下，共享结构和价值联合性是否改变现有精确表示/求解方法的状态数、编译成本和求解成本？这里不预设所有方法必然指数复杂，也不以旧实现慢速作为创新证据。

零假设是四格差异仅为数值噪声或由未控制边际造成。若配对后 `Δ_int` 不稳定，或成熟基线已直接覆盖该对象，则该方向不形成新的算法问题。

## 2. 冻结数据对象

### 2.1 schema

```text
E(eid, size)
B(sid, eid, city, industry)
H(sid, year, workers)
D(city, province)
```

- `E`、`B`、`H` 的每一条物理记录分别是一个玩家。
- `D` 是固定外生维表，不参与分配。
- V1 固定一个统计年度 `year = y0`，每个 `sid` 在该年最多一条 H；多年度作为后续维度扩展，不进入首轮四格。
- 不把 E、B、H 的相关记录绑定成一个玩家。玩家映射由 fixture manifest 明示，不能根据外键关系推定。

### 2.2 联盟数据库与见证

令 `N=N_E∪N_B∪N_H`。联盟 `S⊆N` 对应 `E_S`、`B_S`、`H_S`，D 始终完整。基础见证关系为

\[
W_S=E_S\Join_{E.eid=B.eid}B_S
\Join_{B.sid=H.sid\land H.year=y_0}H_S
\Join_{B.city=D.city}D.
\]

因此一个见证至少需要一条 E、一条 B 和一条 H 同时在联盟中。该合取语义是本游戏与 D1-P 固定增量游戏的关键差别。

### 2.3 固定完整报表

地理坐标集合

\[
\mathcal G=\{\text{NAT}\}\cup\mathcal P\cup\mathcal C
\]

在全国、省、市三个层级固定输出以下五项：

1. `enterprise_count = COUNT(DISTINCT eid)`；
2. `site_count = COUNT(DISTINCT sid)`；
3. `workers = SUM(workers)`；
4. `mfg_workers = SUM(workers) FILTER (industry='manufacturing')`；
5. `mfg_share = mfg_workers / workers`。

固定地理骨架由 D 产生，所有联盟都输出同一坐标集合；空组计数和求和填 0。`workers=0` 时 `mfg_share=0`。首轮使用全 JOIN 报表：企业数和场所数也要求相应 H 事实存在，避免不同指标采用不同玩家可见性规则。若研究者希望企业/场所数不依赖 H，必须另建查询版本，不能静默改 SQL。

记完整向量为 `Y(S)=(y_{g,m}(S))`。必须保存 SQL 文本、schema、排序规则、空值政策和 DuckDB 版本。

## 3. 价值函数

### 3.1 坐标得分标准化

对四个计数/求和指标，定义

\[
z_{g,m}(S)=\min\{y_{g,m}(S)/y_{g,m}(N),1\},
\]

满联盟分母为 0 的坐标在 fixture 生成阶段禁止出现。比例坐标不直接按比值除以满联盟比例，而定义

\[
z_{g,r}(S)=z_{g,\mathrm{workers}}(S)
\max\{0,1-|r_g(S)-r_g(N)|\},
\]

使空联盟得分为 0，并同时反映覆盖与比例接近程度。这只是受控实验效用，不作市场成交价值或通用商业价值解释。

### 3.2 A：坐标可加价值

\[
G_A(Y)=R\sum_{g\in\mathcal G}\eta_g
\sum_{m\in\mathcal M}w_m z_{g,m},
\qquad \sum_g\eta_g=\sum_mw_m=1.
\]

默认 `R=1000`；层级总权重按 NAT/省/市各 `1/3` 后在同层坐标等分；五指标等权作为首轮默认，同时保存可替换权重配置。这里“可加”只指坐标得分相加；由于 JOIN 和 DISTINCT，`v(S)` 并不是玩家可加游戏。

### 3.3 J：跨坐标联合价值

为隔离交互而保留与 A 相同的主效应尺度：

\[
J(Y)=\sum_g\eta_g\left[
0.4z_{g,e}z_{g,s}
+0.4z_{g,w}z_{g,mw}
+0.2z_{g,r}
\right],
\]

\[
G_J(Y)=R\bigl[(1-\lambda)A(Y)+\lambda J(Y)\bigr],
\quad A(Y)=G_A(Y)/R.
\]

首轮固定 `λ=0.5`，并验证 `λ=0` 与 `G_A` 在所有联盟上完全一致。A/J 均满足空联盟为 0、满联盟为 R。J 的乘积项是明确的实验性交互，不被表述为新的经济理论。

特征函数统一为

\[
v_X(S)=G_X(Y(S))-G_X(Y(\varnothing)),\quad X\in\{A,J\}.
\]

## 4. 2×2 主实验

### 4.1 结构因子：低/高跨地区复用

以同一组 E、B、H、D 行为基础，仅通过保持度数的 `B.eid` 重连产生配对 fixture：

- `L`：每个 `eid` 的所有 B 行位于同一城市（至少同一省），跨省企业比例为 0；
- `H`：在保持每个 eid 的 B 度数、每城市 B 数、行业边际、每个 sid 的 H 行和 workers 不变时，使预设比例（建议至少 50%）的多场所企业跨越两个及以上省份。

采用二部图 2-switch/边交换生成 H，并保存变换日志。不得改变 E/B/H 行数、玩家 ID、每个企业的场所度、每个城市的场所数、行业计数和 H 数值；若无法同时保持，则降低 fixture 或明确记录偏差。

结构操纵量至少包括：

- `cross_city_eid_rate`、`cross_province_eid_rate`；
- 每个 E 玩家参与的 witness 数及其地区熵；
- witness 对之间共享 E 玩家的比例；
- lineage AND/OR 节点数、变量出现次数和超图度数。

### 4.2 四个实验单元

| 单元 | 结构 | 价值 | 保持不变 |
|---|---|---|---|
| A | L | `G_A` | 玩家、行数、度数、地区/行业边际、R、权重 |
| B | H | `G_A` | 同上，仅 `B.eid` 配对重连 |
| C | L | `G_J` | 与 A 同一 fixture，仅 G 改变 |
| D | H | `G_J` | 与 B 同一 fixture，仅 G 改变 |

每个随机基础实例生成一组 A/B/C/D，共用 `pair_id`。分析单位是独立的基础实例，不是同一实例上的三次计时。

### 4.3 首轮规模

- 语义 smoke：`N=9`（每表 3 玩家或保证至少两个地区），1 个 pair。
- 正确性 pilot：`N=12`，3 个独立 pair，四格全联盟 `4×4096`。
- 主确认：`N=16`，建议 5 个独立 pair，四格全联盟 `5×4×65536=1,310,720` 个联盟值。
- `N=18` 只在 N=16 正确性和资源门通过后作为精确扩展；每个 pair 四格为 1,048,576 个联盟值。
- `N≥20` 不默认做全联盟 SQL；只对已经通过同目标核验的方法做资源受限扩展，并保留删失/失败记录。

## 5. 基线资格与方法矩阵

| 方法 | 当前实现证据 | 新游戏首轮资格 | 必须新增 | 接受条件 |
|---|---|---|---|---|
| B0 全联盟 DuckDB + 子集公式 | 历史多次 `VERIFIED` | 必选 exact oracle | 新 schema、联盟 SQL、批处理与结果格式 | SQL/Python lineage 所有坐标一致；效率误差 ≤ `1e-10` |
| B0b 完整排列枚举 | 历史有实现思路 | 仅 N≤10 独立核对 | 新游戏 evaluator | 与子集公式逐玩家一致 |
| H3 JOIN evidence-state DP | H3-JV/H3-CONTROL `VERIFIED` | 条件性精确基线 | E/B/H witness state 与 report decoder | 所有联盟 state→Y 唯一；Shapley 对 B0 ≤ `1e-10` |
| H5-R S4/S5/S6 | 可加状态游戏 `VERIFIED` | 非直接资格 | 只能在上述 H3 state 适配通过后调用共享求解外壳 | 不把旧 fixed-delta 路径冒充 JOIN 支持；同目标全联盟核对通过 |
| P3 原生 MTBDD | P3 固定目标 `VERIFIED` | 候选，不是已实现新基线 | 新 lineage/多终端编译器与变量顺序 manifest | 输入不使用 oracle；小 N 全联盟值与 Shapley 一致 |
| Abramovich/LExaShap | Boolean/线性分量 `VERIFIED`，当前环境部分阻塞 | A 的可归约分量候选；J 默认不适用 | 手工或验证过的 SQL→DNF；联合 G 的精确归约证明 | 相同 v(S)，计入 source/compile/solve；否则标 `INPUT_UNSUPPORTED` |
| Luo 独立效用 | world/D1-P V-count/H3 加性归约有证据 | A 的独立输出子目标候选；J 不适用 | E/B/H 同游戏适配、作者环境 | 所有联盟等价或严格定理归约；否则不计性能 |
| 通用 d-DNNF | `MISSING` | 不进入 V1 已实现基线 | 作者实现、版本、编译与求导适配 | 完成作者实现核验后另行审批 |
| 通用变量消去 | 只有 H5/H3 特定状态版本 | 候选 | 新 lineage 因子、顺序、宽度和 exact 输出 | 小 N exact；原始顺序/节点/内存日志完整 |
| Faithful GSV/MC | 近似实验 `VERIFIED` | 可作为明确标注的近似对照 | 记录级玩家接口、预算对齐 | 与 exact oracle 报误差/预算，不与 exact 方法混排 |

不得把理论论文中的算法直接列为“已实现”。不得把 `ENV_BLOCKED` 当性能失败。

## 6. 输出指标

### 6.1 正确性

- `max_abs_report_error`：SQL 与独立 lineage 的所有联盟、所有坐标最大误差；
- `max_abs_shapley_error`；
- 效率误差 `|Σ_i φ_i-[v(N)-v(∅)]|`；
- dummy、对称玩家、线性（仅对 G_A 分量）的构造测试；
- A 与 J 在 `λ=0` 的退化一致性；
- 空联盟、满联盟、缺 E/B/H 任一类、零分母测试。

Softmax 或其他归一化与本 exact 实验无关；不从预算守恒推导全部 Shapley 公理。

### 6.2 分配结构

- 归一化份额 `s_i=φ_i/[v(N)-v(∅)]`；
- 四格玩家份额的配对 L1、最大差和 Spearman 排名变化；
- E/B/H 三类份额总和与组内 Gini；
- 多地区 E 玩家相对单地区 E 玩家的份额差；
- 按 witness 度、地区熵分层的份额曲线；
- `Δ_int` 的实例分布和配对 bootstrap 区间（实例数足够时）。

### 6.3 计算结构与成本

- witness、DNF clause、变量出现、lineage 节点、MTBDD/d-DNNF/VE 状态或节点数（仅适用方法）；
- `T_source`、`T_transform`、`T_compile`、`T_solve`、`T_total`；
- SQL 全联盟时间、算法时间、每玩家查询时间；
- 进程峰值 RSS 与 Python peak 分开记录；
- 缓存命中、状态转移、最大 frontier、失败原因和停止位置。

绝对耗时只在同机、同环境、同输入和同计时口径下比较。

## 7. 扩展实验可行性

| 扩展因子 | 建议水平 | 可复用资产 | 新增模块 | 主要瓶颈 | 独立正确性验证 |
|---|---|---|---|---|---|
| 玩家规模 N | 9/12/16/18；20+ 资源受限 | P3/S1 全联盟、H5-SCALE 门控 | 配比生成器、批处理 oracle | `2^N` 联盟、SQL 输出量 | N≤16 全联盟；更大 N 用嵌套小实例和随机联盟，不宣称 exact 全覆盖 |
| 统计维度 | 城市数 2/4/8；指标固定 5 | D1-P/H3 报表向量 | D skeleton 与坐标 manifest | 坐标×状态维数 | 每层汇总等于叶层重算；固定输出行数 |
| 来源共享 | low/medium/high | H3-CONTROL 生成/指标 | E-B 度数保持重连 | 高共享可能改变可达状态方向不单调 | 配对边际、重连日志、结构指标 |
| 联合价值复杂度 | `λ=0,.25,.5,.75`；主实验 0/.5 | D1-P V1/V2、H3 G1/G2 | 价值配置与符号审计 | 数值终端数、方法适用性缩小 | λ=0 退化；空/满值；高精度重算 |
| 年度维度 | 1/2/4 年，后续 | 无直接同目标 | H 多行、时间坐标 | 玩家和坐标同时增长，混杂首轮 | 先固定 N 做年度配对；不与首轮合并 |

## 8. 正确性门与停止条件

### Gate 0：冻结

schema、玩家映射、SQL、A/J 公式、权重、λ、随机种子和配对生成规则全部 hash。任何一项变化均生成新版本，不覆盖 V1。

### Gate 1：语义

N=9/12 的所有联盟必须满足 SQL 与独立 lineage evaluator 完全一致；发现一处玩家绑定、空组、DISTINCT 或比例语义不一致即停止。

### Gate 2：oracle

子集 Shapley、完整排列小样本、效率和构造型 dummy/symmetry 检查通过。算法不得读取 exact Shapley 或完整联盟表来构建输入，除非明确作为 lookup 基线。

### Gate 3：同目标基线

每种算法必须证明相同 `N,Q,G`。接口不支持记 `INPUT_UNSUPPORTED`；缺依赖记 `ENV_BLOCKED`；超资源记 `RESOURCE_LIMIT`。三者都不是算法错误。

### Gate 4：资源

建议首轮单任务上限：15 分钟/8 GiB（smoke/pilot），主确认单任务 60 分钟/16 GiB；状态 cap 从历史 5k/25k 起逐级记录，未经审批不无限提高。达到上限即保存已完成阶段并停止该单元。

### Gate 5：研究判断

若四格配对效应不稳定、被混杂解释，或成熟同目标方法已完整覆盖，则记录否定结论，不启动新算法。只有正确性、同目标和成本口径全部通过，且存在可重复的结构瓶颈，才进入后续算法研究审批。

## 9. 独立目录建议

后续经批准后，新资产建议建立在：

```text
IDEA03_shared_lineage_cost/experiments/IDEA03_2_joint_structure/
├─ README.md
├─ configs/
├─ fixtures/ebhd_v1/
├─ sql/
├─ src/
├─ scripts/
├─ tests/
└─ runs/                 # 大型逐联盟数据不进入 Git，只保存 manifest/summary/hash
```

不得修改 P3、D1-P、H3、H5 的冻结目录。V1 设计完成不表示实验已执行。
