# 文献范围与证据状态

## 1. 当前可确认的文献池

本轮继承三个现有材料池：

1. `tmp/researchlab_v2/workspace/deepread/`：实际发现47个具有 `精读档案_v2.md` 或 Luo 主档案的目录；47项均有 `source.json`、`model_spec.md` 和 `theorem_atlas.md`，其中 QueryGames 缺独立 `证据审计结果.md`，其余46项具有审计文件。
2. `research/IDEA03_theory_extension_deepread_v2/`：Owen、MC-nets、bounded dependency、Comparisons of Signals、Markets for Information 五组理论补充，其中 Owen 仍无正文。
3. `research/IDEA03_story_literature_deepread_v1/`：另有 Blackwell、2D-Shapley、replication-robust analytics markets、Ghorbani--Kim--Zou 的 distributional framework、LMFAO 五项主要依靠 theorem audit 或历史全文审计，尚无独立 Luo 七件套。
4. `research/reading_2026_11_BC/`：11篇 `DOSSIER_FIRST_PASS` 及后续竞争队列。这里与上述目录高度重叠，不能再次累加。

因此，“以前精读了35篇”是较早的历史批次口径。当前系统矩阵登记57个文献实体：47个 Research Lab dossier、5个理论扩展档案、5个故事审计层条目。这个57仍不是“57篇均已人工验收的独立正式论文”：mono/dual/工作论文/预印本/扩展摘要/无全文条目的证据强度不同，且正式唯一文献数仍需以标题、DOI、版本和 PDF 哈希最终去重。本轮不修改历史编号。

## 2. 可以用于图谱的证据

- `FULLTEXT_THEOREM_VERIFIED` / `FULLTEXT_MODEL_VERIFIED`：可用于记录定理或模型边界，但仍应回链到具体档案页码。
- `DOSSIER_FIRST_PASS`：可以作为局限候选来源；视觉、公式、附录或代码未核验项必须保留。
- `METADATA_ONLY` / `PDF_NOT_LOCATED` / `FULLTEXT_UNAVAILABLE`：只能记录“证据缺失”，不能产生理论覆盖结论。
- Flash 的 `DRAFT_MODEL_OUTPUT`：只作检索导航，不能独立产生 `L0_EXPLICIT`。

## 3. 当前证据层次分布

### 有较强本地全文或定理档案

Abbas--Hazen、Blackwell、Faithful GSV、2D-Shapley、两组 Dynamic Shapley、Data Shapley、Distributional Shapley、Green provenance semiring、aggregate provenance、Livshits、Standke--Kimelfeld、Abramovich/LExaShap、Kara model counting、LMFAO、F-IVM、ProvSQL、MC-nets、bounded dependency、Comparisons of Signals、Markets for Information。

“较强档案”不表示所有图表、附录和作者代码均已验收。

### 已有首轮 dossier，但仍有四类核验缺口

Ai、Abbas--Hazen、Cui、SPO、FastSHAP、TN-SHAP-G、Coyle--Manley、Bergemann--Bonatti--Smolin、Ebiele 等 taxonomy、Nagrecha--Chawla、Mandi 等。具体缺口见：

`research/reading_2026_11_BC/10_十一篇档案缺失证据清单_20261113.csv`

### 尚不能进入理论结论

- Owen 1977：`FULLTEXT_UNAVAILABLE`。
- Černý--Grabisch：历史队列中 `PDF_NOT_LOCATED`。
- Bodendorf--Franke：历史队列中 `PDF_NOT_LOCATED`。
- ShaplEIG、Goldwasser--Hooker、RelGNN：队列状态不一致或尚未完成全文审计。

## 4. 本图谱的边界

本版优先覆盖 IDEA-03 当前最相关的价值、玩家、表示和精确计算文献。`03_ORIGINAL_SCOPE_BOUNDARY_MATRIX.csv` 已登记57个文献实体。它是现有本地精读库的结构化证据综合，不是通过外部数据库重新检索形成的系统综述，也不声称已穷尽全部作者局限。没有原文页码的记录不升级为 `L0_EXPLICIT`。

## 5. 作者局限提取进度（2026-11-19）

- 在原先标记 `NOT_YET_EXTRACTED` 的条目中，先选取31篇已有全文审计的论文回到 PDF 讨论、结论和未来工作页。
- 29篇找到了作者明确陈述，其中24篇来自本地原始/作者/会议 PDF，3篇来自 mono/dual 译本附件，2篇来自官方 arXiv 远程原文。
- Distributional Shapley (2021) 与 LensXPlain (2019) 已完成全文关键词和末尾页检查，但未找到可与模型假设明确分开的作者局限段，标记 `SEARCHED_NOT_FOUND`，不据此推断“没有局限”。
- 其余待提取项主要属于 `PARTIAL_FIRST_PASS`、`AUTHOR_VERSION_FIRST_PASS`、故事 theorem-audit 层或无全文层；它们是“证据尚未达到同等级”，不是“尚未精读”的单一含义。
- 逐篇结果见 `07_AUTHOR_EXPLICIT_EXTRACTION_BATCH1.csv`；`03_ORIGINAL_SCOPE_BOUNDARY_MATRIX.csv` 的作者局限状态已同步更新。

