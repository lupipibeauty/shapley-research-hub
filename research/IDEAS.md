# Idea 总览与子问题（草案，不是已创建的 GitHub Issues）

## IDEA-01 真实整表价值与买方任务
- 子问题：哪些买方具体决策会使用整张多层统计报表？不同指标怎样改变决策？有哪些可观察的收益或损失？
- 既有基础：D1-P V1/V2 是给定价值函数的实验模型。
- 当前状态：文献与应用价值审计尚待开展；不能写成已通过经济验证。

## IDEA-02 现有精确 Shapley 方法的覆盖边界
- 子问题：玩家绑定、COUNT DISTINCT、JOIN、联合价值等在成熟 DP/WMC/知识编译下分别覆盖到哪里？
- 已完成：P3-0 精确锚点、P3-1B 阈值分解、P3-1C R2 同目标适配等。
- 已否定：JOIN 本身不是新难点，V1 比例评分并不必全联盟枚举等过强命题。
- 当前状态：持续覆盖审计，不直接声称新算法创新。

## IDEA-03 多指标共享来源与成本
- 已执行：E0/E1/E2 和补充结构诊断。诊断覆盖 N=10–64、18个 fixture、72个价值检查和144个精确基线单元。
- 已证实结构：每个企业形成独立 witness 分量；incidence/primal treewidth 恒为1/2。Low/High 保持度数，只在省内替代证明与跨省同企业项之间转移复杂度。
- 已证实价值边界：当前 G 只使用2/35坐标，可严格分解为 Boolean DNF 分量或稀疏 Harsanyi 项。官方 LExaShap 与 Harsanyi 均在 N=10–64 精确完成。
- H3-S6 诊断：终端状态数为 `product_e(2*3^degree_e-2^degree_e)`，在 G 应用前形成。N=24 的414,736状态属于全局表示瓶颈，不是当前游戏的内在困难。
- 当前判断：原“共同来源 × 联合价值稳定增加成本”未获支持；不再机械扩大原四格。
- 候选新问题：来源图宽/证明交叠的参数化边界；Harsanyi 与 Boolean 编译的优势转换；共享子电路复用；具有真实买方依据的坐标交互图。
- 下一门槛：固定度数、共享企业数、OR 展开量和图宽的正交小型对照；再加入真正利用图宽的 VE/d-DNNF/OBDD 基线。
- 阶段0（2026-11-13）：已冻结35坐标重建保真度 `v_fid`，并冻结省际制造业占比差重建 `v_gap` 作为补充任务。N=12、4096联盟数学审计通过；主值可按坐标精确分解，gap 非 unanimity 且存在跨地区混合差分。价值函数不作为主要创新。
- 阶段1（2026-11-13）：旧 E1 的主保真度产生有效城市/层级差异，gap 仍是省级负对照。新 N=16 严格配对固定35坐标并实现同一 E 跨 PA/PB；来源超图非同构，联盟游戏与 Shapley 改变，但 Harsanyi、DNF计数和width均未增长。
- 阶段2A（2026-11-13）：官方 LExaShap 已从6个 JOIN 见证直接编译正 DNF；`v_fid/v_gap` 通过线性与64见证有限状态分解精确恢复16名玩家 Shapley，最大误差 `1.39e-16`。全局 arithmetic DAG 为26对28，说明相同width不保证相同表示；集中实例反而略小。
- 阶段2B-0（2026-11-14）：4096个重连中288个满足冻结满报表计数，归并为12个非同构代表；全部 incidence/primal treewidth 恒为1/2。协议允许的参考VE在三种预注册顺序下完成36/36独立语义核验。物理E优先顺序放大企业度差异，企业分量顺序将两类最大因子统一为16，触发 `ORDER_EFFECT_DOMINATES_CURRENT_STRUCTURE_EFFECT`。来源—坐标图未提供额外表示解释。
- 当前准入状态：`MOVE_TO_REAL_NONSTAR_PROVENANCE`。2D并入2B并在当前星形F0家族收尾；不扩大N、不增加种子、不自动进入2C/2F。若继续，应先从已有真实数据库或公共基准审计非星形 provenance，不能人工制造无业务依据的桥表或循环JOIN。
- 阶段2B-0证据入口：`IDEA03_shared_lineage_cost/experiments/IDEA03_stage2B0_ordered_structure_gate_v1/`。
- Stage 3A-Q9（2026-11-14）：本地SF0.1 Q9提取402条真实witness。P1完整物理玩家下最大overlap=3、incidence/primal宽度上界=3/4；P2固定PART/SUPPLIER后退化为overlap=1、宽度=1/2。Q9报表兼容但非星形性依赖玩家边界，状态 `Q9_NONSTAR_DEPENDS_ON_PLAYER_BOUNDARY`，未进入Stage 3B。
- Stage 3A-Q9证据入口：`IDEA03_shared_lineage_cost/experiments/IDEA03_stage3A_q9_nonstar_gate_v1/`。
- Stage 3B-1（2026-11-14）：12个官方LExaShap编译与24个VE诊断完成。LExaShap中高重叠H的DAG小于L，VE中H-P1中间因子随m显著增长；方向相反，状态 `REPRESENTATION_DEPENDENT_EFFECT`。L12-P1官方backward另有数值稳定性失败，未进入完整报表G。
- Stage 3B-1证据入口：`IDEA03_shared_lineage_cost/experiments/IDEA03_stage3B1_q9_nonstar_cost_gate_v1/`。
- Numerical Gate（2026-11-14）：解析不相交DNF在N=60独立复现LExaShap异常；输入、标签、wrapper均排除，根因定位为作者N_add浮点反卷积误差经阶乘梯度放大。50/100位同递推恢复并推迟失败边界，状态 `FINITE_PRECISION_FAILURE_SUPPORTED`；未做结构族扩展，不能上升为一般数值稳定性新Idea。证据入口：`IDEA03_shared_lineage_cost/experiments/IDEA03_numeric_gate_lexashap_v1/`。
- Numerical Gate 2（2026-11-14）：反卷积不是N_add数学必需操作；标准prefix/suffix与product-tree sibling product在float64下直接修复N=60，保持效率与对称，且不破坏lifting。成本为有限局部缓存/操作差异，未形成可支持独立研究问题的权衡，状态 `LOCAL_IMPLEMENTATION_CHOICE_ONLY`，该数值方向收尾。证据入口：`IDEA03_shared_lineage_cost/experiments/IDEA03_numeric_gate2_nadd_stability_v1/`。
- 阶段2A证据入口：`IDEA03_shared_lineage_cost/experiments/IDEA03_stage2A_mature_source_compilation_20261113/`。
- 阶段1证据入口：`IDEA03_shared_lineage_cost/experiments/IDEA03_2_cross_region_source_control_v1/`。
- 阶段0证据入口：`IDEA03_shared_lineage_cost/experiments/IDEA03_stage0_fidelity_freeze_20261113/`。
- 历史诊断入口：`IDEA03_shared_lineage_cost/experiments/IDEA03_2_joint_structure_v2/PREVIOUS_EXPLORATION_DIAGNOSIS.md`。
- IDEA-03-2A～2F 的统一谱系与状态入口：`IDEA03_shared_lineage_cost/IDEA03_2A_2F_BRANCH_REGISTRY.md`。这些编号是研究子方向，不等于已经创建六条 Git branch。
- 2026-11-19 最新进展入口：`IDEA03_shared_lineage_cost/IDEA03_2A_2F_LATEST_PROGRESS_20261119.md`。新增分支竞争审计、理论精读和57项原文范围矩阵后，2C/2F 保持优先但需强基线准入；2B/2D 收缩为表示选择问题；2E 与 IDEA-01 的真实价值/支付证据联动。
- 后续候选谱系（尚未自动立项）：2C 承接为 IDEA-03-3-1 部分子 DAG 共享、03-3-2 数值状态复用、03-3-3 多输出 all-player 梯度复用；2F 承接为 03-3-4 多 G 复用及 03-6-1/03-6-2 摊销与增量归因；2B/2D 承接为 03-4-1 表示选择和 03-4-2 混合表示；玩家边界继续拆分为 03-5-1～03-5-3。以上均须通过冻结对象、竞争文献与同目标基线准入后再建实验分支。

## IDEA-04 GNN 学习式贡献估算
- 子问题：能否表达玩家独特的下游来源？是否能在相似报表上摊销训练成本？跨不同来源模式何时失效？
- 既有证据：TPC-H 派生冻结数据、三个 checkpoint、去图边/锚点消融；SF1 同结构规模外推与四个不同结构外部游戏是不同问题。
- 已知限制：玩家节点没有反向消息；训练时数据 SHA-256/commit 不存在；四个外部游戏不支持通用迁移主张。
- 当前状态：独立研究候选；反向边等应作为新的对照实验，不修改已冻结基准。

## IDEA-05 玩家粒度与 owner 直接分配
- 子问题：逻辑事实包、物理事实、owner 直接组成联盟，以及记录 Shapley 事后求和，是哪些不同博弈？
- 既有基础：早期 M2、D1-P 及 P3 的映射与分配结果。
- 当前状态：先核实早期来源与数学定义，再决定是否提升为独立主 Issue。

## 共同约定
任何 Idea 下的多个实验均引用同一个 canonical run ID / 输入版本，不把同一冻结数据复制到不同 Idea 中。关闭被否定的子问题时保留反证和所检验的条件。
