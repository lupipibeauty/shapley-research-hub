# 成熟算法初步覆盖审计

## 1. 判定口径

- `DIRECT`：论文问题对象和输入接口可直接表达冻结任务。
- `EXACT_REDUCTION`：可证明拆为该方法覆盖的组件，但仍需构造与组合。
- `THEORY_ONLY_ADAPTER_MISSING`：理论路线合理，仓库尚无同目标实现。
- `REPRESENTATION_ONLY`：可构造/维护 SQL 来源或报表统计，但不直接给出全玩家标准 Shapley。
- `CURRENT_EVIDENCE_INSUFFICIENT`：本地原文、定理条件或实现证据不足。

## 2. 覆盖矩阵

| 方法/文献 | 主保真度 | 省际 gap | 本地实现证据 | 结论与边界 |
|---|---|---|---|---|
| Livshits 等数据库 Shapley | Boolean CQ/部分聚合分量可直接或经归约处理 | 需先把两个比例差的有限状态函数分解 | 保存的理论审计，无本阶段同目标适配 | `EXACT_REDUCTION`，不是任意多输出 G 的直接接口；必须逐项核对查询层次性、聚合及内生事实前提 |
| Standke & Kimelfeld AggCQ | COUNT DISTINCT、AVG 等在其局部价值与查询前提下有 tractability frontier；可覆盖部分单坐标游戏 | 跨两个地区的联合评分不在当前已核对的直接接口内 | `H3_JV/literature_theorem_audit.csv` 与精读档案；未做新 G 适配 | 主值 `EXACT_REDUCTION/THEORY_ONLY`；gap `CURRENT_EVIDENCE_INSUFFICIENT`，不能只凭“含 AVG/COUNT DISTINCT”宣布覆盖 |
| Abramovich 等 / 官方 LExaShap | 坐标值若展开为 Boolean-number/阈值组件，可逐组件精确求解 | 有限 gap 状态也可展开，但组件数与共享编译待核 | P3 H1/H2、历史 GR/GL/GC 已本地验证；最大误差约 `2.78e-17` | `EXACT_REDUCTION`；新 G 适配尚未执行。官方接口的 d-tree 构建不等于 SQL→lineage 构建免费 |
| Luo et al. 2022 | 只对独立可加输出效用直接；counts/sums 的线性部分可用 | 两省比例差绝对误差非独立可加 | 保存精读；无新 G 运行 | 部分 `DIRECT`、整体 `EXACT_REDUCTION` 或不适用；不能用坐标可加混同记录独立可加 |
| Luo et al. 2024 / simple games | Boolean 门槛或最小获胜联盟组件可用 | 需先离散/门槛分解 | 历史 P3-1C 当时 R1 环境阻塞；后续档案另有复现，版本不可混同 | `EXACT_REDUCTION`；不能直接输入实值 ratio/gap |
| Kara–Olteanu–Suciu | Boolean 函数 Shapley与按基数模型计数互约；d-DNNF 等可求 | 同上，先构造精确 Boolean 组件 | 全文精读；P3/IDEA03 组件路线已有验证 | `EXACT_REDUCTION/THEORY_ONLY_ADAPTER_MISSING`；成熟理论已覆盖 Boolean 核心，阶段1问题是来源编译与组件复用 |
| Green 等 provenance semiring | 能表达正关系查询来源多项式 | 同样可提供来源，不直接计算联合实值评分的 Shapley | 本地精读 | `REPRESENTATION_ONLY` |
| Amsterdamer 等 aggregate provenance | 能携带聚合 provenance/semimodule 信息 | 可作为 ratio 前的 numerator/denominator 来源 | 本地精读 | `REPRESENTATION_ONLY`；不能据此声称全玩家 Shapley 已实现 |
| ProvSQL | 可在 PostgreSQL 中生成 provenance circuit/多项式并支持部分 Shapley 接口 | 任意 G 的同目标 adapter 未验证 | P3 C2 环境为 `ENV_BLOCKED`；未有冻结任务运行 | `REPRESENTATION_ONLY`/部分 Boolean 直接覆盖；当前实现证据不足 |
| F-IVM | 环上的因式化多查询/增量维护，可共享 JOIN/aggregate 中间量 | 可共享构造两个地区 ratio 所需计数，但不直接给 Shapley 权重 | 保存精读；本轮未运行 | `REPRESENTATION_ONLY`；对 IDEA-03-2C/2F 是强竞争设计思想 |
| LMFAO | 理论上属于因式化多输出聚合/共享优化方向 | 可能减少同一 SQL 来源服务多个统计量的重复工作 | 本地仅在 P3 文档中被列名；没有原文精读、定理页码、代码或结果 | `CURRENT_EVIDENCE_INSUFFICIENT`，不得写成已覆盖或已适配 |
| 已保存知识编译文献（d-DNNF/OBDD/宽度） | 编译后的 Boolean/有限状态组件可按基数计数 | 可覆盖 gap 的有限状态展开 | Kara/Amarilli 精读；本地 Reduced ADD 只从真值表构造 | `THEORY_ONLY_ADAPTER_MISSING`；SQL lineage→结构电路的直接编译仍是阶段1验证点 |

## 3. 分量级判断

### 可较直接分解

1. 主保真度的35个坐标可由 Shapley 线性性独立求解后相加。
2. COUNT、COUNT DISTINCT、SUM 在冻结目标下的绝对误差，可利用单调子集输出和有限整数状态处理。
3. ratio/AVG 可保留 numerator/denominator 联合状态，或在有限域上精确分解为 Boolean 指示分量。
4. 历史 G0/G1/GC 已有 Boolean DNF/Harsanyi/LExaShap 证据，但不是新 G 的完成结果。

### 不能声称直接覆盖

1. gap 先联合两个地区比例再取绝对误差；必须给出精确状态或组件归约。
2. 多个坐标共享 SQL lineage 是否能在一次编译中复用，不由 Shapley 线性性自动解决。
3. 生成整张真值表再构造 ROADD 不属于避免联盟枚举的成熟结构算法。

## 4. 阶段0结论

没有证据支持“冻结主保真度超出现有理论”。相反，它的坐标可加结构使大量分量可经成熟方法精确归约。仍值得研究的是同一来源对多统计分量的共享构造/编译，以及来源结构参数怎样影响表示规模；这对应 IDEA-03-2B/2C/2D/2F，而不是把价值函数包装成创新。
