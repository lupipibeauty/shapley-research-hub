# GitHub 工作流改造建议

> 本文件只提出建议。本轮未初始化 Git、未创建 Issue、未建立分支、未移动文件、未提交远程仓库。

## 1. 仓库边界建议

首先恢复原 Git 元数据；在此之前不要把当前目录整体直接初始化并当作唯一历史。根据现有事实，至少应明确三个相对独立的研究单元：精确结构求解、BRBD 文献复现、RPV-GNN 课程论文。若保留 monorepo，需用顶层 project manifest 标明边界；若拆仓库，也应保留跨项目 evidence link，而不是复制结果后失去来源。

## 2. 父子 Issue 适用范围

建议以“研究问题”建父 Issue，以可证伪实验建子 Issue：

- 父 Issue：受控结构因素何时造成精确求解困难
  - 子 Issue：共享/独立 witness × 可加/联合价值 2×2
  - 子 Issue：强 DP/WMC 基线
  - 子 Issue：规模与状态宽度曲线
- 父 Issue：文献算法边界复现
  - 子 Issue：LexaShap 91 失败分类
  - 子 Issue：Figure 4 口径对齐
  - 子 Issue：Luo SF1 原环境复核
- 父 Issue：RPV-GNN 摊销估算论文
  - 子 Issue：玩家—事实映射导出
  - 子 Issue：消息方向/反向边核验
  - 子 Issue：标签—checkpoint lineage
  - 子 Issue：论文结论边界审校

仅为一次性文档修正或单个图表重绘时，不必创建新的研究父 Issue；挂在对应实验子 Issue 下即可。

## 3. 分支建议

独立实验应使用短期分支，并保持一个分支只改变一个可识别因素。示例命名：

- `exp/p3-witness-value-2x2`
- `repro/lexashap-failure-triage`
- `repro/luo-sf1-env`
- `paper/rpv-gnn-message-direction-audit`

不要按含糊阶段命名 `test2`、`new-final`、`v12-final2`。分支合并前必须链接 Issue 和 run manifest；失败实验也可以合并其配置、日志索引和结论，不要求只有“成功代码”才能进入历史。

## 4. Issue 状态与证据标签

将证据等级和研究状态拆为两组标签，避免混用：

- `evidence:A`、`evidence:B`、`evidence:C`
- `research:planned-D`、`research:blocked-E`、`research:rejected-F`
- 过程标签：`needs-semantic-audit`、`needs-reproduction`、`needs-failure-triage`、`paper-ready`

Issue 关闭原因建议限定为：answered、rejected、covered-by-prior-art、environment-blocked、superseded。环境阻塞可关闭当前执行 Issue，但不应把研究命题标成“已否定”。

## 5. 实验 Issue 模板

每个实验 Issue 至少包含：

1. 研究问题与可证伪假设。
2. 与父问题、前一版本和成熟方法的关系。
3. 数据标识与哈希。
4. 玩家定义及 player→fact 映射。
5. SQL、价值函数和联盟语义。
6. 唯一自变量、控制变量和基线。
7. 预期停止准则、资源预算和失败分类。
8. 执行命令、配置路径、代码提交。
9. run manifest、原始结果、图表和报告路径。
10. 结论、证据等级、适用边界及下一问题。

## 6. 不可变运行档案

建议未来正式运行写入 `runs/<experiment_id>/<run_id>/`，运行后不原地覆盖。每个目录包含：

- `manifest.json`：实验 ID、父 Issue、commit、命令、开始/结束、退出状态；
- `config.snapshot.*`：实际配置快照；
- `environment.json`：OS、CPU/GPU、内存、数据库和依赖；
- `input_manifest.csv`：输入路径、行数、哈希；
- `metrics.csv` 与 `stdout.log`/`stderr.log`；
- `artifact_manifest.csv`：图表、表格、报告及其生成脚本；
- `conclusion.md`：只写由本次 run 支持的结论。

大型数据和模型可采用 Git LFS、release artifact 或外部对象存储，但 Git 中必须保留哈希、来源和恢复说明。不要仅提交汇总图而丢弃生成它的原始表。

## 7. 研究状态入口

仓库根目录建议保留一个机器可读 `research_state.yaml` 和一个面向人的 `RESEARCH_STATUS.md`。前者列 experiment_id、Issue、branch、status、evidence、latest_run、report；后者只汇总已回答、阻塞、否定和候选问题。每次正式运行或结论变化时在同一 PR 更新，避免依靠新 AI 窗口重新扫描全盘。

## 8. PR 验收清单

- 是否只改变预声明因素？
- 是否存在代码提交、配置快照和输入哈希？
- 是否保存失败运行而非覆盖？
- 是否把证据等级与研究状态分开？
- 是否区分实例结论、实现结论和方法族结论？
- 是否链接原始表而非只给报告文字？
- 是否更新 research state 和父 Issue？

## 9. 推荐落地顺序

1. 找回 Git 元数据或确认历史不可恢复。
2. 将本次 62 行实验索引作为只读迁移底稿，而非直接当作 Git 历史。
3. 为三个研究单元建立父 Issue，并只导入仍需核实的子 Issue。
4. 优先处理 P0 缺口：玩家映射、消息方向、标签 lineage、P3 子版本。
5. 最后再安排新实验；已否定或被覆盖的方向保留关闭 Issue，避免重复开展。
