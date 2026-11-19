# 补充精读优先级

## P1：下一轮必须优先补齐

| 优先级 | 文献/主题 | 原因 | 目标故事 | 完成门槛 |
|---|---|---|---|---|
| P1-1 | Owen (1977), *Values of Games with a Priori Unions* | C1/C2 的“记录后汇总、owner 直接作为玩家、预联盟结构”必须用原始定义和价值公式比较 | C1,C2,E1 | 获取原文；核对玩家、先验联盟、效率/对称性；与 FGSV 定理1逐式比较 |
| P1-2 | Ieong & Shoham, *Marginal Contribution Nets* | A3/D1 的局部交互是否只是 MC-net 加法规则需要直接审计 | A3,D1 | 冻结官方PDF；核对表示、Shapley算法与复杂度；判断整表 `G∘Y` 何时可精确归约 |
| P1-3 | bounded dependency games 准确版本 | 结构局部性可能为 D1/D2 提供成熟参数化边界 | D1,D2 | 先核实题名、作者、venue；再审计 dependency graph 和 Shapley 复杂度 |
| P1-4 | Brooks–Frankel–Kamenica, *Comparisons of Signals* | A2 的多信号共同信息、冗余和互补不能只靠经典 Blackwell 单信号排序 | A2,A3 | 全文定理、信息结构与可比性条件；说明确定性报表的嵌入方式 |
| P1-5 | Bergemann & Bonatti, *Markets for Information: An Introduction* | A1/B1/E1 需要区分信息价值、定价机制与固定收入归因 | A1,B1,E1 | 冻结版本；提取买卖方、支付、信息设计与使用价值对象 |
| P1-6 | Coyle–Manley 引用链中的实证数据估值论文 | 十张卡目前缺少真实完整统计产品买方行为证据 | A1,A2,A3,B1 | 找到实际成交/使用任务证据；不能用 ML benchmark 代替买方决策 |

## P2：针对算法边界回查

- ProvSQL `shapley_all_vars` 的输入电路、精确性和编译前提。
- LMFAO/F-IVM 的多输出共享和增量维护是否能保留完整 `G` 所需联合状态。
- LExaShap 的 d-tree 梯度与 all-player 复杂度，特别是非 Boolean/整表值的归约条件。
- Ensemble Shapley、Harsanyi dividend 和 d-DNNF 的“共享中间量”是否跨多个 `G` 可重用。
- Dynamic Shapley 的精确/近似边界与 D2 的三类事件（新增、删除、属性修订）逐一对应。

## 暂不扩展

本轮不因“完整报表”关键词缺失而无限检索，也不把 ML 数据估值论文的玩家和效用直接迁移到关系数据库记录游戏。P1 完成后再决定是否补充信息产品交易、统计披露或数据合作市场文献。

