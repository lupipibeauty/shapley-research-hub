# IDEA-03-3 最终审计决定

## 总体状态

`IDEA03_3_NEEDS_TARGETED_GATES`

## 回答核心问题

现有文献已经充分覆盖三件事：单个查询/单个聚合根的全玩家精确 Shapley；多聚合查询在 SQL/视图/数值维护层的共享；显式局部因子游戏通过 Shapley 线性性分解。它们没有共同给出“同一完整层次报表的多异构输出 × 全物理玩家”的联合精确 Shapley 计算。

真正尚未判清的不是 provenance DAG 能否共享，而是：

1. 异构统计坐标能否形成不爆炸的 coalition-size 联合数值状态；
2. 多个报表根能否在不可避免的 \(MN\) 输出之外共享 Shapley 反向消息。

因此研究问题应收缩为上述两个计算机制。非可加 multi-G 保留为应用层验证对象；坐标交互稀疏和纯 partial-provenance 共享不再单独立项。

## 分支处置

| 分支 | 状态 | 处置 |
|---|---|---|
| 3-1 partial provenance | `REPRESENTATION_ONLY` | 不单列算法创新；作为 GATE-B 输入结构 |
| 3-2 numeric state | `UNCLEAR_NEEDS_ONE_GATE` | 执行 GATE-A 后决定保留或收尾 |
| 3-3 multi-output gradient | `UNCLEAR_NEEDS_ONE_GATE` | 执行 GATE-B 后决定是否存在 L5 缺口 |
| 3-4 multi-G | `SURVIVES_AUDIT` | 可加部分关闭；非可加部分依赖 A/B，不另开 gate |
| 3-5 interaction sparsity | `REDUCTION_COVERED` | 作为结构参数保留，独立分支收尾 |

## 不能再使用的表述

- “完整报表有35个坐标，所以必然存在新算法困难。”
- “共享 provenance 就等于共享 Shapley。”
- “自动微分已经免费解决全部多输出 Shapley。”
- “某个 solver 在高共享实例更慢，所以问题固有更难。”
- “数值反卷积异常是新的 Shapley 理论问题。”

## 下一步停止线

本审计完成后停止。只有研究者批准后才执行 GATE-A/B；不新增第三个 gate，不扩展大规模 TPC-H，不开发新求解器。如果两个 gate 都否定内部计算节约，则 IDEA-03-3 收缩为系统工程整合；如果至少一个 gate 通过，再围绕通过的单一层建立形式化条件和同目标成熟基线。
