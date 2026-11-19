# 理论启发矩阵

## 1. 五篇论文解决的是不同层次

| 文献 | 原始现实/数学问题 | 核心结构 | 已解决对象 | 对 IDEA-03 的直接作用 | 不能据此关闭的问题 |
|---|---|---|---|---|---|
| Owen (1977) | 玩家已有亲和联盟时如何修改通常 value | 先验联盟/兼容顺序 | 结构化玩家联盟下的价值概念（正文待获取） | R4 玩家与议价块 | 重叠所有权、owner-game 与 record-sum 等价、SQL 计算 |
| Comparisons of Signals | 信息源排序为何被已有相关信息翻转 | 同一扩展空间中的信号 join；reveal-or-refine | 对额外信息稳健的信号比较 | R1 冗余/互补，R3 任务价值 | 确定性报表如何合法嵌入、记录收益分配、精确 Shapley |
| MC-nets | 指数特征函数如何用局部交互紧凑表示 | 正/负规则的加法和 | 已有规则表示下线性 Shapley | R3 结构化精确求解，R2 规则基复用 | SQL+G 编译规模、多输出共享、经济价值依据 |
| Bounded dependency | 怎样用实例结构参数化合作博弈计算 | 语义 dependency graph | 已知依赖集合时 Shapley FPT；黑箱发现下界 | R1/R3 语义交互，R5 局部更新 | provenance 图到语义图的证书、依赖发现成本、真实 G |
| Markets for Information | 来源—中介—买方之间如何生产和交易信息 | 信息设计、转移、买方行动 | 经济对象与机制的统一视角 | R3 价值形成、R4 三方边界、R2 任务族 | 固定收入分配算法、SQL provenance、具体交易价格 |

## 2. 关键桥接关系

### 2.1 信息结构到合作博弈

给定状态 `ω`、先验、买方行动集与效用，联盟 `S` 提供的记录可诱导信号 `π_S`，再定义决策价值 `v(S)`. Comparisons of Signals 约束 `π` 之间的稳健排序；Shapley 才对由这些信号诱导的 `v` 归因。信号比较不是另一种分配算法。

### 2.2 玩家制度到联盟值

Owen 处理玩家已有的联盟结构；Markets for Information 区分来源方、中介和买方。二者结合提示：玩家是谁、哪些主体先组成议价块、分配的是买方支付还是平台净收入，需要合同先验冻结。记录 owner 标签本身不足以推出先验联盟。

### 2.3 游戏表示到精确计算

MC-net 从句法规则分解 `v`；dependency graph 从语义上记录“谁会改变谁的边际”。前者可以给后者一个候选图，但规则冗余会产生假边。SQL provenance 又是更上游的证明结构。研究空间位于：

`SQL/provenance → exact game representation → semantic dependency → all-player Shapley`。

每个箭头都需要语义等价证书和表示规模界，不能用概念相似替代。

### 2.4 多 G 复用

Markets for Information 给多 `G` 一个经济来源：买方先验、行动和损失不同。Comparisons of Signals 可判断某些来源排序是否跨任务稳健；MC-net 可共享规则支持；dependency 方法可共享候选交互图。是否真正加速取决于共享的是 Q、lineage、规则基、依赖图还是局部边际表。

## 3. 对 R1–R5 的扩展而非封口

| 既有组合 | 新增可验证子问题 | 理论依据 | 证据仍缺 |
|---|---|---|---|
| R1 | 报表等价分输出等值、冻结任务等值、任务域稳健等值三层 | Comparisons of Signals | 真实状态/行动嵌入 |
| R1 | provenance overlap 与 semantic dependency 何时一致 | bounded dependency + MC-net | SQL 类的充分/必要条件 |
| R2 | 多买方 G 是否共享规则支持或依赖候选图 | Markets + MC-net | 真实任务族与编译界 |
| R3 | 决策诱导的互补能否编译为小规则/低依赖度 | Signals + MC-net + dependency | 任务模型和结构规模 |
| R4 | record-sum、owner-game、Owen 型分配何时一致 | Owen + 信息市场三方模型 | 正文、合同与权利证据 |
| R5 | 更新是否只触及局部依赖与规则 | dependency + MC-net | 动态正确性与摊销界 |

