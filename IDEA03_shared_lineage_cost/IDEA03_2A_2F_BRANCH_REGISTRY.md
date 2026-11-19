# IDEA-03-2A～2F 研究子方向谱系

更新日期：2026-11-19

本文件中的“分支”指研究子方向，不表示已经创建同名 Git branch。当前仓库以主线保存共同证据，待某个子方向通过准入门槛并进入独立实现时，再建立实验分支。

## 总表

| 子方向 | 核心问题 | 当前状态 | 是否有独立实验 | 后续承接方向 |
|---|---|---|---|---|
| IDEA-03-2A | 联合价值是否真实非退化 | 已完成审计；现象成立但不单独作为算法创新 | 有 | IDEA-03-3-5、真实价值依据审计 |
| IDEA-03-2B | 来源结构参数如何决定表示规模 | 当前星形 F0 家族已收尾；真实非星形来源继续验证 | 有 | IDEA-03-4-1、IDEA-03-4-2 |
| IDEA-03-2C | 多统计分量能否共享编译并恢复全部玩家 Shapley | 精确性已验证；冷端到端共享优势尚未证实 | 有局部实验，未完成最终对照 | IDEA-03-3-1、03-3-2、03-3-3 |
| IDEA-03-2D | 来源共享增加时表示何时反而缩小 | 历史观察保留；在当前星形族并入 2B，不再单独扩样 | 有 | IDEA-03-4-1、03-4-2 |
| IDEA-03-2E | 负 Shapley 如何映射到固定收入 | 负贡献现象已验证；属于独立支付层问题 | 有现象证据，暂无支付层正式实验 | IDEA-03-5-3，亦可与 IDEA-01 联动 |
| IDEA-03-2F | 同一 SQL 来源服务不同价值函数 G 时能否复用 | 已冻结实验约束；尚未形成独立完整实验 | 有设计与局部缓存观察 | IDEA-03-3-4、03-6-1、03-6-2 |

## IDEA-03-2A：联合价值有效性

- 已回答：历史阈值函数存在退化；修正后的跨地区联合任务可以出现非零混合差分，不能只凭公式含乘积就认定存在交互。
- 证据入口：
  - `experiments/IDEA03_2_shared_compilation_tpch_v1/07_IDEA03_SUBDIRECTION_REGISTRY.md`
  - `experiments/IDEA03_stage0_fidelity_freeze_20261113/03_VALUE_VALIDITY_CHECK.md`
  - `experiments/IDEA03_2_joint_value_deepening_v1/`
- 研究判断：价值函数有效性是算法实验的准入条件，不把价值函数换名本身作为创新。
- 后续：若继续，应研究具有实际整表评价依据的稀疏交互图，而非任意扩大联合指标数量。

## IDEA-03-2B：来源结构与表示规模

- 已回答：玩家数量、价值状态数和来源表示难度不是同一参数；当前 E/B/H 星形族的 incidence/primal treewidth 长期保持 1/2，变量顺序效应可主导结构差异。
- 证据入口：
  - `experiments/IDEA03_stage2B0_ordered_structure_gate_v1/`
  - `experiments/IDEA03_stage3A_q9_nonstar_gate_v1/`
  - `experiments/IDEA03_stage3B1_q9_nonstar_cost_gate_v1/`
  - `experiments/IDEA03_2_joint_structure_v2/PREVIOUS_EXPLORATION_DIAGNOSIS.md`
- 研究判断：当前星形 F0 家族不再扩大 N 或增加随机种子；真实非星形来源中仍可研究表示门槛。
- 后续：比较不同表示体系的结构参数与优势转换，不能把单一求解器的状态膨胀当作游戏困难下界。

## IDEA-03-2C：多输出共享编译

- 已回答：Boolean 分量分解、官方 LExaShap 完整分量缓存和共享 ROADD 可以精确恢复目标游戏；warm reuse 存在。
- 尚未回答：从 SQL provenance 直接构造共享多输出表示，能否降低冷启动端到端成本；部分子 DAG、数值状态和 all-player 梯度是否能在不同统计分量间复用。
- 证据入口：
  - `experiments/IDEA03_2_shared_compilation_tpch_v1/`
  - `experiments/IDEA03_stage2A_mature_source_compilation_20261113/`
- 后续拆分：
  - IDEA-03-3-1：部分来源子 DAG 的跨输出共享；
  - IDEA-03-3-2：相同来源上的数值状态复用；
  - IDEA-03-3-3：多输出 all-player Shapley/梯度复用。

## IDEA-03-2D：共享增加但表示缩小

- 已回答：集中共享在部分表示中会缩小，在另一些表示或变量顺序下会放大；方向依赖表示，不能预设“共享越多越难”。
- 证据入口：
  - `experiments/IDEA03_stage2B0_ordered_structure_gate_v1/`
  - `experiments/IDEA03_stage3B1_q9_nonstar_cost_gate_v1/`
  - `experiments/IDEA03_2_shared_compilation_tpch_v1/07_IDEA03_SUBDIRECTION_REGISTRY.md`
- 研究判断：作为 2B 的机制解释保留，不删除历史观察；当前星形族内不再作为独立扩样分支。
- 后续：IDEA-03-4-1 表示选择条件、IDEA-03-4-2 混合表示。

## IDEA-03-2E：负 Shapley 与固定收入

- 已回答：比例型统计价值中确实出现负边际和负 Shapley；标准 Shapley 与非负支付、预算平衡等合同约束不能混为同一层。
- 证据入口：
  - `experiments/IDEA03_2_shared_compilation_tpch_v1/07_IDEA03_SUBDIRECTION_REGISTRY.md`
  - `experiments/IDEA03_2_joint_value_deepening_v1/`
- 研究判断：底层精确 Shapley 保持原定义；若需要非负收入分配，应另建支付映射层并明确改变了哪些公理。
- 后续：IDEA-03-5-3 固定基础设施下的归因与支付边界，也可与 IDEA-01 的真实买方价值验证联动。

## IDEA-03-2F：同一 Q、多种 G 的计算复用

- 已冻结设计：固定 SQL lineage，分别运行主保真度、跨地区 gap 与历史压力价值；共享来源构造/编译，不允许读取或复用联盟 oracle。
- 已有证据：相同 canonical Boolean 分量可以完整缓存命中，说明“完全相同分量复用”可行；这不等于不同 G 的部分结构共享已经解决。
- 证据入口：
  - `experiments/IDEA03_stage0_fidelity_freeze_20261113/05_STAGE1_EXPERIMENT_CONSTRAINTS.md`
  - `experiments/IDEA03_stage0_fidelity_freeze_20261113/04_EXISTING_ALGORITHM_COVERAGE.md`
  - `experiments/IDEA03_2_shared_compilation_tpch_v1/`
- 当前状态：`DESIGN_FROZEN / PARTIAL_CACHE_EVIDENCE / STANDALONE_EXPERIMENT_NOT_COMPLETED`。
- 后续拆分：IDEA-03-3-4 多 G 共享变换与求解；IDEA-03-6-1 重复报表归因的摊销计算；IDEA-03-6-2 数据或报表变化下的增量 Shapley。

## 2026-11-19 文献与理论审计更新

- 六个方向的最新状态统一见 `IDEA03_2A_2F_LATEST_PROGRESS_20261119.md`。
- 2A/2E 新增价值、信息市场和收益机制原文证据，进一步确认“联盟价值—记录贡献—最终支付”必须分层。
- 2B/2D 新增 MC-net、bounded dependency、knowledge compilation 和 aggregate-CQ 证据，支持把后续问题收缩为表示选择及参数化条件。
- 2C/2F 新增 DBSP、F-IVM、LMFAO、provenance 与模型计数竞争审计；成熟方法已能共享查询/统计中间量，但是否能同目标恢复全部玩家 Shapley 仍需正式归约和实验。
- 新证据目录为 `../research/IDEA03_3_branch_audit_20261114/`、`../research/IDEA03_story_literature_deepread_v1/`、`../research/IDEA03_theory_extension_deepread_v2/` 和 `../research/IDEA03_literature_limitation_atlas_v1/`。

以上更新不改变历史 canonical runs，也不把文献相似性直接判作覆盖或创新。

## Git 分支准入规则

1. 研究子方向先在本表和 `research/IDEAS.md` 登记，不因提出候选问题就创建空分支。
2. 当方向具有冻结的 Q、玩家、G、竞争基线和停止条件，并需要独立代码改动时，才创建 `idea03/<编号>-<短名>` 分支。
3. 已收尾、被合并或得到否定结果的方向保留证据，不删除、不改写为“从未尝试”。
4. 不同分支的性能比较必须引用同一冻结输入和 canonical run，避免用不同玩家或不同 G 的历史结果排名。
