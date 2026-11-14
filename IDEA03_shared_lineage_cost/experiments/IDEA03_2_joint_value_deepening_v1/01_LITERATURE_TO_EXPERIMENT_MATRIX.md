# 01 文献—算法—实验对应矩阵

## 证据口径

本轮不是重新摘要全部文献，而是从本地精读库筛出 11 项与 `Q → provenance → G → Shapley` 直接相关的工作。`FULL_TEXT_AUDITED` 表示已有原文精读档案，但仍不等于研究者人工验收；作者代码是否实际运行另列。主要索引为 `tmp/researchlab_v2/workspace/deepread/回溯精读质量审计_20261105.md` 与各论文目录的 `精读档案_v2.md`。文献流程参照 Kassis et al. (2026), *Scientific Agent Skills*（arXiv:2609.00065），该引用只说明流程，不作为数据库 Shapley 结论的证据。

|论文|原文结论/严格条件|可利用结构|作者实验方法|本轮映射|证据状态|
|---|---|---|---|---|---|
|Livshits et al. (2021), *The Shapley Value of Tuples in Query Answering*|Boolean CQ 的 hierarchical/非 hierarchical 分界；按联盟大小计数；部分 SUM/单原子 MIN/MAX 扩展|固定查询结构、内生/外生 tuple、cardinality-conditioned counting|理论与小例子为主|审查 F0/F1/F2 的 fact-level 玩家和局部查询是否落在既有前沿；不覆盖任意多坐标 G|`FULL_TEXT_AUDITED`，本地档案 `deepread/Livshits2021_BLKZPMVL/精读档案_v2.md`|
|Standke & Kimelfeld (2025), Aggregate CQ Shapley|对 MIN/MAX/COUNT DISTINCT/AVG/quantile 给出不同层次条件；定理条件是固定 AggCQ 的局部聚合|聚合类型与查询层次共同决定状态|理论归约与局部 DP|证明 COUNT DISTINCT、SUM、比例不能被当作同一线性对象；整表 G 需另证|`FULL_TEXT_AUDITED`，`deepread/Standke2025_QIH44NZG/精读档案_v2.md`|
|Kara, Olteanu & Suciu (2024), *From Shapley Value to Model Counting and Back*|Boolean 函数 Shapley 与按大小模型计数多项式互约；确定可分解电路可复用|Boolean lineage、deterministic/decomposable circuit|理论与构造|支撑把冻结比值域展开成 Boolean 阈值分量；不直接覆盖实值 G|`FULL_TEXT_AUDITED`，`deepread/Kara2024_FromShapleyModelCounting/精读档案_v2.md`|
|Abramovich et al. (2025), *Advancing Fact Attribution…*|给定 d-tree 后全变量 Shapley 递推；COUNT/SUM 线性组合可处理；AVG 列为未直接覆盖对象|lifting、d-tree、共享梯度、Boolean-number pairs|Academic/IMDB/TPC-H/ProvSQL；与 LExaShap 等比较|官方 LExaShap 作为 Boolean 分量求解器；比值先由本轮证明转换|`FULL_TEXT_AUDITED + OFFICIAL_CODE_VERIFIED_LOCAL`，源码 SHA 见 canonical run manifest|
|Luo et al. (2022), independent utilities|独立非负 tuple utility 下，结果价值可按独立效用组合|独立结果 utility|作者算法与数据库实例|仅能覆盖 G0 中真正线性的分量，不能直接覆盖门槛×比例|`LOCAL_AUDITED/HUMAN_REVIEW_REQUIRED`，知识库核心证据矩阵；本轮未重新精读|
|Green et al. (2007), provenance semirings|`N[X]` 的普适同态性质；JOIN/UNION/投影的代数传播|tuple 变量、多项式 provenance|理论示例|定义 JOIN witness 与来源变量；不提供 Shapley 权重|`FULL_ORIGINAL_AUDITED`，`deepread/ProvenanceSemirings_Green2007/精读档案_v2.md`|
|Amsterdamer et al. (2011), aggregate provenance|SUM/COUNT 等需要 semimodule/张量式聚合来源，不能只保留 Boolean 出现|数值聚合与 provenance 联合状态|理论与示例|说明比值至少保留 `(M,W)`，不能只保留最终比例|`FULL_TEXT_AUDITED`，`deepread/ProvenanceAggregate_Amsterdamer2011/精读档案_v2.md`|
|Amarilli et al. (2020), knowledge compilation/width|不同电路类与 primal/incidence width 的上、下界关系；启发式宽度不是精确复杂度证明|OBDD/FBDD/d-DNNF 与宽度|理论|规定必须报告实际节点/状态，不能只贴“复杂”标签|`FULL_TEXT_AUDITED`，`deepread/KnowledgeCompilation_Amarilli2020/精读档案_v2.md`|
|Kara et al. (2024), F-IVM|环上的因式化视图与 delta 维护减少重复聚合|变量顺序、共享中间因子|多类分析查询与更新实验|提示共享编译机会；不等于已经计算所有玩家 Shapley|`FULL_TEXT_AUDITED`，`deepread/FIVM_Kara2024/精读档案_v2.md`|
|Sen et al. (2019), ProvSQL|SQL grounding 与 provenance circuit 的工程实现；编译本身可能成为成本|PostgreSQL 查询改写、provenance circuit|TPC-H 启发性能实验|用于分离 source construction 与 Shapley solve；不是任意 G 求解器|`FULL_TEXT_AUDITED`，`deepread/ProvSQL_Sen2019/精读档案_v2.md`|
|Luo et al. (2024), simple-game synthesis/RDSV|给定最小获胜联盟的单调二值简单博弈可分解；非二值效用不自动覆盖|最小联盟与垂直/水平分解|作者 Rust 实现已在 P3 路线审计|门槛分量可借鉴；比例与实值联合 G 需额外转换|`PARTIAL_REAUDIT/HUMAN_REVIEW_REQUIRED`，`knowledge_base/理论与算法覆盖矩阵.md`|

## 对实验设计的直接约束

1. 文献已解决的是若干 Boolean、局部聚合或给定电路的精确计算条件，不是“任意 35 坐标整表价值”的统一求解。
2. 本轮必须把比值转换步骤单独计时；若转换后的 Boolean 分量规模小，不能把 G2 描述成新困难类。
3. 官方 LExaShap 只接收转换后的 Boolean DNF 分量；适配器正确性必须由同一 `(N,Q,G)` oracle 核验。
4. F-IVM/ProvSQL 给出共享来源与预处理基线，但没有直接输出当前记录游戏的 Shapley 向量。

