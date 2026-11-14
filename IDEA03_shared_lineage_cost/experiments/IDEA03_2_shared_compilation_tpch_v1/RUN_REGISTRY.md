# 运行登记

| 运行 | 阶段 | 状态 | 说明 |
|---|---|---|---|
| `SHARED_20261113_164908` | E0→E2 | `RESOURCE_LIMIT_ORCHESTRATION_ABORTED` | wrapper 中止后 detached child 产生了部分 E1/E2 raw，但缺少原子 summary/env，全部不作为 canonical；各阶段已独立重跑。 |
| `SHARED_20261113_175706` | E1 | `VERIFIED` | 3 个配对、6 个 N=16 游戏、390 个 SQL/Python 掩码检查。 |
| `SHARED_20261113_175906` | E2 | `RESOURCE_LIMIT` | 对全部 6 个夹具重复重编译超出首轮试验预算，未生成原子结果表。 |
| `SHARED_20261113_180500` | E2 | `VERIFIED` | 预先缩回 E0 与第 1 组受控配对；60 个方法单元全部通过精确性门槛。 |
| `SHARED_20261113_181253` | TPC-H | `VERIFIED` | SF0.1 自然样本与高共享压力样本，N≤16 全联盟 oracle。 |
| `SHARED_20261113_181356` | E0 | `VERIFIED` | 历史 G1 等价性、k=2 非退化夹具及 4096 联盟 SQL 核验。 |

中止运行保留原文件与原因；不存在删除失败运行或用成功运行覆盖失败状态的情况。

