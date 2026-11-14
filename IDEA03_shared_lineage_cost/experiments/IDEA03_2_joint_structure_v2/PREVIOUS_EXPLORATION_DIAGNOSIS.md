# 前期探索未发现稳定算法瓶颈的原因诊断

## Material Passport

- `artifact_id`: IDEA03-2-PREVIOUS-EXPLORATION-DIAGNOSIS-V1
- `artifact_type`: 理论结构诊断、判别性实验与成熟精确基线复现
- `status`: VERIFIED
- `date`: 2026-11-13
- `canonical_run`: `runs/DIAG_20261113_130136/`
- `scope`: 冻结 E/B/H/D 物理玩家游戏；不修改 E0/E1/E2 历史结果
- `methods`: SPARSE_HARSANYI_PROVENANCE；OFFICIAL_LEXASHAP_BOOLEAN_COMPONENTS；H3-S6 code-path diagnosis

## 1. 结论先行

此前没有观察到稳定的“跨地区共同来源 × 非可加价值”额外成本，不能只归因于样本少。五类原因中，有四类同时成立：

1. **游戏本身容易分解：已证实，是首要原因。** E/B/H witness 超图按企业分成互不相交的分量；incidence treewidth 恒为1，primal treewidth 恒为2。玩家数从10增加到64时，这两个宽度都没有增长。
2. **生成器没有形成更复杂的基础来源图：已证实。** Low/High 保持企业度数，只改变 B.eid 与地区的对应。无标签来源图宽度、企业分量数和度数签名不变；它把省内替代证明复杂度转移成跨省同企业项，而不是增加总的度数控制复杂度。
3. **价值函数过于容易分解：已证实。** 35个报表坐标中，G 只读取2个。两个 COUNT DISTINCT 的乘积可展开为企业指标两两乘积的有限线性和，并由官方 LExaShap 的 Boolean DNF 分量或稀疏 Harsanyi 项精确计算。
4. **H3-S6 的表示方式掩盖了因素：已证实。** 它在应用 G 之前就构造所有 witness evidence-count 状态，并把本来独立的企业分量做全局笛卡尔积。Add/Joint 因而共享同一个状态图；N=24 的414,736个状态不是联合价值造成的。
5. **统计证据不足：成立，但属于次要解释。** E1 每格一次计时、只有3个独立 fixture，确实不足以判断秒级差异；但更多同类 seed 不能改变前四项结构事实，也不能使原操纵突然变成正交设计。

因此，原 RQ3 的正命题目前不应继续通过机械扩大四组实验来追索。更值得研究的是：**来源分量结构、区域证明分配、价值交互图和知识表示之间的参数化复杂度与算法优势转换。**

## 2. 实际执行范围

诊断运行覆盖9个配对规模、18个 fixture：N=10、16、三个 N=20、N=24、32、40、64。共完成：

- 72个价值表达重建检查，全部 `VERIFIED`；
- 144个精确基线单元，全部 `VERIFIED`；
- N≤20 与冻结全联盟 oracle 对照；
- N>20 使用随机联盟、空/满/单玩家联盟、效率性和两个独立精确方法互检；
- H3-S6 在 N=20、24 的逐层 evidence-state 构成检查；
- 6个用于分离结构参数的数学微型对照。

两种不同精确计算思路在所有 N=10–64 fixture 上的最大相互差异不超过 `9.95e-14`；N≤20 相对冻结 oracle 的最大误差不超过 `5.69e-14`。

## 3. 基础来源表达式为什么容易分解

### 3.1 witness 和企业指标

对场所 s，令 e(s) 为其企业，基础 JOIN witness 为

\[
x_s(S)=\mathbf 1\{E_{e(s)},B_s,H_s\in S\}.
\]

企业 e 在地区 r 出现的 DISTINCT 指标为

\[
I_{e,r}(S)
=\mathbf 1\{E_e\in S\}
\left[1-\prod_{s\in\mathcal S_{e,r}}
\left(1-\mathbf 1\{B_s,H_s\in S\}\right)\right].
\]

因此：

\[
C_r(S)=\sum_e I_{e,r}(S),
\]

而场所数、就业人数和制造业就业人数分别是

\[
N_r(S)=\sum_{s\in r}x_s(S),\qquad
W_r(S)=\sum_{s\in r}w_sx_s(S),\qquad
M_r(S)=\sum_{s\in r,\,ind(s)=mfg}w_sx_s(S).
\]

除 COUNT DISTINCT 外，三个指标已经是 witness 单项式的线性和。COUNT DISTINCT 也只在单个企业分量内部形成 OR。

### 3.2 超图分解和宽度

每个超边为 \(\{E_e,B_s,H_s\}\)。B_s 和 H_s 只出现在一个 witness 中，不同企业没有共享玩家。因此：

- 每个企业形成一个独立的3-均匀超边星形分量；
- incidence 图每个分量都是树，精确 treewidth 为1；
- primal 图是多个三角形只在 E_e 上做 clique-sum，精确 treewidth 为2；
- 当前所有 N=10–64 fixture 均满足上述结论。

实际度数签名为：

| N | 企业度数签名 | 最大度数 | incidence tw | primal tw |
|---:|---|---:|---:|---:|
| 10 | 2,2 | 2 | 1 | 2 |
| 16 | 1,1,2,2 | 2 | 1 | 2 |
| 20 | 2,2,2,2 | 2 | 1 | 2 |
| 24 | 2,2,3,3 | 3 | 1 | 2 |
| 32 | 1,1,1,1,2,2,2,2 | 2 | 1 | 2 |
| 40 | 八个2 | 2 | 1 | 2 |
| 64 | 十个2、两个3 | 3 | 1 | 2 |

这说明**玩家数量增长不等于来源结构宽度增长**。当最大企业度数有界时，增加企业只是增加更多独立分量；d-DNNF/OBDD、变量消去、分量模型计数和线性 Shapley 分解都可利用这一结构。

## 4. Low/High 实际操纵了什么

### 4.1 基础图不变，地区证明分配改变

Low/High 的企业度数签名、incidence/primal treewidth 和企业分量数完全相同。改变的是每个企业在 PA/PB 的证明数 \((a_e,b_e)\)。

企业 e 的地区 OR 展开项数为 \(2^{a_e}-1\) 和 \(2^{b_e}-1\)，同一企业跨地区乘积项数为

\[
(2^{a_e}-1)(2^{b_e}-1).
\]

三者满足恒等式

\[
(2^{a_e}-1)+(2^{b_e}-1)
+(2^{a_e}-1)(2^{b_e}-1)
=2^{a_e+b_e}-1.
\]

所以在企业度数 d_e 固定时，高共享不会增加这个度数控制总量，只会在“省内替代证明”和“跨省同企业项”之间重新分配。

### 4.2 冻结实例的实际转移

| N | 结构 | 跨省企业 | 省内 OR 项 | 跨省同企业乘积项 | 守恒总量 |
|---:|---|---:|---:|---:|---:|
| 20 | Low | 0 | 12 | 0 | 12 |
| 20 | High | 4 | 8 | 4 | 12 |
| 24 | Low | 0 | 20 | 0 | 20 |
| 24 | High | 4 | 12 | 8 | 20 |
| 40 | Low | 0 | 24 | 0 | 24 |
| 40 | High | 8 | 16 | 8 | 24 |
| 64 | Low | 0 | 44 | 0 | 44 |
| 64 | High | 12 | 28 | 16 | 44 |

High 确实提高了跨地区共同物理来源，但同时减少了单省 DISTINCT 的替代证明。两种效应可能抵消，甚至对不同表示产生相反影响。

### 4.3 证明重叠

同一企业的两个 witness 都是三变量证明，恰好共享一个 E 玩家；B/H 不共享。不同企业 witness 的玩家交集为空。因此当前生成器只产生“星形中心共享”，没有共享 B、共享 H、多对多关联或循环 provenance。

## 5. 两个实验因素是否真正相互作用

原 Low/High 操纵不能独立识别：

- 跨地区共享企业数 q；
- 地区内替代证明数；
- 同企业跨地区乘积项；
- 变量排序下的中间 frontier。

微型结构对照给出以下结果：

| 对照 | 地区证明数 (A:B) | q | 省内 OR 项 | 跨省同企业项 | 总量 |
|---|---|---:|---:|---:|---:|
| degree2_low | 2:0; 0:2 | 0 | 6 | 0 | 6 |
| degree2_cross | 1:1; 1:1 | 2 | 4 | 2 | 6 |
| q2_degree4_unbalanced | 1:3; 3:1 | 2 | 16 | 14 | 30 |
| q2_degree4_balanced | 2:2; 2:2 | 2 | 12 | 18 | 30 |
| fixed_LX_q1 | 0:1;0:3;3:0;3:2 | 1 | 25 | 21 | 46 |
| fixed_LX_q3 | 0:1;1:2;1:2;4:1 | 3 | 25 | 21 | 46 |

由此可建立三个判别实验，而不是继续增加原 seed：

1. 固定度数、固定 q，改变地区内证明平衡，识别局部 OR 与跨省乘积复杂度的转换。
2. 固定度数、固定省内 OR 项和跨省乘积项，只改变 q，识别“共享企业数量”本身是否重要。
3. 固定上述统计，再改变证明交叠形态，例如让 witness 共享 H 或经关系表形成循环，以识别 treewidth/证明重叠的独立作用。

前两个控制已有生成规则和结果数据；第三个需要新建独立 fixture，不能改写历史 E/B/H 对象。

## 6. 价值函数为什么容易分解

### 6.1 COUNT DISTINCT 乘积

当前跨省目标为

\[
C_A(S)C_B(S)
=\sum_{e,f}I_{e,A}(S)I_{f,B}(S).
\]

若 \(e\ne f\)，两个布尔分量使用不相交的企业来源分量；若 \(e=f\)，只共享 E_e，且只在 High 中出现。整个数值价值是有限个 Boolean DNF 查询 Shapley 的加权线性和。

对当前冻结实例，这一分解已在所有测试 mask 上严格重建原 G，误差为0；N≤20 的支付与全联盟 oracle 一致。

### 6.2 输出35个坐标不等于使用35个坐标

local/cross 的 add/joint 都只读取2个坐标，使用率为 \(2/35\)。其余33个坐标只参与报表语义核验，不进入 G，也不会增加新基线的价值交互结构。此前把“完整35坐标报表”作为计算复杂性的叙述背景，不能替代对 G 实际依赖图的分析。

### 6.3 表示之间出现优势转换

cross-joint 的表示规模如下：

| N | 结构 | 稀疏 Harsanyi 项 | 最大单项次数 | LExaShap Boolean 分量 |
|---:|---|---:|---:|---:|
| 20 | Low | 48 | 10 | 8 |
| 20 | High | 24 | 6 | 24 |
| 24 | Low | 120 | 14 | 8 |
| 24 | High | 48 | 10 | 24 |
| 40 | Low | 168 | 10 | 24 |
| 40 | High | 80 | 6 | 80 |
| 64 | Low | 528 | 14 | 48 |
| 64 | High | 224 | 10 | 168 |

High 对 Harsanyi 展开更容易，因为省内 OR 变短；但对逐 Boolean 分量的 LExaShap 更难，因为跨省企业组合更多。不存在一个脱离表示语言的单一“共享更难”结论。这是比原四格计时更清楚的算法优势转换现象。

## 7. H3-S6 为什么掩盖价值与结构因素

### 7.1 状态图与 G 无关

H3-S6 先按每个玩家的 witness-incidence delta 构造所有层；只有层全部建成后，才对 terminal states 调用 value。历史代码的顺序是 `h5_shared.py` 第591–603行：先构造 `self.layers`，再执行 `self.value(state)`。

所以 Add 和 Joint 共享完全相同的状态表示。G 只改变终端数值与反向求值，不改变 frontier。

### 7.2 414,736 的组成

企业度数为 d 时，一个企业分量的完整 evidence-count 状态数为

\[
q(d)=2\cdot3^d-2^d.
\]

解释是：未选 E 时每个 witness 的 B/H 计数取0、1、2，共 \(3^d\)；选 E 时平移为1、2、3，再有 \(3^d\)；两者在每维取1或2的 \(2^d\) 个状态重合。

不同企业分量独立，但 S6 将它们做全局笛卡尔积：

\[
|\mathcal Z|=\prod_e(2\cdot3^{d_e}-2^{d_e}).
\]

于是：

- N=20，度数2,2,2,2：\(14^4=38,416\)；
- N=24，度数2,2,3,3：\(14^2\times46^2=414,736\)；
- N=32：9,834,496；
- N=40：1,475,789,056；
- N=64：612,062,849,929,216。

N=24 的失败发生在最后一个 H 玩家加入时，Low/High 都达到414,736。逐层中间状态略有差异，因为 B/H 的 sid 顺序与企业重连不同；但最终状态数由度数签名决定。所有层的 `value_function_calls=0`，所以该增长发生在 G 应用之前。

### 7.3 这是表示瓶颈，不是游戏内在宽度瓶颈

基础来源 treewidth 只有1/2，而 S6 状态数却是企业分量状态数的乘积。它没有利用企业分量可分解性。不能把 S6 的 N=24 上限写成所有精确算法的困难证据。

可以避免该成本的成熟思路包括：

- 先按企业分量做变量消去/模型计数，再按价值因子组合；
- 把 Boolean lineage 编译到 deterministic/decomposable circuit；
- 利用 Shapley 线性性，把 G 展开成 Boolean 分量或 Harsanyi unanimity 项；
- 对重复 DNF/子电路做共享编译，而不是构造全局 evidence Cartesian product。

## 8. 新增成熟精确基线

### 8.1 SPARSE_HARSANYI_PROVENANCE

从原 SQL lineage 直接用 inclusion-exclusion 得到稀疏 multilinear/Harsanyi 项。对项 \(c_T\prod_{i\in T}x_i\)，每个 \(i\in T\) 获得 \(c_T/|T|\)。这使用标准 unanimity/Harsanyi 分解，没有先枚举 \(2^N\) 联盟。

### 8.2 OFFICIAL_LEXASHAP_BOOLEAN_COMPONENTS

把加法项和乘积项分解为加权 Boolean DNF 组件，调用仓库中冻结的 Abramovich 官方 `DNFCircuit`，再按 Shapley 线性性组合。官方源码路径与 SHA-256 已写入运行环境 manifest。

### 8.3 实测结果

- 两种方法各72个单元全部 `VERIFIED`；
- N≤20 对全联盟 oracle 最大误差 `5.69e-14`；
- 两方法最大相互差异 `9.95e-14`；
- N=64 cross-joint 仍精确完成：Low 为528个 Harsanyi 项/48个 Boolean 分量，High 为224项/168分量；
- 单单元最大实测 solve 时间约0.016秒（稀疏 Harsanyi）和0.47秒（官方 LExaShap）。这些时间用于确认可执行性，不是经过重复计时的正式性能排名。

这直接推翻了“当前 N=24 游戏本身已经难以精确求解”的解释。困难属于 H3-S6 的全局状态表示，而不是当前 G 的内在不可分解性。

## 9. 五类原因的证据矩阵

| 候选原因 | 当前状态 | 直接证据 | 对原 RQ3 的影响 | 可区分的后续实验 |
|---|---|---|---|---|
| 游戏天然易分解 | 已证实 | incidence tw=1、primal tw=2；企业独立分量 | 原实例不是复杂 lineage 压力测试 | 固定 N/度数，加入循环或共享 B/H，使 treewidth 单独增长 |
| 生成器未形成复杂来源 | 已证实 | max degree仅2–3；Low/High 保持度数和宽度 | High 只重分配地区证明 | 固定 q/L/P，独立改变证明交叠和图宽 |
| 价值函数简单 | 已证实 | 只用2/35坐标；可展开为有限 Boolean 分量 | 乘积符号不等于困难交互 | 先从真实买方任务确定 G，再测坐标交互图宽度 |
| H3-S6 表示不合适 | 已证实 | \(\prod_e(2\cdot3^{d_e}-2^{d_e})\)；G 前爆炸 | 原计时无法隔离价值效应 | 与分量 VE、d-DNNF/OBDD、LExaShap 同目标比较 |
| 统计证据不足 | 已证实但次要 | 三个 fixture、每格一次计时、交互两正一负 | 秒级方向不可稳定解释 | 只在结构正交、方法适配后增加独立 fixture 与3–5次计时重复 |

## 10. 从诊断结果发展出的研究机会

以下是候选问题，不是已成立创新点。

### 机会 A：可分解性条件与参数化上界

定义最大企业度数 \(\Delta\)、企业数 m、价值交互阶数 k、来源 primal treewidth t。对当前函数依赖 B→E、H→B 的森林 lineage，当 \(\Delta\) 和 k 有界时，可研究：

- Boolean 分量数量是否为 \(O(m^k)\)；
- 每个分量的编译规模是否只指数依赖 \(k\Delta\) 或 t；
- 全玩家 Shapley 是否因此在 m 上保持多项式。

当前实验给出支持性实例，但尚未构成一般定理。

### 机会 B：表示选择与算法优势转换

Harsanyi 项数受地区内 OR 展开影响；LExaShap 分量数受跨地区企业组合影响。可建立一个 representation selector，以

\[
(\Delta,\;L_{OR},\;P_{cross},\;t,\;k)
\]

预测选择稀疏 Harsanyi、Boolean 分量编译还是分量变量消去。研究重点是可证明的规模界和优势转换条件，而不是再造一个黑盒求解器。

### 机会 C：共享来源是否减少重复编译

High 产生更多 Boolean 分量，但许多组件共享同一企业 indicator DNF。可测试结构化 d-DNNF/MTBDD 或 memoized component compilation 是否把168个组件压缩为共享子电路。这里“共享”可能带来收益，而不是只带来成本。

### 机会 D：完整报表价值的交互图

应把35个坐标视为候选节点，把真实 G 的因子视为超边。真正可能控制复杂度的是坐标交互图的 treewidth、因子阶数和来源—坐标二部图重叠，而不是坐标总数35。下一步先从买方决策、质量约束或统计一致性要求中确定有依据的因子；不应随意把乘积扩大到十个指标。

### 机会 E：打破当前函数依赖的真实来源结构

需要调查真实报表是否存在：

- 一个事实经桥接表支持多个企业/地区；
- 多个场所共享同一就业或分类事实；
- 多条 JOIN 路径形成循环 provenance；
- 可替代证明共享不止一个玩家；
- 同一统计对象的证明图具有增长的 treewidth。

只有这些结构有现实语义时，才建立新 fixture 并测试知识编译边界。

## 11. 下一步研究顺序

1. **不再扩展原 Low/High seed。** 原操纵已经证明不正交。
2. **建立结构参数协议。** 至少冻结 \(\Delta,q,L_{OR},P_{cross},t,k\) 和坐标交互图宽度。
3. **先做三个小型控制。** 固定度数下分别控制 q、地区内证明平衡和证明共享/循环。
4. **保留三类成熟基线。** 稀疏 Harsanyi、官方 LExaShap Boolean 分量、一个真正利用图宽的 VE/d-DNNF/OBDD 实现。
5. **在同一 N、Q、G 上核验。** N≤20 使用冻结 oracle；扩大规模前先过 exactness 门。
6. **价值结构先找应用依据。** READ-C1/IDEA-01 的买方决策价值审计应先于高阶多指标 G。

## 12. 最终回答

我们之前没有找到稳定算法困难，**主要因为游戏本身容易分解、生成器只产生企业中心的低宽度星形来源、价值函数只使用两个且可线性分解的坐标**。同时，**H3-S6 使用了不利用企业分量独立性的全局 evidence-state 表示**，制造了与 G 无关的状态爆炸，从而既掩盖 Add/Joint 差异，也不能代表游戏的内在难度。E1 计时证据不足进一步增加了噪声，但它不是最主要原因。

下一步应研究的不是“更多相同四格”，而是：**来源图宽与证明交叠、地区证明分配、价值交互图，以及不同知识表示之间的优势转换条件。**

## 13. 代码与证据

- 诊断实现：`src/rq3_diagnosis.py`
- 执行入口：`scripts/run_diagnosis.py`
- 配置：`configs/diagnosis_v1.json`
- 测试：`tests/test_rq3_diagnosis.py`
- canonical results：`runs/DIAG_20261113_130136/results/`
- H3 历史实现：`aggregate_report_shapley/src/aggregate_report_shapley/h5_shared.py`
- 本地理论参照：`tmp/researchlab_v2/workspace/deepread/KnowledgeCompilation_Amarilli2020/`、`tmp/researchlab_v2/workspace/deepread/Kara2024_FromShapleyModelCounting/`

## 14. 方法工具引用

本轮的判别实验设计和证据分层使用了 Scientific Agent Skills 的实验设计与科学批判流程：

Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. arXiv:2609.00065. https://doi.org/10.48550/arXiv.2609.00065

