# DeepSeek Flash 执行审计

## 1. 连通性恢复

第一次失败发生在 DeepSeek 服务端之前：Codex 子进程继承了指向 `127.0.0.1:9` 的阻断代理。仅在随后命令进程中清除三个代理环境变量后，`deepseek_research.py ping --allow-external-api` 成功：模型 `deepseek-flash`，prompt 22、completion 7、合计 29 tokens。没有修改系统代理、项目 `.env` 或 API Key。

## 2. 实际外发范围

仅发送四篇公开作者/会议 PDF 的逐页提取文本：Comparisons of Signals、Marginal Contribution Nets、Cooperative Games with Bounded Dependency Degree、Markets for Information。Owen (1977) 无公开正文，没有发送摘要冒充全文。没有发送历史实验、私人笔记、Zotero 数据库或密钥。

## 3. 调用与用量

| 论文 | 页数 | scan切片 | 模型 | 状态 |
|---|---:|---:|---|---|
| Comparisons of Signals | 33 | 11 | deepseek-flash | 10 DRAFT；页19–21为1 RAW |
| Marginal Contribution Nets | 10 | 6 | deepseek-flash | 6 DRAFT |
| Bounded Dependency Degree | 8 | 5 | deepseek-flash | 5 DRAFT |
| Markets for Information | 23 | 8 | deepseek-flash | 8 DRAFT |

总计：30次 scan 调用；prompt 71,907、completion 43,836、合计 115,743 tokens。未调用 `deepseek-v4-pro`，未运行 `synthesize`。

## 4. 自动审计结果

- 四篇均完成物理页覆盖；Comparisons 有1个 low-text page，仍需视觉核验。
- Flash 多数条目缺少工作流预期的 `exact_quote` 与统一 `pdf_page` 字段，自动审计报告大量 `QUOTE_MISSING`。这说明覆盖存在，不说明引文已核验。
- Comparisons 第19–21页输出未通过标准 JSON schema，保存为 `RAW_MODEL_OUTPUT`；审计器因 `evidence` 中出现字符串而非对象触发 `AttributeError`。原响应保留，不修写为合格证据。
- 其余三篇第一次审计只因 Windows GBK 无法打印数学符号中止；设置当前进程 `PYTHONIOENCODING=utf-8` 后完成。该设置不改变论文数据。
- `assemble` 需要 `deep` 阶段；本轮已有 Codex Luo dossier，按“不重复全文生成”规则未继续调用 Flash deep，更未调用 Pro。

## 5. 证据权限

所有 Flash 文件均为 `DRAFT_MODEL_OUTPUT` 或 `RAW_MODEL_OUTPUT`。它们可以帮助发现章节、术语与待核问题，但不能覆盖：

1. 本地 PDF 的公式和定理编号；
2. Owen 正文缺失状态；
3. Codex 已建立的研究启发分类；
4. 研究者对 R1–R12 的最终判断。

原始切片与调用记录位于 `flash_workspace/deepread/`；独立 SQLite 位于 `flash_workspace/knowledge.sqlite`，没有写入历史 Research Lab 知识库。
