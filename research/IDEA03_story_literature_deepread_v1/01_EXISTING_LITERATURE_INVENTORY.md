# 现有与补充文献总清单

## 1. 唯一文献 ID

| ID | 文献 | 年份/版本 | 本地证据 | 状态 | 主要故事 |
|---|---|---|---|---|---|
| LIT-001 | Abbas & Hazen, *On the Value of Information Across Decision Problems* | Decision Analysis 22(1), 2025；online 2024；DOI 10.1287/deca.2024.0187 | `tmp/researchlab_v2/workspace/deepread/AbbasHazen2025_ValueInformation/`；Zotero PDF 14页 | `FULLTEXT_THEOREM_VERIFIED`，公式视觉仍有少量复核项 | A1,A3,B1,E1 |
| LIT-002 | Blackwell, *Equivalent Comparisons of Experiments* | Ann. Math. Stat. 24(2), 1953, 265–272；DOI 10.1214/aoms/1177729032 | 正式入口和公开全文入口已核实；本机代理阻止下载 | `FULLTEXT_MODEL_VERIFIED`；原始 PDF 本地化待补 | A2,A3 |
| LIT-003 | Lee et al., *Faithful Group Shapley Value* | NeurIPS 2025, Vol.38；DOI 10.52202/085713-5437；arXiv 2505.19013 | `tmp/researchlab_v2/workspace/deepread/FaithfulGSV_Lee2026/`；作者代码在 `aggregate_report_shapley/external/fgsv/` | `FULLTEXT_THEOREM_VERIFIED` + `SOURCE_CONFLICT`：旧档年份误记2026 | C1,C2,E1 |
| LIT-004 | Liu et al., *2D-Shapley: A Framework for Fragmented Data Valuation* | ICML 2023, PMLR 202:21730–21755 | PMLR 26页官方全文，定义3.1/3.2、定理3.3及附录已定位 | `FULLTEXT_THEOREM_VERIFIED` | C1,C2,E1 |
| LIT-005 | Yang et al., *Dynamic Shapley Computation* | arXiv:2605.20620v1, 2026 | `tmp/researchlab_v2/workspace/deepread/DynamicShapley_Yang2026/`；原始英文PDF 27页 | `FULLTEXT_THEOREM_VERIFIED` | B1,B2,D2 |
| LIT-006 | Falconer, Kazempour & Pinson, *Toward(s) Replication-Robust Analytics Markets* | journal online 2025，正式卷期 2026 5(2):155–170；DOI 10.1287/ijds.2025.0075 | 作者博士论文 Paper B 全文和正式元数据；arXiv:2310.06000 | `FULLTEXT_THEOREM_VERIFIED` + 年份/标题拼写版本说明 | A2,C1,C2 |
| LIT-007 | Ghorbani & Zou, *Data Shapley: Equitable Valuation of Data for Machine Learning* | ICML 2019, PMLR 97:2242–2251 | `tmp/researchlab_v2/workspace/deepread/DataShapley_GhorbaniZou2019/`；PMLR官方全文 | `FULLTEXT_MODEL_VERIFIED` | A1,A3,B1 |
| LIT-008 | Ghorbani, Kim & Zou, *A Distributional Framework for Data Valuation* | ICML 2020, PMLR 119:3535–3544 | PMLR主文与补充材料全文；旧库中的 Kwon 2021 不是本篇 | `FULLTEXT_THEOREM_VERIFIED` | A1,B1,E1 |
| LIT-009 | Coyle & Manley, *What Is the Value of Data?* | Journal of Economic Surveys 38(4), 2024；DOI 10.1111/joes.12585 | `tmp/researchlab_v2/workspace/deepread/CoyleManley2024_ValueData/` | `FULLTEXT_MODEL_VERIFIED`；综述无自有核心定理 | A1,B1,E1 |
| LIT-010 | Xia et al., *Computing Shapley Values for Dynamic Data* | IEEE TKDE 37(6), 2025, 3253–3271；DOI 10.1109/TKDE.2025.3527380 | `tmp/researchlab_v2/workspace/deepread/DynamicShapley_Xia2025/`；原始PDF 18页 | `FULLTEXT_THEOREM_VERIFIED` | D2,B2 |
| LIT-011 | Owen, *Values of Games with a Priori Unions* | 1977 book chapter；DOI 10.1007/978-3-642-45494-3_7 | 目前只有书目信息和历史理论定位 | `FULLTEXT_UNAVAILABLE` | C1,C2 |
| LIT-012 | Ieong & Shoham, *Marginal Contribution Nets* | EC 2005 | 历史审计与公开论文入口 | `FULLTEXT_MODEL_VERIFIED`，本轮未逐页重审 | A3,D1 |
| LIT-013 | Igarashi et al., *Cooperative Games with Bounded Dependency Degree* | P1候选 | 尚未冻结准确版本 | `UNVERIFIED` | A3,D1 |
| LIT-014 | Green, Karvounarakis & Tannen, *Provenance Semirings* | PODS 2007；DOI 10.1145/1265530.1265535 | `tmp/researchlab_v2/workspace/deepread/ProvenanceSemirings_Green2007/` | `FULLTEXT_THEOREM_VERIFIED`（复用历史精读） | A2,C2,D1 |
| LIT-015 | Amsterdamer, Deutch & Tannen, *Provenance for Aggregate Queries* | PODS 2011；DOI 10.1145/1989284.1989310 | `tmp/researchlab_v2/workspace/deepread/ProvenanceAggregate_Amsterdamer2011/` | `FULLTEXT_MODEL_VERIFIED` | A2,C2,D1 |
| LIT-016 | Livshits et al., *The Shapley Value of Tuples in Query Answering* | PVLDB版本以本地档案为准，年份字段仍需书目复核 | `tmp/researchlab_v2/workspace/deepread/Livshits2021_BLKZPMVL/` | `FULLTEXT_THEOREM_VERIFIED` + 书目版本待统一 | D1,D2,E1 |
| LIT-017 | Standke & Kimelfeld, aggregate-CQ Shapley | 2025 | `tmp/researchlab_v2/workspace/deepread/Standke2025_QIH44NZG/` | `FULLTEXT_THEOREM_VERIFIED` | A3,D1,E1 |
| LIT-018 | Abramovich et al., *Advancing Fact Attribution for Query Answering* | PVLDB 2025；DOI 10.14778/3749646.3749670 | `tmp/researchlab_v2/workspace/deepread/Abramovich2025_S5CRW9IE/`；官方适配记录 | `FULLTEXT_THEOREM_VERIFIED` | D1,D2,E1 |
| LIT-019 | Kara, Olteanu & Suciu, *From Shapley Value to Model Counting and Back* | 2024 | `tmp/researchlab_v2/workspace/deepread/Kara2024_FromShapleyModelCounting/` | `FULLTEXT_THEOREM_VERIFIED` | A3,D1,D2 |
| LIT-020 | Schleich et al., *A Layered Aggregate Engine for Analytics Workloads (LMFAO)* | SIGMOD 2019；DOI 10.1145/3299869.3324961 | 历史全文审计，未建独立 Luo 七件套 | `FULLTEXT_MODEL_VERIFIED` | B2,D1,D2 |
| LIT-021 | Kara et al., F-IVM | 2024版本见本地档案 | `tmp/researchlab_v2/workspace/deepread/FIVM_Kara2024/` | `FULLTEXT_MODEL_VERIFIED` | B2,D1,D2 |
| LIT-022 | Sen et al., ProvSQL | 2019 | `tmp/researchlab_v2/workspace/deepread/ProvSQL_Sen2019/`；另有官方 Shapley 文档 | `FULLTEXT_MODEL_VERIFIED` | D1,D2 |
| LIT-023 | Brooks, Frankel & Kamenica, *Comparisons of Signals* | 2024 working paper | 公开入口已知，尚未建立完整定理档案 | `FULLTEXT_DESCRIPTION_ONLY` | A2,A3 |
| LIT-024 | Bergemann & Bonatti, *Markets for Information: An Introduction* | P1候选 | 尚未冻结完整版本 | `UNVERIFIED` | A1,B1,E1 |

## 2. 重要去重和纠错

1. `DistributionalShapley_Kwon2021` 是 Kwon、Rivas、Zou 的 *Efficient Computation and Analysis of Distributional Shapley Values*，不能替代 LIT-008 的 Ghorbani、Kim、Zou 2020 原始框架论文。
2. `FaithfulGSV_Lee2026` 旧目录名和 `source.json` 年份不准确；正式出版为 NeurIPS 2025。旧档不改，新档记录版本冲突。
3. Falconer 文献存在 preprint 标题 `Towards`、正式标题 `Toward`，以及 online 2025 / 卷期 2026 的差异；不是两篇不同论文。
4. Yang 2026 的 D-Shap 与 Xia 2025 的动态数据 Shapley 是不同问题：前者是 player-by-task 矩阵和局部近似/更新，后者针对数据点添加删除的采样更新。

## 3. 现有代码和复现证据

- FGSV 作者代码：`aggregate_report_shapley/external/fgsv/source/Faithful_GSV-main/`；已有复现说明：`aggregate_report_shapley/reports/fgsv_r2_reproduction_and_d1p.md`。
- Abramovich/LExaShap、ProvSQL、F-IVM、LMFAO、P3/H3/H5 等本轮只用于算法边界核对，没有重新运行。
- 本轮没有以旧实验的不同 `N,Q,G` 做性能排名。

