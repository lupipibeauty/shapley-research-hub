# GitHub 迁移计划（尚未执行）

## 为什么现在可以进入迁移准备
第二轮已经把 Git 历史、GNN 映射与边方向、P3 子任务身份、M3 身份、91 项失败的核心歧义查清；不必因此再做一次无目标的大规模扫描。仍有证据缺口，但可在新基线持续补齐。

## 建议采用的最低结构

```text
research-hub/
├── README.md
├── RESEARCH_STATUS.md
├── AGENTS.md
├── research/
│   ├── IDEAS.md
│   ├── ROUND2_FACTS.md
│   ├── experiment_index_round1.csv
│   └── EXPERIMENT_INDEX_README.md
├── evidence/round2/                 # 原始第二轮上传报告（保持不变）
├── docs/
│   ├── GITHUB_MIGRATION_PLAN.md
│   ├── CODEX_STAGE3_TASK.md
│   └── NEW_WINDOW_START.md
└── .github/ISSUE_TEMPLATE/           # 起步两个简短模板
```

初期不移动 62 项实验的代码和 GB 级原始数据。后续若确需纳入 Git，逐目录审查体量、许可、敏感信息和再现方法。外部 Luo checkout 应单独记录其来源与 commit，不应被当成自己的旧 Git 历史。

## 分阶段动作

**0. 基线只读准备**：选定新私有仓库名称；保存 62 项历史索引及第二轮核验报告；列出源目录、需排除的数据/外部源码、文件大小，制作迁移前校验清单。

**1. 本地 Git 初始化（需用户批准）**：在**新空目录**建立元数据仓库，而不是原样对整个 `<SOURCE_WORKSPACE>` 执行 `git init`；仅提交本包的研究状态与证据清单；初始提交明确写“2026-11-10 后的新基线”。

**2. 推送远端（需用户批准与认证）**：连接私有 GitHub 仓库，核对权限后推送；确保 Markdown 中旧绝对路径在新环境可能不可访问，并提供索引链接/哈希和可恢复存储说明。

**3. Issues 导入（需用户批准）**：先建立 IDEA-02/03/04 三个问题 Issue 和少量有明确门禁的子 Issue；IDEA-01/05 暂留文档状态，避免制造大量空 Issues。历史 62 项保持档案，不逐项自动建 Issue。

**4. Codex 执行（未来）**：从已批准的子 Issue 建短期分支或 Git worktree；执行实验后通过 PR 记录结果并更新主状态。

## 当前不宜执行的动作
- 不重置/删除旧实验文件，不把 90 个 Python 位数失败写成已修复；
- 不把旧 P3 MTBDD 与 M3 合并；
- 不把用户历史讨论当成已有 Git commit；
- 不从用户电脑导出未经检查的数据；
- 不一次性把所有候选 Idea 的长期分支和历史 Issue 建好。
