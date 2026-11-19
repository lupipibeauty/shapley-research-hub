# 研究状态总览

## 研究主题

项目研究关系型数据、层次报表与固定收益下的 Shapley 贡献分配：包括查询语义与精确算法复现、联合价值／共享来源边界、层次汇总报表，以及基于图神经网络的摊销近似。

## 当前研究方向

| Idea | 状态 | 当前判断 |
|---|---|---|
| IDEA01：买方／整份报表价值 | 候选账本 | 缺少稳定动机与直接原始证据，暂不建立执行分支。 |
| IDEA02：精确 Shapley 方法覆盖与语义边界 | 有证据的成熟方法覆盖 | D1-P、P3 与作者适配器已有历史材料；下一步是输入—语义—输出证据矩阵，而非新的复杂度主张。 |
| IDEA03：共享来源／成本边界 | Stage 3B-1 与数值门完成；候选方向重新收缩 | 星形 F0 族由变量顺序主导，真实 Q9 非星形来源的成本方向依赖表示。LExaShap 数值异常已定位并有局部稳定替代；2A～2F 谱系均保留，下一步聚焦多输出/多 G 复用、表示选择和玩家边界。 |
| IDEA04：GNN 摊销贡献估算 | 课程实验已完成，方法边界明确 | 适合固定来源模式下重复估算；不是精确算法，也未证明通用跨数据库迁移。 |
| IDEA05：玩家粒度与所有者分配 | 候选账本 | 玩家绑定依赖生成器的映射规则；缺少可独立复核的完整映射导出表。 |

## 已确认的档案判断

- 主体项目没有可恢复的旧 Git 提交历史；两个 Luo 嵌套 Git checkout 是外部来源，不能作为项目历史。
- M3 是 D1-P 的设计修订，仍是“仅设计、未执行”；没有 M3 BDD／变量排序实验的原始运行证据。P3 的 MTBDD 输出是另一项实验。
- P3-1B、P3-1C R1、R2、C2 是阈值准备、作者最小复现、同目标适配和语义控制四类不同任务，不是连续参数版本。
- LexaShap 正式批次的 91 项未完成已分类：90 项为 Python 整数转字符串位数限制，1 项为空 divisor 参数错误；尚未全部修复。
- GNN 玩家—物理事实绑定嵌入冻结 JSONL；图代码与数据均为正向边，玩家局部表示不接收下游节点消息，图级池化仍提供全图 context。
- IDEA-03-2：E0/E1 为 VERIFIED；E2 的 H3-S6 为 RESOURCE_LIMIT；补充诊断72个价值检查和144个精确基线单元均 VERIFIED。当前游戏可按企业分解，原四格不应机械扩大。
- IDEA-03-2 后续：五个冻结游戏的历史 G1 与 GR 全联盟等价；新的 N=12、k=2 游戏通过4096联盟 SQL 核验。三组 N=16 F2 配对完成结构/SQL 检查，但只改变同省城市分布，尚未形成跨省共同来源。共享 ADD 与作者 LExaShap 缓存均通过逐玩家精确性门槛；TPC-H SF0.1 自然/供应商共享最小样本已验证结构存在性，未做性能排名或 SF1 扩展。
- IDEA-03 阶段0：`FID_F0_N12` 固定 F0 SQL、E/B/H 物理玩家与35坐标。主 `v_fid` 的 `v(N)=35/36`，可按坐标精确分解；省际 `v_gap` 有225个非零联盟、2286个跨地区非零混合差分和63个负边际，非 unanimity。该阶段确立的“结构化算法不得读取全联盟真值表”约束继续有效。
- IDEA-03 阶段1：旧 E1 主保真度有22,687个联盟差异而 gap 完全相同。新严格配对固定16名玩家、6个见证和35个满联盟坐标，企业度数多重集不同；`v_fid/v_gap` 分别有10,304/2,268个联盟差异，但粗粒度表示规模不变。该阶段结束时阶段2尚未启动。
- IDEA-03 阶段2A：不读取全联盟表作为算法输入，官方 LExaShap 直接编译来源分量；`v_fid` 143个原始分量合并为65个唯一 DNF，`v_gap` 49个分量全部可命中同实例已有完整键。四个对象逐玩家误差不超过 `1.39e-16`。作者接口不接受外部变量顺序、也不支持跨输出部分公共子图，因此阶段2B未启动。
- IDEA-03 阶段2B-0：4096个重连中288个满足冻结满报表计数，归并为12个非同构代表；incidence/primal treewidth 均为1/2。36/36个参考 VE 语义核验完成，企业分量顺序消除主要结构差异，当前星形族状态为 `ORDER_EFFECT_DOMINATES_CURRENT_STRUCTURE_EFFECT`。
- IDEA-03 Stage 3A/3B-1：TPC-H SF0.1 Q9 的完整物理玩家边界形成真实非星形来源，固定 PART/SUPPLIER 后又退化。官方 LExaShap 与 VE 对高重叠结构给出相反成本方向，支持 `REPRESENTATION_DEPENDENT_EFFECT`，不能用单一表示概括结构难度。
- IDEA-03 Numerical Gate：LExaShap 的 N_add 异常定位为浮点反卷积误差被阶乘梯度放大；prefix/suffix 与 product-tree sibling product 在 float64 下直接修复 N=60。该问题定性为局部实现选择，不扩展为独立研究主线。
- IDEA-03-2A～2F 均已登记在 `IDEA03_shared_lineage_cost/IDEA03_2A_2F_BRANCH_REGISTRY.md`。2D 在当前星形族并入2B，2F仍是已冻结设计但未完成独立实验，不得误记为六个已执行 Git 分支。
- IDEA-03-2A～2F 的 2026-11-19 最新进展已汇总到 `IDEA03_shared_lineage_cost/IDEA03_2A_2F_LATEST_PROGRESS_20261119.md`：2A 为价值准入门；2B/2D 转入表示选择；2C/2F 保留为多输出/多 G 共享计算候选；2E 是尚未开始正式支付模型的规范层问题。
- 文献侧已建立57项原文范围矩阵，并对31篇已有全文审计论文回查作者局限：29篇定位到作者明确陈述，2篇完成检索但未发现独立局限段。该结果用于提出质疑和准入条件，不用于自动宣布创新或关闭方向。

## 证据使用规则

证据等级与研究状态必须分开记录。报告文本不自动等价于 A 级证据；“环境阻塞”“用户暂停”“仅设计”也不得记为失败。无法回到代码、配置、CSV、JSON 或日志的判断保持待核实。

详细证据参见 `evidence/round1/`、`evidence/round2/`、`research/EXPERIMENT_INDEX_CURRENT.csv`、`IDEA03_shared_lineage_cost/IDEA03_2A_2F_BRANCH_REGISTRY.md`、`IDEA03_shared_lineage_cost/IDEA03_2A_2F_LATEST_PROGRESS_20261119.md`、`research/IDEA03_3_branch_audit_20261114/`、`research/IDEA03_story_literature_deepread_v1/`、`research/IDEA03_theory_extension_deepread_v2/` 与 `research/IDEA03_literature_limitation_atlas_v1/`。
