# 研究成熟度总览：先看原文，再看交叉缺口

## 1. 成熟度刻度

- `M0 导航`：只有书目、摘要或综述导航。
- `M1 定义成熟`：对象和问题有清楚定义，但没有一般理论或可运行方法。
- `M2 理论成熟`：有定理、复杂度或公理化结果，适用条件明确。
- `M3 算法成熟`：有可执行算法及复杂度分析。
- `M4 实证/系统成熟`：有代码、系统或多数据实验；不表示已经适配本项目。
- `M5 跨场景成熟`：同一数学对象在多个真实场景、不同任务和实现中得到验证。

成熟度评价针对各论文自己的问题，不是“是否解决 IDEA-03”。

## 2. 六层研究地图

### 第一层：数据/信息为什么有价值

**已有研究程度：M2--M4，但价值对象高度分化。**

- 信息价值和定价：Abbas--Hazen、Ai、Bergemann--Bonatti--Smolin、Markets for Information 已明确价值依赖先验、行动、效用、信息机制和买方类型。
- 决策价值：Cui、SPO、DFL、Nagrecha--Chawla 已表明预测改善、行动改善和货币收益是不同目标。
- 数据价值分类：Coyle--Manley、Ebiele 等已经系统区分成本、收入、市场、影响、任务效用和社会价值。
- 真实收入制度：Caglio--Mayhew 提供“数据收入分配规则改变参与者行为”的实证证据。

**仍未统一：**一份多源完整统计产品的买方、已有信息、行动、效用、成交价格和成交后收入池之间没有通用转换公式。这不是“价值文献很少”，而是不同价值对象本来就不等价。

### 第二层：应该把谁视为玩家，分配什么

**已有研究程度：M2--M4，多种规范目标已经成熟。**

- Data Shapley：记录作为玩家、给定任务 utility 的标准 Shapley。
- Faithful GSV：组值应等于组内记录标准 Shapley 之和，避免其他组重分组影响。
- Owen：先验联盟结构下的价值概念，但本项目缺正文证据。
- 2D-Shapley、Beta Shapley、Banzhaf、semivalue：分别改变玩家结构或联盟权重，不能与标准记录 Shapley混称。
- Badewitz、Dawande、Joseph：把贡献分配与精度选择、参与成本、公平下界或平台收益最大化结合，目标不再只是标准 Shapley。

**仍需研究者决定：**研究的是技术来源贡献、可撤回事实包、所有者议价单位，还是平台机制中的卖家。这是制度选择，不应由计算便利倒推。

### 第三层：SQL 输出从哪些事实产生

**已有研究程度：M3--M4，是当前最成熟的一层。**

- Green 的 provenance semiring 统一正关系代数来源。
- Amsterdamer 等扩展至聚合来源。
- ProvSQL 把来源追踪工程化到 PostgreSQL。
- Scorpion、LensXPlain 处理聚合异常和解释，但目标不是收益分配。
- DBSP、F-IVM 处理查询和统计状态的增量维护。

**主要边界：**provenance 表达“证明/来源”，不自动给出玩家 Shapley；物理 tuple 变量与逻辑事实包玩家也不天然一致。来源表达、玩家绑定和任务价值需要三次独立语义转换。

### 第四层：数据库事实 Shapley 的精确计算

**已有研究程度：M2--M4，成熟理论和强基线很多。**

- Deutch、Livshits：Boolean/CQ、safe/hierarchical 查询和 d-D 电路。
- Kara--Olteanu--Suciu：Shapley 与模型计数的归约关系。
- Abramovich/LExaShap：lifting、d-tree、gradient 与聚合扩展。
- Standke--Kimelfeld：MIN/MAX/COUNT DISTINCT/AVG/quantile 等 aggregate CQ 的复杂度前沿。
- Luo：独立记录效用下按结果记录和 minimal synthesis 分解。
- Dosso：关系科学数据库中的 tuple/curator credit。

**尚未自动覆盖：**逻辑记录包、多坐标完整报表和外部联合 `G`。但这些对象差异本身不是创新；必须证明不能被成熟模型计数、线性分解或 aggregate-CQ 方法精确归约。

### 第五层：近似、抽样和学习式摊销

**已有研究程度：M3--M4，方法丰富但目标与误差口径不同。**

- TMC/G-Shapley、Efficient Sampling、ASSS、RSS/ARSS：降低抽样方差或提高样本利用率。
- FastSHAP：训练解释器实现高吞吐摊销预测。
- TN-SHAP-G：学习图对齐张量网络代理，再在代理上确定性提取 Shapley/交互。
- Ensemble Shapley：利用分片和集成复用，但改变为受限排列目标。

**主要争议：**训练/编译/效用 oracle 成本是否计入；代理误差是否转化为 Shapley 误差；使用的是否仍是同一个标准 Shapley 游戏。当前不能只比较推理 wall-clock。

### 第六层：动态、多任务和持续更新

**已有研究程度：M2--M4，但局部性条件很强。**

- Xia：复用旧排列与 utility，估计新增/删除后的 Shapley 差分。
- Yang：维护玩家×任务 Shapley 矩阵，依赖支持集局部性和任务距离。
- FedDSV：按训练轮定义并累加轮内价值，适用于动态参与。
- DBSP/F-IVM：精确维护查询结果和统计状态，不维护所有联盟边际。

**尚未统一：**SQL 更新局部性、任务局部性和 Shapley 边际局部性是三个概念。少量报表单元变化不保证少量玩家贡献变化。

## 3. 当前真正成熟与仍脆弱的部分

| 问题 | 当前成熟度 | 依据 | 仍脆弱之处 |
|---|---:|---|---|
| 给定联盟价值后的标准 Shapley 定义 | M5 | 合作博弈与大量数据估值工作 | 玩家和价值必须先冻结 |
| Boolean/若干 aggregate query 的事实 Shapley | M3--M4 | Deutch、Livshits、Kara、Abramovich、Standke | 多坐标联合 G 与逻辑事实包 |
| SQL provenance 和聚合来源 | M4 | Green、Amsterdamer、ProvSQL | 来源图不等于语义依赖图 |
| 黑箱 Shapley 近似 | M4 | TMC、CC、ASSS、RSS 等 | 同预算、同 oracle、误差与端到端成本 |
| 学习式摊销 Shapley | M3--M4 | FastSHAP、TN-SHAP-G | 原游戏 fidelity、分布外和安全路由 |
| 买方信息/决策价值 | M2--M4 | 信息经济学、SPO/DFL、供应链实证 | 真实完整统计产品的任务和成交证据 |
| 所有者/事实包制度边界 | M2 | FGSV、Owen、机制设计文献 | 权利、退出、共同交付的实证证据 |
| 多源完整报表的统一模型 | M1--M2 | 当前项目与跨论文组合 | 三层拼接尚未形成共同定理 |

## 4. 对“研究程度”的简要判断

该领域不是“Shapley 还没人研究”，而是各层已经分别高度成熟；目前最不成熟的是层间转换：

1. `真实任务/交易 → 冻结 G`；
2. `物理事实/权利结构 → 合法玩家 N`；
3. `SQL provenance + G → 精确合作博弈表示`；
4. `查询/任务更新 → 可证明局部的贡献更新`。

这些转换是否能形成新理论，需要研究者选择一个真正关心的现实矛盾后再证明，不能仅靠把所有层拼在一起。

