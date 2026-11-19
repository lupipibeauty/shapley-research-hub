# RUN REGISTRY

## 审计运行

| 日期 | 类型 | 操作 | 状态 |
|---|---|---|---|
| 2026-11-17 | 只读本地审计 | 读取 Stage2A、Stage2B0、Stage3A、Stage3B1、Numerical Gate 1/2 报告、代码与结果索引 | `COMPLETE` |
| 2026-11-17 | 本地文献审计 | 读取 Livshits、Standke--Kimelfeld、Abramovich、Green、Amsterdamer、ProvSQL、F-IVM、Kara、knowledge compilation 精读档案 | `COMPLETE` |
| 2026-11-17 | PDF 预检 | Livshits、Standke、Abramovich extended、Green、Amsterdamer、ProvSQL | `PASS` |
| 2026-11-17 | PDF 预检 | Kara--Olteanu--Suciu 2024 本地 PDF | `UNAVAILABLE_MALFORMED_POINTERS` |
| 2026-11-17 | 原文补检 | LMFAO、MC-nets、bounded dependency、Baur--Strassen、ProvSQL Shapley API | `COMPLETE` |
| 2026-11-17 | 新 Shapley 实验 | 未执行 | `NOT_RUN_BY_DESIGN` |

## 检索范围与查询

先查本地 Zotero/精读库/历史实验，再用互联网补齐原始论文和官方文档。主要检索式：

- `LMFAO layered aggregate engine multi-output aggregate sharing`
- `Marginal Contribution Nets Shapley linear input size`
- `Cooperative Games bounded dependency degree Shapley theorem`
- `Baur Strassen all partial derivatives complexity PDF`
- `ProvSQL shapley_all_vars token`

数据库/站点：本地 Zotero、项目 deepread 库、ACM/作者 PDF、AAAI 官方 PDF、Microsoft Research、ProvSQL 官方文档。未声称系统综述或穷尽性检索。

## 核心原文

- Green, Karvounarakis, Tannen. *Provenance Semirings*. PODS 2007.
- Amsterdamer, Deutch, Tannen. *Provenance for Aggregate Queries*. PODS 2011.
- Livshits et al. *The Shapley Value of Tuples in Query Answering*. ICDT 2020.
- Standke, Kimelfeld. Aggregate-query Shapley paper. PACMMOD 2025, DOI 10.1145/3767720.
- Abramovich et al. *Advancing Fact Attribution for Query Answering: Aggregate Queries and Novel Algorithms*. PVLDB 18(11), 2025, DOI 10.14778/3749646.3749670.
- Kara, Olteanu, Suciu. *From Shapley Value to Model Counting and Back*. PODS 2024.
- Schleich et al. *A Layered Aggregate Engine for Analytics Workloads*. SIGMOD 2019, DOI 10.1145/3299869.3324961.
- Ieong, Shoham. *Marginal Contribution Nets*. EC 2005, DOI 10.1145/1064009.1064030.
- Igarashi, Izsak, Elkind. *Cooperative Games with Bounded Dependency Degree*. AAAI 2018, DOI 10.1609/AAAI.V32I1.11475.
- Baur, Strassen. *The Complexity of Partial Derivatives*. TCS 22, 1983.

## 在线原文入口

- LMFAO: https://doi.org/10.1145/3299869.3324961
- MC-nets PDF: https://www.microsoft.com/en-us/research/wp-content/uploads/2005/01/ieong05mcnet.pdf
- Bounded dependency PDF: https://cdn.aaai.org/ojs/11475/11475-13-15003-1-2-20201228.pdf
- ProvSQL Shapley docs: https://provsql.org/docs/user/shapley.html
- Baur--Strassen PDF: https://web.vu.lt/mif/s.jukna/tropical/Baur-Strassen.pdf

## 未核实项

- Kara et al. 2024 的本地 PDF 视觉页码需换一份有效 PDF 后复核；当前只使用已保存全文提取中的定理定位。
- 未发现 Standke--Kimelfeld 针对“异构完整报表联合状态”的作者实现。
- 未发现 Abramovich/ProvSQL 的多 root、显式 M×N 联合 Shapley API。

## 写入

本轮只新增 `research/IDEA03_3_branch_audit_20261114/` 下的审计文件与 PDF 预检记录；未执行 `git add`、`commit` 或 `push`。
