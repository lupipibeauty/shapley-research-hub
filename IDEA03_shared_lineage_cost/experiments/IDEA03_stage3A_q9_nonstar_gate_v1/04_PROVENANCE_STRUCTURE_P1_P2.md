# 04 P1/P2来源结构比较

## 核心结果

| 指标 | P1完整物理事实 | P2保守边界 |
|---|---:|---:|
| 玩家数 | 918 | 854 |
| witness数 | 402 | 402 |
| witness大小 | 5 | 3 |
| 最大玩家witness度 | 40 | 14 |
| 最大witness overlap | 3 | 1 |
| overlap≥2的witness对 | 1,559 | 0 |
| overlap≥3的witness对 | 1,559 | 0 |
| incidence分量 | 10 | 50 |
| 最大分量：玩家/witness | 147 / 65 | 49 / 24 |
| incidence是否有cycle | 是 | 否 |
| incidence cycle rank | 700 | 0 |
| incidence min-fill width上界 | 3 | 1 |
| primal min-fill width上界 | 4 | 2 |
| primal clique下界 | 4 | 2 |
| 是否可严格按pair拆分 | 否 | 否（仅2条订单桥接） |

原始指标见 `results/provenance_metrics.csv`，overlap分布见 `results/witness_overlap_distribution.csv`。

## P1：真实非星形成立

P1中重复同一 `(part,supplier)` 的两个witness自然共享：

`PART + SUPPLIER + PARTSUPP`

最大交叠为3，共1,559对；不存在大小2的交叠。不同pair还会通过共同PART、一个共同SUPPLIER及少量共同ORDERS继续连接。incidence图出现cycle，min-fill上界3；primal图每条五玩家witness形成5-clique，宽度下界和启发式上界都为4。因此P1明确超过F0的incidence/primal 1/2。

## P2：退化为低宽结构

移除PART/SUPPLIER玩家后，相同pair内的witness只共享一个PARTSUPP；跨pair的两条订单连接也只产生单玩家共享。P2最大overlap为1，incidence图是森林、宽度上界1，primal宽度上界2，回到F0同级。

P2严格意义上不能完全按pair独立拆分，因为两条订单分别跨接两个pair；但这种连接没有形成多玩家overlap或高于F0的宽度，不能据此称为明显非星形压力对象。

## 玩家边界结论

Q9的强非星形证据依赖把PART和SUPPLIER主数据纳入收益分配玩家。它不是由人工键关系造成，但也不是对所有合理玩家定义都成立。因此不能笼统表述为“Q9天然是非星形Shapley游戏”。
