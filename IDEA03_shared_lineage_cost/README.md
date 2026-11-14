# IDEA03：共享来源、联合成本与价值边界

## 1. 研究问题

当多个报表结果共享来源记录、见证或中间计算时，玩家贡献是可加的，还是必须使用联合价值函数？共享来源带来的计算节省是否会改变收益分配对象？

## 2. 探索过的方向

H3、H5 及层次汇总实验观察了联合状态、层次结构和报表聚合；P2 的来源／层次／价值因素提供了实验材料；部分精确复现涉及共享 witness 或多个结构表示。但这些实验并非都以“共享来源成本边界”为唯一自变量。

## 3. 实验设计与目的

最小设计是 2×2：witness 关系取独立／共享，价值函数取可加／联合。四个单元固定玩家绑定、查询语义、数据规模、精确 oracle 和评价指标，比较贡献分解、效率性、运行成本和共享项的边际变化。

## 4. 实际完成度（2026-11-13）

IDEA-03-2 已建立独立 V2 实验，并实际执行 E0、E1 和 E2 资源门。E0 在 N=10、16 完成全部联盟 SQL/独立 evaluator/H3-S6 对 oracle 核验；E1 在三个 N=20 独立配对实例上完成 Low/High × Add/Joint，以及 local/cross 两组价值。E2 在首个 N=24 配对上触发非枚举基线的结构状态上限，按协议停止，没有进入 E3/E4。

当前结论是否定/未证实，而不是成功创新点：N=20 的跨地区成本交互两正一负，方向不稳定；N=24 的资源阻塞对 Low/High、Add/Joint 均相同。补充诊断进一步证明基础 lineage 的 incidence/primal treewidth 恒为1/2，G 只使用2/35坐标；官方 LExaShap 布尔分量与稀疏 Harsanyi 在 N=10–64 均精确完成。因此 H3-S6 的 N=24 阻塞属于全局 evidence-state 表示问题，不能归因于游戏内在困难。完整档案在 `experiments/IDEA03_2_joint_structure_v2/`。

## 5. 停止／阻塞原因

现有 H3-S6 evidence-state 基线在 N=24 的 AD 层达到414,736个状态，超过冻结上限300,000；闭式规模为 `product_e(2*3^degree_e-2^degree_e)`，在 G 应用前形成。LExaShap Boolean 分量适配现已完成并通过同目标核验，但真正利用图宽的通用 d-DNNF/VE/MTBDD 适配仍缺失。原四格不应扩大；下一步应改变来源图宽、证明交叠或有应用依据的价值交互结构。

## 6. 下一步边界

本轮已停止。若后续继续，先适配一种不同家族的成熟同目标精确方法，并对 N=20 分开执行独立结构重复与3–5次计时重复；未通过该门槛前不启动 E3。不得把 witness-state 报表核验压缩包装成新的 Shapley 算法。

## 7. 2026-11-13 联合价值与共享编译后续

新档案位于 `experiments/IDEA03_2_shared_compilation_tpch_v1/`。本轮证明历史 G1 在阈值1下与纯比例价值严格等价；建立 k=2 的 N=12 游戏并完成4096联盟 SQL 核验；补齐 ROADD 的按联盟大小精确 Shapley DP；在一个受控配对上比较官方 LExaShap、完整分量缓存、共享 ADD 与合并 Harsanyi；并使用 TPC-H SF0.1 原生主外键建立自然/高共享两个 N≤16 样本。

当前判断仍不是算法创新成立：k=2 GC 在最小夹具上退化为满联盟游戏；合成 E1 只改变同省城市分布，没有形成跨省共同来源；共享 ADD 虽精确但冷构造慢，官方完整分量缓存只带来很小的冷端到端改善。下一步必须先构造固定状态和证明数的真正跨省共享配对，再判断多输出共享编译是否有剩余空间。

## 8. 2026-11-13 阶段2A成熟来源编译门

档案位于 `experiments/IDEA03_stage2A_mature_source_compilation_20261113/`。本轮只复用阶段1的两个严格 N=16 配对，从6个 JOIN 见证直接构造正 DNF，并使用官方 LExaShap d-tree；全联盟表只作事后 oracle。28个 COUNT/SUM 坐标经线性归约，7个 ratio 和省际 gap 经64个见证状态的精确 Möbius 分解，四个游戏—价值对象均恢复全部16名玩家 Shapley，最大误差 `1.39e-16`。

成熟作者表示区分了两个相同 width=2 的来源：全局 arithmetic DAG 为26对28，四个企业分量合计24对26；集中度更高的实例反而略小。但作者接口不接受外部变量顺序，也不共享跨输出的部分公共子图。当前结论是 `STAGE2A_COMPLETED_STAGE2B_NOT_STARTED`：完整相同 DNF 缓存已被成熟方法覆盖，ordered compiler 与部分子表达式共享仍需研究者另行批准后核验，不进入规模扩张。

## 9. 2026-11-14 阶段2B-0有序结构门

档案位于 `experiments/IDEA03_stage2B0_ordered_structure_gate_v1/`。在不重跑联盟oracle和LExaShap的前提下，系统枚举了4096个 `B.eid` 重连，得到288个满足冻结满报表计数的赋值及12个非同构代表。全部代表的 incidence/primal treewidth 恒为1/2，只分为3/1/1/1与2/2/1/1两种企业度序列。

本地没有满足外部变量序门槛的成熟编译器，因此按协议使用明确标记的教科书式 VE 参考诊断器；36次运行均与独立DNF容斥计数一致。物理E优先顺序会把集中实例最大因子放大到1024对128，但企业分量顺序把两类都降至16，说明顺序效应主导。阶段2A的作者DAG 26/28方向不能作为固定顺序规律复现；来源—坐标图也未增加表示解释力。2D并入2B收尾，正式判断为 `MOVE_TO_REAL_NONSTAR_PROVENANCE`，但本轮未自动进入下一阶段。

## 10. 2026-11-14 Stage 3A-Q9玩家边界审计

档案位于 `experiments/IDEA03_stage3A_q9_nonstar_gate_v1/`。在本地TPC-H SF0.1上按现有Q9条件提取402条真实witness、52个PARTSUPP pair。P1将PART、SUPPLIER、PARTSUPP、LINEITEM、ORDERS均作为物理玩家，出现1,559对共享3个玩家的witness，incidence/primal宽度上界为3/4；P2固定PART/SUPPLIER后，最大overlap降为1，宽度退回F0同级1/2。Q9可以自然形成Global–RegionKey–Nation × Year的多指标报表，但强非星形结论依赖完整主数据玩家边界。最终状态为 `Q9_NONSTAR_DEPENDS_ON_PLAYER_BOUNDARY`，未批准自动进入Stage 3B。

## 11. 2026-11-14 Stage 3B-1精确表示成本门

档案位于 `experiments/IDEA03_stage3B1_q9_nonstar_cost_gate_v1/`。冻结Q9-L/Q9-H前4、8、12条及P1/P2，共运行12个官方LExaShap编译和24个参考VE诊断。官方算术DAG中H比L更小（P1在m=12为54对73），而合理顺序VE中H-P1最大因子随m增长为128、512、8192，L-P1始终为64；顺序可降低但不能消除VE差异。两种表示对H/L方向相反，判断为 `REPRESENTATION_DEPENDENT_EFFECT`。另有L12-P1官方backward数值失稳，只有11/12通过效率核验。未批准Stage 3B-2或完整报表G。

## 12. 2026-11-14 LExaShap Numerical Gate

档案位于 `experiments/IDEA03_numeric_gate_lexashap_v1/`。纯解析族 `m` 个互不相交五变量子句在 `N=60` 独立复现了历史错误，排除了Q9、SQL、玩家映射和本地wrapper。错误首次出现在作者 `N_add._backward()` 的浮点反卷积，随后被阶乘梯度放大；50位与100位同递推恢复N=60，50位把loose failure推迟到N=100。最终状态为 `FINITE_PRECISION_FAILURE_SUPPORTED`，但尚未达到结构依赖或一般数值稳定性研究问题准入门，本轮按提前停止规则收口。

## 13. 2026-11-14 LExaShap Numerical Gate 2

档案位于 `experiments/IDEA03_numeric_gate2_nadd_stability_v1/`。数学审计确认 `N_add` 需要的是其余child不满足分布的sibling product，并不要求反卷积。独立prefix/suffix和product-tree诊断路径均在普通float64下把N=60恢复为每人1/60、效率和1、对称差0；product tree在失败点约为当前1.55倍系数级操作，未观察到墙钟惩罚，也不改变lifted d-tree。结合标准算术电路反向微分和scan技术，最终判断为 `LOCAL_IMPLEMENTATION_CHOICE_ONLY`，数值稳定性方向停止，不进入结构族扩展。
