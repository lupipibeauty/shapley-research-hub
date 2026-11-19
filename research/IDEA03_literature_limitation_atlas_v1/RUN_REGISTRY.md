# Run Registry

| 日期 | 操作 | 输入 | 输出 | 状态 |
|---|---|---|---|---|
| 2026-11-19 | 继承并去重检查现有批次口径 | `IDEA03_story_literature_deepread_v1`、`reading_2026_11_BC`、`IDEA03_theory_extension_deepread_v2` | `01_CORPUS_SCOPE_AND_EVIDENCE_STATUS.md` | COMPLETE_WITH_IDENTITY_GAPS |
| 2026-11-19 | 建立局限证据等级与首版图谱 | 现有全文档案、theorem audit、dossier 缺口清单、覆盖矩阵 | `LITERATURE_LIMITATION_ATLAS.csv` | FIRST_PASS |
| 2026-11-19 | 跨论文接缝整理 | 价值、玩家、表示、计算四层材料 | `CROSS_PAPER_THEORY_TENSIONS.md` | FIRST_PASS_NO_NOVELTY_CLAIM |
| 2026-11-19 | 建立研究者主体记录模板 | R1--R12 历史候选及用户主体性要求 | `RESEARCHER_IDEA_SEEDS.md`、`IDEA_PROVENANCE_LEDGER.md` | COMPLETE |
| 2026-11-19 | 全精读库重新盘点 | 47个 Research Lab dossier、5个理论扩展档案、5个故事审计层条目 | `01_CORPUS_SCOPE_AND_EVIDENCE_STATUS.md` | 57_EVIDENCE_ENTITIES_IDENTIFIED |
| 2026-11-19 | 原文优先范围矩阵 | 单篇精读档案、model/theorem/audit 文件 | `03_ORIGINAL_SCOPE_BOUNDARY_MATRIX.csv` | 57_ROWS_VALIDATED |
| 2026-11-19 | 作者局限与项目推断拆分 | 可定位作者局限、定理/实验边界 | `02_AUTHOR_EXPLICIT_LIMITATIONS.md` | FIRST_PASS_EXPLICIT_ONLY |
| 2026-11-19 | 研究成熟度和质疑问题整理 | 六层文献图谱 | `04_RESEARCH_MATURITY_DASHBOARD.md`、`05_CRITICAL_QUESTION_AND_DIVERGENCE_BANK.md` | COMPLETE_FIRST_PASS |
| 2026-11-19 | 原文之后映射 IDEA-03 | R1--R12 | `06_IDEA03_MAPPING_AFTER_ORIGINAL_EVIDENCE.md` | NO_NOVELTY_RANKING |
| 2026-11-19 | 作者局限原文回补第一批 | 31篇已有全文审计论文的 Conclusion/Discussion/Future Work 与显式 scope statements | `07_AUTHOR_EXPLICIT_EXTRACTION_BATCH1.csv`、更新后的 `02_AUTHOR_EXPLICIT_LIMITATIONS.md` 和 `03_ORIGINAL_SCOPE_BOUNDARY_MATRIX.csv` | 29_LOCATED_2_SEARCHED_NOT_FOUND |

## 未执行

- 未重新调用 DeepSeek Flash 或 Pro。
- 未重新读取/生成论文全文 dossier。
- 未运行新实验或算法。
- 未执行 Git add、commit 或 push。
- 两篇仅有远程原文记录的数据库论文使用官方 arXiv PDF 复核结论；未下载或修改原始实验资产。

## 下一道门

由研究者先从 T01--T10 选择最想追问的三项，并在 `RESEARCHER_IDEA_SEEDS.md` 写下直觉。完成前不自动生成候选算法或创新等级。

