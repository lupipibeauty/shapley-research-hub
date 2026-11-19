# IDEA-03-2A～2F 最新研究进展

更新日期：2026-11-19

本文件汇总六个研究子方向的最新状态。它们是 IDEA-03 下的研究问题谱系，不等于六条 Git 分支，也不表示六个方向都已经完成独立实验。

## 总览

| 子方向 | 已取得的进展 | 最新研究判断 | 当前状态 | 下一道门 |
|---|---|---|---|---|
| IDEA-03-2A 联合价值有效性 | 历史退化值已识别；`v_fid` 与 `v_gap` 完成空联盟、满联盟、混合差分、负边际和线性分解审计 | 价值有效性是算法实验准入条件，不把价值函数换名作为创新 | `COMPLETED_AS_GATE` | 用真实买方任务或正式统计评价规则为坐标交互提供依据 |
| IDEA-03-2B 来源结构与表示规模 | 星形 F0、严格配对、4096重连、TPC-H Q9 非星形来源及 LExaShap/VE 对照均已完成 | 玩家数、来源共享、图宽和表示规模不是同一参数；成本方向依赖表示和变量顺序 | `STAR_FAMILY_CLOSED / NONSTAR_REPRESENTATION_DEPENDENT` | 在同一冻结游戏上比较有理论保证的不同表示，不以单求解器状态代替困难下界 |
| IDEA-03-2C 多输出共享编译 | Boolean 分量、共享 ROADD、LExaShap 分量缓存均通过精确性门；warm reuse 已观察 | “完全相同分量复用”已成立，但 SQL 到共享多输出表示的冷启动端到端收益未证明 | `PARTIAL_EXPERIMENT / FINAL_CONTROL_MISSING` | 分开验证部分来源子 DAG、数值状态和 all-player 梯度复用 |
| IDEA-03-2D 共享增加但表示缩小 | 星形重连和 Q9 高低重叠均出现不同表示下相反方向 | 共享增多既可能压缩也可能放大表示，不存在当前证据支持的单调定律 | `MERGED_INTO_2B_FOR_CURRENT_FAMILY` | 发展表示选择条件或混合表示问题，不再在星形族机械扩样 |
| IDEA-03-2E 负 Shapley 与固定收入 | `v_gap` 等比例/比较价值中已核验负边际与负贡献现象 | 标准贡献归因、非负支付、预算平衡和参与约束属于不同规范层 | `PHENOMENON_VERIFIED / PAYMENT_MODEL_NOT_STARTED` | 冻结合同目标、退出权和基础设施责任后，再定义支付映射及其公理代价 |
| IDEA-03-2F 同一 Q、多种 G 的计算复用 | 已冻结同一 SQL lineage 服务 `v_fid`、`v_gap` 和压力值的约束；完整 canonical 分量缓存可命中 | 相同分量复用不等于不同 G 的部分共享已解决；尚无独立完整实验 | `DESIGN_FROZEN / STANDALONE_EXPERIMENT_NOT_COMPLETED` | 与成熟多查询/多输出方法做同目标冷启动、warm 和增量三口径对照 |

## 本轮文献与理论补充对六方向的影响

### 2A 与 2E：价值定义和支付层必须分开

Data Shapley、Beta Shapley、Badewitz、Dawande、Galperti 及信息市场文献共同说明：任务价值、记录贡献、平台收入和最终支付并不自动等价。该文献进展强化了两条约束：2A 只负责冻结可解释的联盟价值；2E 必须另行说明非负支付、参与和预算平衡会改变哪些 Shapley 性质。

### 2B 与 2D：表示依赖不是偶发现象

知识编译、模型计数、bounded dependency、MC-net 与 aggregate-CQ 文献提供了 treewidth、pathwidth、dependency degree、规则规模和 localized value 等不同参数。当前实验中的 `REPRESENTATION_DEPENDENT_EFFECT` 与这些理论语言一致，但尚未形成新的统一边界。后续问题应是“什么条件下选择什么表示”，而不是证明共享必然增加成本。

### 2C 与 2F：已有多输出基础设施是强竞争对象

DBSP、F-IVM、LMFAO、provenance semiring 和模型计数文献已经成熟处理查询维护、因子化和共享中间量。它们没有直接输出同一记录游戏的全部玩家 Shapley，但构成 2C/2F 必须比较的成熟基础设施。剩余问题是来源共享能否穿过 Shapley 的 coalition-size 权重、外部 G 和 all-player 求解，而不是简单宣称“多输出尚无人研究”。

## 新增证据入口

- 六方向历史与实验谱系：`IDEA03_2A_2F_BRANCH_REGISTRY.md`
- 3-1～3-5 分支级竞争文献与理论审计：`../research/IDEA03_3_branch_audit_20261114/`
- 十张研究故事与竞争文献矩阵：`../research/IDEA03_story_literature_deepread_v1/`
- Owen、MC-net、bounded dependency、signals 与 information markets 理论补充：`../research/IDEA03_theory_extension_deepread_v2/`
- 57项原文范围、研究成熟度与作者局限图谱：`../research/IDEA03_literature_limitation_atlas_v1/`

## 当前优先顺序

1. 优先保留 2C/2F：但先做同目标、同输入、冷启动与复用成本分离的准入实验。
2. 继续 2B/2D 的理论化：转为表示选择和参数化条件，不扩大当前星形 fixture。
3. 2E 保留为规范性分配问题：需要真实权利与合同设定，不与精确求解器混做。
4. 2A 作为所有算法实验的固定准入门，不独立包装成算法贡献。

## 不应误记的事项

- 六个子方向不是六个已经执行的 Git 分支。
- 2D 在当前星形数据族已经并入 2B，但历史观察和否定证据继续保留。
- 2F 仍是冻结设计和局部缓存证据，不能写成完成实验。
- 新文献说明存在可借鉴结构，不等于已经覆盖本项目，也不等于已证明创新。
