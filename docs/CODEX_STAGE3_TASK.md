# 给 Codex 的下一步任务：准备 GitHub 科研总账基线（先只读、再提交建议）

你在 `<SOURCE_WORKSPACE>` 工作。第二轮只读审计已完成，结果见本迁移包的 `evidence/round2/` 和 `research/ROUND2_FACTS.md`。

**目标**：确认可以怎样安全建立一个独立的新研究档案 Git 仓库，使不同 AI 窗口能够准确恢复 Idea、实验和结论。此轮先完成迁移准备和清单，不替用户直接初始化/推送 GitHub。

**第一步：核对本包与本地材料**
1. 阅读 `00_READ_FIRST.md`、`RESEARCH_STATUS.md`、`research/IDEAS.md`、`research/ROUND2_FACTS.md`。
2. 根据 Windows 目录确认所有第二轮证据路径仍可定位；相互冲突时引用原始代码/manifest，不自动采信整理摘要。
3. 确认 62 行第一轮实验索引存在；识别其中已被第二轮纠正的旧判断，另写增补说明，不静默改原索引。

**第二步：拟定最小迁移清单**
4. 列出可进入 GitHub 的 Markdown、YAML、小型结果索引，以及应排除的虚拟环境、第三方 checkout、大型训练数据、模型权重、敏感信息和缓存。
5. 逐个给出预期新仓库文件的来源路径、大小、是否含敏感信息、是否应直接入 Git，以及需要保留的 SHA-256 或相对证据链接。
6. 给出 `research_state.yaml` 的示例，但不得编造 issue 号、远程 URL 或 commit 哈希。
7. 只建议先建 IDEA-02/03/04 三个主 Issue 与各自一个最明确的子任务；IDEA-01/05 保留为候选台账。

**第三步：输出并停止**
8. 在独立的新目录 `research_audit/20261110_stage3_plan/` 输出 `MIGRATION_INVENTORY.md`、`STATUS_CONFLICTS.md`、`PROPOSED_REPO_TREE.md`、`GITHUB_ACTIONS_REQUIRING_APPROVAL.md`。
9. 不创建或修改任何 Git 仓库、分支、Issue、PR；不安装依赖、运行实验、移动原始文件、上传云端。输出完成即停止。

**验收**：我可以快速知道将上传什么、不会上传什么、如何恢复一份旧结果、哪个 Idea 当前该做什么。任何材料不齐时要明确标注而不是补造。
