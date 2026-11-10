# Git 历史恢复结果

## 核验范围与方法

只读检查了 `<SOURCE_WORKSPACE>` 根目录、主要实验目录、`<SOURCE_PARENT>` 下的 `.git` 目录及 Git/bundle/backup 候选文件，并在 `<USER_HOME>\Downloads`、`Documents`、`Desktop` 查找 bundle、Git 备份及名称含 Shapley 的压缩包。未执行 `git init`、fetch、checkout、branch 或任何网络操作。

## 结论

### 项目历史：未找到可恢复 Git 历史

- `<SOURCE_WORKSPACE>` 不是 Git worktree；`git rev-parse --show-toplevel` 和 `git worktree list` 均失败。
- 没有在项目根、`aggregate_report_shapley/`、`projects/`、`course_paper_gnn/`、`project_handoff_and_progress/` 发现项目级 `.git`、Git bundle 或 `.git` 备份。
- 未找到能够承载本项目提交对象的 Git archive。现存 P3 handoff ZIP 是交接材料，不含 Git 历史。

因此，**不能恢复本项目的旧 branch、commit、worktree、已跟踪文件状态或历史提交时间。** 后续若建立新仓库，必须标为“从新基线开始”，不能将新提交冒充旧实验提交。

### 例外：两份可用但外部的 Git checkout

| 工作树 | Git 事实 | 与项目历史的关系 |
|---|---|---|
| `tmp/researchlab_v2/workspace/BRBD_v1/sources/luo_2024/official_checkout/` | detached HEAD `2a514fb4a0e3d45365d6dffe6435f93499afd7e3`；origin `https://github.com/IDEAL-Lab/shapley-value-simple-game.git`；提交日期 2024-01-06 | Luo 作者源码依赖版本证据。 |
| `tmp/researchlab_v2/workspace/BRBD_v1/adapters/luo_dnf_adapter/official_fork/` | 同一 detached HEAD 与 origin；`git status --short` 显示未跟踪 `src/bin/cal_dnf_adapter.rs` | 外部 fork；未跟踪文件可作为本地适配痕迹，不是项目提交。 |

这两份 Git checkout 修正了“工作区中任何地方没有 `.git`”的表述；但不改变“主体项目没有可恢复 Git 历史”的结论。

### 检查到但不构成项目历史的压缩包

- `<USER_HOME>\Downloads\shapley-value-independent-utility-master.zip`：Luo 独立效用源码包，非 Git bundle。
- `<SOURCE_WORKSPACE>\handoff_p3_algorithm_audit_20261104.zip` 与 `P3_1C_handoff_20261104.zip`：P3 交接材料，不含 `.git` 对象库。
- `<USER_HOME>\Downloads\cifar_shapley_experiment_backup.zip`、`Shapley_Experiment_Results.zip`：图表/表格类其他实验材料，不是本项目 Git 历史。

## 可行迁移方式（建议，不实施）

1. 若用户之后找到原 `.git`、bundle 或远端 URL，先在隔离副本验证其 `git fsck`、提交图和项目路径，再决定是否恢复。
2. 若确认找不到，建立新仓库前先将本次审计文件、原始 run manifest、输入/输出哈希作为“迁移前证据基线”。
3. 外部 Luo checkout 可记录其 commit `2a514fb…`，但不得将其作为 `aggregate_report_shapley`、P3 或 GNN 的代码提交号。
