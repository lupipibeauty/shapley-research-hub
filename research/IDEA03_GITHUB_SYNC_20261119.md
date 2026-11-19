# IDEA-03 GitHub 同步说明（2026-11-19）

## 目的

把 IDEA-03-2A～2F 的最新研究判断、分支级竞争审计和文献证据同步到 `shapley-research-hub`，使新窗口能够同时看到实验谱系与精读文献边界。

## 本次纳入

- `IDEA03_shared_lineage_cost/IDEA03_2A_2F_BRANCH_REGISTRY.md`
- `IDEA03_shared_lineage_cost/IDEA03_2A_2F_LATEST_PROGRESS_20261119.md`
- `research/IDEA03_3_branch_audit_20261114/` 中的小型 Markdown 研究审计文件
- `research/IDEA03_story_literature_deepread_v1/` 中的研究故事、矩阵、定理审计和证据 JSON
- `research/IDEA03_theory_extension_deepread_v2/` 中的精读档案、研究启发、理论矩阵和证据审计
- `research/IDEA03_literature_limitation_atlas_v1/` 中的57项范围矩阵、研究成熟度图谱和作者局限回补
- 更新后的 `RESEARCH_STATUS.md`、`research/IDEAS.md` 与 `research_state.yaml`

## 明确排除

- 原文 PDF 和外部作者源码
- DeepSeek/Flash 切片工作目录与本地知识库 SQLite
- Excel 检查 NDJSON、预览 PNG 和 PDF preflight 临时结果
- 数据库、模型权重、虚拟环境、缓存和大型实验数据

## 路径与敏感信息处理

本地档案需要保留原始附件位置以便复核；公开 GitHub 档案副本将本机绝对路径替换为 `<SOURCE_WORKSPACE>` 或 `<USER_HOME>`。该令牌化差异是有意的，不表示研究内容不一致。未发现 API 密钥、GitHub token 或其他凭据进入同步清单。

## 状态解释

本次同步不创建六条 Git 分支。IDEA-03-2A～2F 是六个研究子方向，其中2A作为价值准入门，2D在当前星形族并入2B，2F仍为冻结设计和局部证据。具体状态以 `IDEA03_2A_2F_LATEST_PROGRESS_20261119.md` 为准。
