# IDEA-03 理论扩展精读：范围与证据协议

## 1. 本轮定位

本目录继承 `../IDEA03_story_literature_deepread_v1/` 的十张研究故事卡、LIT 编号和 R1–R5，不修改历史实验、旧精读判断或 canonical run。本轮只增加五组理论原文证据、研究启发和真实任务调查入口，不执行 Shapley 实验，不开发算法。

## 2. Luo 模板执行口径

每篇设置八个文件：`精读档案.md`、`source.json`、`model_spec.md`、`theorem_atlas.md`、`algorithm_reconstruction.md`、`experiment_matrix.csv`、`证据审计结果.md`、`研究启发.md`。结论必须落到版本、页码或章节；“原文明确”“基于原文推导”“新研究设想”分开记录。

证据状态：

- `FULLTEXT_THEOREM_VERIFIED`：作者、出版社或会议原文已逐节核验，关键定理有页码。
- `FULLTEXT_MODEL_VERIFIED`：模型与主要结论已核验，但附录、代码或视觉要素仍有缺口。
- `FULLTEXT_UNAVAILABLE`：只获得出版社元数据/摘要，不声称完成全文精读。
- `APPENDIX_UNVERIFIED`、`CODE_UNVERIFIED`、`VISUAL_PENDING`：分别表示附录、代码和 PDF 视觉复核尚未完成。

## 3. 本轮来源结果

| LIT | 论文 | 冻结版本 | 本轮状态 |
|---|---|---|---|
| LIT-011 | Owen (1977) | Springer chapter, pp. 76–88 | `FULLTEXT_UNAVAILABLE`；只核验元数据和官方摘要 |
| LIT-023 | Brooks, Frankel & Kamenica | 2024-03 作者 PDF，33页；另核对 AER 发表信息 | `FULLTEXT_THEOREM_VERIFIED`，`CODE_UNVERIFIED` |
| LIT-012 | Ieong & Shoham | EC'05 作者/微软研究院 PDF，10页 | `FULLTEXT_THEOREM_VERIFIED`，`CODE_UNVERIFIED` |
| LIT-013 | Igarashi, Izsak & Elkind | AAAI-18 会议版，8页 | `FULLTEXT_THEOREM_VERIFIED`，长版附录待核 |
| LIT-024 | Bergemann & Bonatti | Annual Review of Economics 2019 作者 PDF，23页 | `FULLTEXT_MODEL_VERIFIED`；综述无自编号主定理 |

## 4. DeepSeek 执行状态

2026-11-18 的第一次 Flash 连通测试因 Codex 进程被注入 `127.0.0.1:9` 阻断代理而失败（`openai.APIConnectionError` / WinError 10061），当时状态为 `DEEPSEEK_FLASH_ENV_BLOCKED`。随后仅在当前命令进程中清除 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`，最小 ping 成功；未修改 `.env`、密钥或系统代理。

恢复后对四篇公开 PDF 执行了 `deepseek-flash` 全文 `scan`：共 30 个逻辑切片、115,743 tokens，其中 29 个为 `DRAFT_MODEL_OUTPUT`，Comparisons of Signals 第19–21页一个切片为 `RAW_MODEL_OUTPUT`。自动审计显示 Flash 没有稳定提供逐字引文和统一页码字段，因此这些结果只作为覆盖草稿保存，未覆盖 Codex 原文档案，也未调用 Pro。详见 `07_DEEPSEEK_FLASH_EXECUTION_AUDIT.md`。

## 5. 防止错误外推

1. Owen 正文未获得，任何完整公式、公理或证明均只能标为二手重构，不能写成“原文已核验”。
2. 确定性统计报表不是天然的经济学“信号”；引入 Brooks 等人的结论前必须定义状态、先验、观测和行动。
3. MC-net 的线性时间以输入规则长度为参数，不等于任意 SQL 游戏对玩家数多项式。
4. bounded dependency 的 FPT 结果假设依赖集合可获得；依赖图发现本身可指数困难。
5. 信息产品成交价、买方决策价值、来源方补偿、平台利润和固定收入池 `R` 是不同对象。

