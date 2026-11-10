# Shapley 数据库收益分配研究档案

这是一个**本地研究管理与证据索引仓库**。它记录研究 Idea、实验历史、已确认判断、证据入口与后续决策；它不是原始实验代码、数据、模型或第三方源码的镜像。

## 新窗口入口

1. 阅读 [RESEARCH_STATUS.md](RESEARCH_STATUS.md) 了解项目全貌和当前边界。
2. 阅读 [research/IDEAS.md](research/IDEAS.md) 与 [research/DECISIONS.md](research/DECISIONS.md) 了解候选方向和已作判断。
3. 查 [research/EXPERIMENT_INDEX_CURRENT.csv](research/EXPERIMENT_INDEX_CURRENT.csv)；历史快照为 [research/experiment_index_round1.csv](research/experiment_index_round1.csv)，不得就地修改。
4. 遇到结论争议，优先查 [evidence/round2](evidence/round2) 的只读核验，再回到原工作区所列代码、配置、CSV、JSON 或日志。

## 已归档与未归档内容

- 已归档：两轮审计报告、62 项历史索引、当前派生索引、Idea 台账、研究判断、核验事实、工作流模板与迁移说明。
- 未归档：实验代码、SQL、Notebook、原始 JSONL 数据、DuckDB 数据库、模型权重、虚拟环境、缓存、外部作者源码及其 Git 历史。
- 本仓库中的 `<SOURCE_WORKSPACE>`、`<SOURCE_PARENT>` 与 `<USER_HOME>` 是对原审计文本中本机绝对路径的令牌化；原始文件仍保留在旧工作区，未被修改。

## 可恢复性与边界

每项历史实验应通过索引中的代码／配置、数据定义、结果／日志路径回到原工作区核验。项目主体没有可恢复的旧 Git 提交历史；BRBD 内的 Luo 嵌套 Git 检出仅是外部来源，不是本项目历史。

本地 Git 基线仅表示 2026 年 11 月的档案迁移状态，不追溯或伪造过去实验的提交历史。未经单独批准，不创建 GitHub 远程、Issue、分支或迁移原始实验材料。
