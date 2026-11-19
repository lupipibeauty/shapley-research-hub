# 模型与符号卡

| 符号 | 含义 | 项目对应 |
|---|---|---|
| `v(i|S)` | 玩家 i 对 S 的边际 | 加入一条物理事实后的整表价值变化 |
| `D(i)` | 能改变 i 边际的玩家集合 | 对冻结 Q、G 的语义依赖 |
| `I(i)` | 与 i 无依赖的玩家 | 可被组合计数聚合的玩家 |
| `d` | 最大 dependency degree | FPT 主参数 |
| positive dependency | 只记录边际严格上升 | 非单调/负交互时不足 |
| value oracle | 查询任意联盟值 | SQL evaluator；可能很昂贵 |

