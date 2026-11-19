# 既有实验直接证据

## 1. Stage 2A：成熟来源编译

原始证据：

- `IDEA03_shared_lineage_cost/experiments/IDEA03_stage2A_mature_source_compilation_20261113/00_EVIDENCE_REUSE_AUDIT.md`
- 同目录 `02_SOURCE_AND_NUMERIC_STATE_AUDIT.md`、`03_EXPERIMENT_A_MATURE_COMPILATION.md`、`04_STAGE2A_DECISION.md`
- 实现：`src/run_stage2a.py`；结果：`results/`

已核实：

- 主保真度被拆为 143 个原始布尔分量，规范化后为 65 个不同 complete DNF。
- 补充价值 `v_gap` 的 49 个 DNF 全部命中同实例 `v_fid` 的 complete-key cache。
- 四个游戏值对象与冻结 oracle 的最大绝对误差为 \(1.39\times10^{-16}\)。
- 作者 LExaShap 路径对每个 DNF 构造单个根 `DNFCircuitNode`，调用 `root.value.backward()`，再读取各变量梯度；没有实现多根联合反向传播。
- 已共享的是 Shapley 线性分解和“整个规范化 DNF 相同”的缓存。未实现跨输出 partial sub-DAG、共同数值状态或联合变量顺序。

结论边界：这是“同一布尔分量完全重复时可复用”的直接证据，不是“部分 provenance 相同即可共享全部 Shapley 计算”的证据。

## 2. Stage 2B-0：来源结构与变量顺序

原始证据：

- `IDEA03_shared_lineage_cost/experiments/IDEA03_stage2B0_source_structure_order_gate_v1/04_STRUCTURE_REPRESENTATION_RESULTS.md`
- 同目录 `05_STAGE2B_DECISION.md` 及结果 CSV/JSON。

已核实：4096 次受约束重连产生 288 个合法完整报表计数实例和 12 个非同构代表；incidence/primal treewidth 均固定为 1/2。企业组件顺序把两类实例的最大中间因子都压到 16。该阶段的正确判断是 `ORDER_EFFECT_DOMINATES_CURRENT_STRUCTURE_EFFECT`，且星形族不能检验真实非星形 provenance。

## 3. Stage 3A/3B-1：Q9 玩家边界与表示依赖

原始证据：

- `IDEA03_shared_lineage_cost/experiments/IDEA03_stage3A_q9_nonstar_gate_v1/04_PROVENANCE_STRUCTURE_P1_P2.md`
- 同目录 `07_STAGE3B_GATE_DECISION.md`
- `IDEA03_shared_lineage_cost/experiments/IDEA03_stage3B1_q9_nonstar_cost_gate_v1/04_P1_P2_COST_COMPARISON.md`
- 同目录 `05_LOW_HIGH_GROWTH_COMPARISON.md`、`06_STAGE3B2_GATE_DECISION.md`、`src/run_stage3b1.py`。

已核实：

- P1 全物理玩家：918 名玩家、402 个 witness、每个 witness 5 个玩家、最大重叠 3；incidence/primal 宽度上界为 3/4，并有 primal clique 下界 4，属于真实非星形。
- P2 固定 PART/SUPPLIER：854 名玩家、witness 大小 3、最大重叠 1、宽度 1/2，退化为 forest。
- 同一 SQL 的“非星形性”依赖玩家边界，不能只用查询名称判断。
- 官方 LExaShap 的 H 实例 d-tree/DAG 可能小于 L，而变量消去诊断中 H-P1 中间因子更大；结果为 `REPRESENTATION_DEPENDENT_EFFECT`，不能宣布通用结构瓶颈。

## 4. Numerical Gate

原始证据：

- `IDEA03_shared_lineage_cost/experiments/IDEA03_numeric_gate_lexashap_v1/08_RESEARCH_GATE_DECISION.md`
- `IDEA03_shared_lineage_cost/experiments/IDEA03_numeric_gate2_nadd_stability_v1/07_RESEARCH_GATE_DECISION.md`

已核实：有限精度异常位于 LExaShap `N_add` 的反卷积实现；标准前后缀或乘积树 sibling-product 在 float64 的 N=60 检查中消除了该异常。其研究状态固定为 `LOCAL_IMPLEMENTATION_CHOICE_ONLY`，不是新的理论分支。

## 5. 对本轮的约束

- 不能把 Stage 2A 的 complete-key cache 扩写成 partial-provenance sharing。
- 不能把 Q9 某种表示的增长扩写成查询本身的固有下界。
- 不能再用 E/B/H 星形族检验非星形结构。
- 新 gate 必须固定同一 \((N,Q,G)\) 并与显式输出规模分开计时。
