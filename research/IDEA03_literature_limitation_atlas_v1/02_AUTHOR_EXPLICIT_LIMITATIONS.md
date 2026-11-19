# 作者明确局限与未来工作

## 说明

本文件只记录作者在正文、结论或局限章节明确提出的内容。定理假设、实验未覆盖和我们针对 IDEA-03 的判断不放在这里。2026-11-19 已对“有全文审计但尚未单列作者局限”的31篇完成首轮逐页关键词检索与结论页复核；逐篇证据见 `07_AUTHOR_EXPLICIT_EXTRACTION_BATCH1.csv`。

## A. 已有明确原文定位

### Luo et al. (2022), *On Shapley Value in Data Assemblage Under Independent Utility*

- 作者未来方向：在独立效用设置下发展近似方法，以及动态/流式增量 Shapley。
- 原文定位：PDF p.12，结论；本地档案 `Luo2022_TNDCSEUE/精读档案.md` 第6节。
- 注意：这是在独立、非负、逐结果记录可加效用条件内的未来工作，不是任意整表非线性价值的开放声明。

### Abramovich et al. (2025), *Advancing Fact Attribution for Query Answering*

- 作者明确将 AVG 列为聚合扩展方向；正文算法已分别处理 COUNT/SUM 与 MIN/MAX。
- 原文定位：PDF pp.8--9；本地档案第3节。
- 注意：跨统计坐标的任意外部 `G` 并非作者明确未来工作，属于我们的范围推断。

### Ebiele, Bendechache & Brennan (2025), *Quantitative Data Valuation Methods*

- 作者说明检索没有覆盖 Google Scholar 和 SpringerLink。
- 多种科学方法同时出现的论文会被研究者归入判断为最相关的一类，因此分类存在主观归类边界。
- 原文定位：§9.3，PDF p.31；本地档案第5节。

### Mandi et al. (2024), *Decision-Focused Learning*

- 作者提出的后续问题包括鲁棒/风险敏感训练、零阶梯度、理论保证和可信性。
- 原文定位：§7；本地档案第5节。
- 注意：这些问题针对 decision-focused learning，不等于记录联盟分配的开放问题。

### Nagrecha & Chawla (2016), *Quantifying Decision Making for Data Science*

- 作者明确未处理 data aging。
- 外部特征能够覆盖全部实例的假设并不总成立。
- 原文定位：§6，PDF p.15；本地档案第5节。

### Lee et al. (2025/2026), *Faithful Group Shapley Value*

- 作者指出一般效用下的 copier attack 仍未解决。
- `do`-utility 并非总能获得。
- 原文定位：论文结尾；本地档案第7节。出版年份/目录年份仍需以固定英文版统一。

### Jiang et al. (2026), *Ensemble Shapley*

- 作者指出大数据集中的排列位置偏差、噪声分片污染及分片策略设计没有在本文中解决。
- 原文定位：结论/讨论；本地档案第6节。
- 注意：其目标是受限分片排列下的 Ensemble Shapley，不是无条件的标准 Shapley。

### Lei et al. (2025), *FedDSV*

- 作者明确警告：数据高度异质、存在极端数据或参与切换频繁时，SMC 估计偏差可能较大。
- 原文定位：SMC 讨论与实验；本地档案第3、6节。
- 轮权重缺少理论最优准则是档案根据方法结构作出的边界判断，不在本文件冒充作者原句。

### Joseph, Song & Chaudhury (2026), fair revenue compensation

- 作者指出特征互补、产生 superadditive accuracy 的情形尚未处理。
- 原文定位：3页扩展摘要未来方向；本地档案第3节。
- 证据限制：只有扩展摘要，没有完整证明或实验。

### Caglio & Mayhew (2016), *Equity Trading and the Allocation of Market Data Revenue*

- 作者强调 ETF 特殊性、交易者构成、市场份额和新 NBBO 激励会限制事件结果解释。
- 原文定位：工作论文的事件研究讨论；本地档案第4节。
- 注意：该文识别的是收入规则对交易行为的影响，不是记录级分配算法。

### RSS / Alizad & Milani (2025)

- quantile stratification 在当前版本中仍是未来提议，未形成已经验证的复杂度或实验结论。
- 原文定位：arXiv v1 讨论；本地档案第6节。

### Faithful GSV、ASSS、Efficient Sampling 的版本限制

- 这些档案分别使用 dual/mono 版本；“需要核对单语英文原版和公式常数”是本项目证据限制，不是作者局限。
- 因此不将其列为论文未来工作，只保留在证据状态矩阵中。

## B. 本批回到原文后新增的作者明确局限

### B.1 数据价值、分配与市场

- **Data Shapley**：作者限定为监督学习训练集，承认隐私、个人关联和完全补偿问题未被框架捕捉，并提出研究其他价值公理及对学习函数/指标的敏感性（PDF p.8；当前为 mono 译本，正式引文需核英文原版）。
- **Beta Shapley**：大规模算法和如何按任务/分布选择最优权重仍是未来问题；附录还指出一个渐近上界条件未知（pp.9, 14）。
- **Badewitz et al.**：已知线性模型、不相关预测变量和监督学习限制；探索式分析、安全与隐私未内生（p.9）。
- **Dawande et al.**：数据合作社扩张、相关数据质量及更复杂多维机制的结构分析仍待研究（pp.29, 50）。
- **Galperti et al.**：平台私下改变数据库、行动约束和缺乏承诺等扩展仍开放；规范性赔偿不属于本文回答范围（pp.15, 17, 25--26）。
- **Comparisons of Signals**：其他信号关系、它们的决策/博弈基础以及获取信号成本如何建模仍开放（pp.21--22）。
- **Markets for Information**：信息中介的最优信息政策、数据供给竞争、隐私和产业组织后果仍大幅开放（pp.9, 20--21）。

### B.2 数据库归因、定价与来源

- **Deutch et al.**：PQE 到 Shapley 的一般反向归约、聚合、否定与更细 bag multiplicity 是明确开放方向（§7；远程 arXiv 原文）。
- **Banzhaf Values for Facts**：聚合/否定、更高可扩展性以及推广到 Shapley、SHAP 和因果度量是未来工作（§7；远程 arXiv 原文）。
- **Livshits et al. / Query Games**：一般 hierarchical CQ 上其他聚合查询的 Shapley 复杂度仍开放（Livshits p.14；Query Games p.6）。
- **Standke--Kimelfeld**：非 localized value、更广聚合函数类别及 numerical aggregate attribution 的理性公理是作者明确研究议程（pp.3, 16, 18）。
- **Kara--Olteanu--Suciu**：作者猜想概率数据库 UCQ dichotomy 可推广到 Shapley（p.16）。
- **Karmakar et al.**：其他 coefficient functions 的归约和 expected Shapley-like scores 的近似算法仍待研究（pp.9, 18）。
- **Dosso et al.**：非单位输出信用、非均匀作者分配，以及把信用用于查询定价和数据缩减是未来工作（p.47）。
- **Li--Miklau**：固定数据库、不发布修订和忽略串谋是明示假设；作者拟研究更广查询、近似答案定价和更多 PTIME 情形（pp.2, 6）。
- **ProvSQL**：SQL 子查询、外连接、嵌套聚合、递归查询及 safe-plan intensional 化仍未完成；其附录语义明确不处理 NULL（pp.12, 15）。
- **Green et al. / aggregate provenance**：否定、更多 c-table/半环、其他数据模型和应用，以及聚合 provenance 在更多任务中的使用被明确列为后续方向（Green pp.9--10；Amsterdamer pp.3, 12）。

### B.3 查询维护、解释与抽样

- **DBSP**：嵌套关系内部结构的增量定义与完整系统评估留待未来（pp.10--11）。
- **F-IVM**：单线程、并行/分布式实现、更多 SQL 算子、概率图推断和复杂 ML 是明确限制/方向（p.25）。
- **Dynamic Shapley**：一般任务尚未达到实时计算，作者提出在特定任务中结合 IVM（p.17）。
- **ASSS**：联合优化层数和层内样本量是未来方向（p.24；dual 版本）。
- **Efficient Sampling**：CCB 开销、近似 CCB、动态玩家和不确定效用是未来问题（p.22；mono 版本）。
- **Scorpion**：自动属性选择、提前剪枝和并行化仍待实现（pp.8, 11）。
- **Qin 综述**：高效低方差抽样、深度/混合模型、多智能体公平和数据资产交易被列为未来方向；这些是综述判断，不是原始定理（pp.3--8, 18）。

### B.4 紧凑博弈与知识编译

- **MC-nets**：等价玩家类、函数式边际贡献和互斥规则语义是作者提出的三个扩展（pp.9--10）。
- **Bounded Dependency Degree**：向 nucleolus、kernel、bargaining set 和其他紧凑博弈类扩展（p.8）。
- **Amarilli et al.**：SDD/d-SDNNF/OBDD 关系、非结构化 d-DNNF、非完整电路宽度及更一般语言是明确开放问题（pp.33, 43）。

## C. 已搜索但未找到独立作者局限段落

- **Distributional Shapley (2021)**：原始 PDF 全文和末尾页已检索，未找到可与模型假设清楚分开的 limitations/future-work 段落。
- **LensXPlain (2019)**：4页系统论文全文已检索，未找到作者单列的 limitations/future-work 陈述。

这里的 `SEARCHED_NOT_FOUND` 只表示本轮没有找到作者明确自述，不表示论文没有范围边界。两篇的假设、目标和实验范围仍在 `03_ORIGINAL_SCOPE_BOUNDARY_MATRIX.csv` 中。

## D. 仍待提取或无法进行作者局限整理

- Owen (1977)：正文未取得，当前只能保留 `FULLTEXT_UNAVAILABLE`。
- 仅有元数据或尚未完成全文审计的 Černý--Grabisch、Bodendorf--Franke、ShaplEIG、Goldwasser--Hooker、RelGNN：不得根据标题生成作者局限。
- 其余 `PARTIAL_FIRST_PASS`、`AUTHOR_VERSION_FIRST_PASS` 和故事审计层条目仍然是“已记录模型边界，但尚未完成同等级作者局限提取”，不能与上面31篇的完成状态混为一谈。

