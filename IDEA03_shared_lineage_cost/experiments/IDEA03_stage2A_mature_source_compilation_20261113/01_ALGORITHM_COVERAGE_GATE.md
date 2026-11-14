# 01 成熟算法覆盖门槛

## Material Passport

- 状态：`COVERAGE_AUDITED / ONE_MATURE_PATH_EXECUTED`。
- 已执行路径：官方 LExaShap `DNFCircuit`。
- 未执行路径：OBDD/MTBDD、d-DNNF/SDD、通用 VE、ProvSQL、LMFAO、F-IVM。

## 1. 覆盖矩阵

| 方法 | 输入/来源构造 | 多输出与按基数计数 | 冻结实值 G | 状态 | 具体证据与边界 |
|---|---|---|---|---|---|
| 官方 LExaShap | 接受正 DNF；不要求先枚举联盟；SQL witness→DNF需适配层 | 给定 d-tree 可一次 backward 得到全部变量 Boolean Shapley；作者接口为单根，未提供部分跨根 DAG 共享 | COUNT/SUM可线性拆分；ratio/gap需有限状态精确归约 | Boolean `DIRECTLY_SUPPORTED`；冻结G `EXACT_ADAPTATION_POSSIBLE`且本轮已验证 | 作者 `README.md` 明示 SPJU 输入为 list-of-sets DNF、SUM/COUNT为DNF与系数列表；本地精读记录 Theorem 3.6（p.7）：给定 d-tree，全变量 Shapley 为 `O(|T||vars(T)|^2)`；不含 grounding/编译成本 |
| d-tree + Shapley模型计数 | Boolean来源可按分解树编译 | 支持按联盟基数计数和全变量 Shapley | 需先做本轮相同的精确分量归约 | `EXACT_ADAPTATION_POSSIBLE` | Kara–Olteanu–Suciu：命题2.3/式(2)按联盟大小计数；定理4.1在确定可分解电路上为FP，见 `tmp/.../Kara2024_FromShapleyModelCounting/theorem_atlas.md` |
| OBDD/MTBDD | 可从Boolean/有限状态函数编译；顺序是显式因子 | 多根/共享DAG在语言层面可表达 | ratio/gap可做有限状态终端，但需要适配 | `THEORY_COVERED_IMPLEMENTATION_MISSING` | Amarilli等精读 p.22–24 给出有界pathwidth到uOBDD、treewidth到d-SDNNF的单指数宽度上界；本地无可复现 OBDD/MTBDD 包，且本轮禁止新写通用编译器 |
| d-DNNF/SDD | Boolean lineage可编译到确定分解电路 | 编译后支持模型计数；多输出共享取决于实现 | 同样需实值分量归约 | `THEORY_COVERED_IMPLEMENTATION_MISSING` | Kara定理4.1与Amarilli知识编译审计提供理论覆盖；本地没有冻结任务适配器或作者可运行工具 |
| Variable Elimination | 可从6个见证因子直接消元；顺序可控制frontier | 可保留多个输出/统计状态，但是否共享取决于因子设计 | 可维护 numerator/denominator 等有限状态 | `THEORY_COVERED_IMPLEMENTATION_MISSING` | 阶段1只算了 min-fill width 上界，没有同目标成熟 VE 实现；不能把 width=2 直接当作整个实值游戏宽度 |
| Livshits 等层次CQ计数 | 层次 Boolean CQ 可直接按联盟大小计数 | 单查询目标；不是通用35输出接口 | SUM等部分坐标可线性归约；ratio/gap非直接接口 | `EXACT_ADAPTATION_POSSIBLE` | Theorem 9/11 与 Eq.(4)；聚合扩展见 Theorem13、Corollary15。当前物理玩家/整表G仍需逐分量证明 |
| Green来源半环 | 正关系查询来源多项式 | 可共享来源表达，不直接给全玩家Shapley | 不直接支持任意ratio/gap评分 | `REPRESENTATION_ONLY` | `tmp/.../ProvenanceSemirings_Green2007/`；提供来源语义，不是Shapley求解器 |
| Amsterdamer聚合来源 | 可携带聚合及numerator/denominator来源 | 可为多个聚合提供表达 | 不直接输出标准Shapley | `REPRESENTATION_ONLY` | `tmp/.../ProvenanceAggregate_Amsterdamer2011/`；本轮将其作为状态表示参照，不声称已求解 |
| ProvSQL | 可从SQL生成provenance电路/概率表示 | 实际共享取决于数据库扩展 | 冻结G适配未验证 | `ENV_BLOCKED` | 历史P3 C2无可用本地服务环境；`ProvSQL_Sen2019`精读明确“来源电路可构造不等于Shapley已支持” |
| F-IVM | 因式化 variable order、ring与共享视图维护 | 强项是多统计量/更新共享 | 不直接维护所有联盟Shapley | `REPRESENTATION_ONLY` | Kara等（2024）精读：p.4–8 因式化视图与delta传播；论文没有玩家或Shapley对象 |
| FAQ/LMFAO | 理论上面向多聚合共享 | 可能覆盖多输出共同子计算 | 无冻结G直接接口证据 | `EVIDENCE_INSUFFICIENT` | 当前精读库没有足够原文定理、接口和同目标运行证据，不能写成已覆盖 |

## 2. 十项接口问题的执行结论

1. Boolean来源：官方 LExaShap接受正 DNF。
2. 联盟枚举：不需要；本轮编译输入只有6个见证及其精确分量。
3. SQL witness：需要最小转换；本轮直接由 E/B/H 玩家三元见证生成 DNF。
4. 固定变量顺序：作者 `DNFCircuit` 不暴露该参数，记为 `INPUT_UNSUPPORTED_AUTHOR_INTERFACE`。
5. 多根输出：作者接口逐根编译；本轮外层适配可缓存完整相同 DNF。
6. 部分共同子表达式：作者分量内部会 lifting/d-tree 分解，跨输出部分子图不共享。
7. 按联盟基数：`Value.prob` 和梯度使用按变量数分层的向量；Kara命题2.3给出一般按大小计数关系。
8. 全玩家精确 Shapley：支持；本轮每个Boolean分量与独立枚举一致，完整G与16玩家oracle一致。
9. 实值聚合/ratio/gap：线性聚合直接分解；ratio/gap通过6见证有限状态 Möbius 精确展开为带符号系数的正 DNF 指示量。
10. 已有保证：作者 Theorem3.6保证给定 d-tree 后的全变量计算；Kara定理4.1覆盖确定分解电路。两者都不把 SQL grounding、数值状态构造和跨输出复用视为免费。

## 3. 门槛判断

存在一条本地可复现的成熟路径，因此没有以“环境阻塞”为由停止全部实验。该路径足以完成实验A和冻结G同目标求解，但不足以回答固定变量顺序与部分跨输出DAG共享；这两个缺口保留为接口缺口，不升级为理论创新缺口。

