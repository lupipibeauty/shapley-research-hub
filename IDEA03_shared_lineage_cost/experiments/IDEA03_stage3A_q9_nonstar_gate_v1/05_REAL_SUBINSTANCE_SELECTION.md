# 05 真实子实例选择

## 预注册规则

选择目标固定为12条witness。规则在正式结构结果产生前写入 `config/stage3a_q9_protocol.json`：

- Q9-L：确定性贪心，依次最小化与已选witness的最大P1 overlap、总overlap、重复pair、共享PART/SUPPLIER、共享ORDERS，最后按物理键破平局。
- Q9-H：先按cycle rank、pair边数、witness数选择PART–SUPPLIER分量；以witness最多的pair为种子，最多取6条，再从共享PART或SUPPLIER的其他pair取样，最后按P1 overlap补齐。

没有读取Shapley或编译结果，也没有修改任何真实键。

## 结果

| 子实例 | 边界 | 玩家 | witness | 最大overlap | overlap≥2 | incidence宽度上界 | primal宽度上界 |
|---|---|---:|---:|---:|---:|---:|---:|
| Q9-L | P1 | 60 | 12 | 0 | 0 | 1 | 4 |
| Q9-L | P2 | 36 | 12 | 0 | 0 | 1 | 2 |
| Q9-H | P1 | 31 | 12 | 3 | 21 | 3 | 4 |
| Q9-H | P2 | 27 | 12 | 1 | 0 | 1 | 2 |

Q9-L的12条记录在P1下完全无玩家共享。Q9-H包含PART=10816下三个真实supplier pair：种子pair `(10816,77)` 取6条，`(10816,337)` 和 `(10816,597)` 各取3条，既保留pair内重复，也保留共同PART形成的跨pair连接。

明细见 `results/q9_l_witnesses.csv`、`results/q9_h_witnesses.csv`；结构见 `results/subinstance_metrics.csv`。它们只是后续候选fixture，本轮没有计算联盟价值或Shapley。
