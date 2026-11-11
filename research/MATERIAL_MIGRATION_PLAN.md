# 原始材料迁移计划（尚未执行）

本计划把“说明文档”和“可归档原始材料”分开。原始工作区继续保留，任何复制都必须写入来源、目标、哈希和排除原因。

## 第一批：建议迁移的自有小型材料

| Idea | 来源范围 | 计划目标 | 迁移规则 |
|---|---|---|---|
| IDEA02 | `projects/aggregate_report_shapley_structure_v12/P2/`、`P3_0/`、`P3_1B/`、`P3_1C/` | `IDEA02_exact_shapley_methods/materials/{p2,p3_0,p3_1b,p3_1c}/` | 复制 `.py`、`.yaml`、`.json`、小型 `.csv`、manifest、summary、日志和 README；排除 `__pycache__`、作者源码压缩包、PDF 和 vendor。 |
| IDEA04 | `course_paper_gnn/src/`、`scripts/draw_rpv_gnn_framework.py`、`report/*.tex`、`report/figures/` 中已确认的小型图表 | `IDEA04_gnn_amortized_estimation/materials/{src,scripts,paper,figures}/` | 复制自有源码、配置、TeX、说明和小型结果图；排除 `data/`、`runs/`、`*.pt`、`*.jsonl`、压缩包和缓存。 |

## 暂不复制的材料

- `aggregate_report_shapley/` 整体：包含外部作者源码、环境、缓存和混合运行产物；需逐模块拆分。
- `projects/P3_1C/reproduction/luo2024_r1/source/`、`*.zip`、`technical_report.pdf`：外部作者实现或大型复现包，记录 provenance，不纳入自有 Git 历史。
- `course_paper_gnn/data/`：原始 JSONL 数据，包括 SF0.1、SF1、dummy 和 smoke 数据。
- `course_paper_gnn/runs/`：训练权重、缓存和完整运行目录。
- `*.duckdb`、`*.db`、`*.sqlite`：数据库运行产物。

## 每次复制的验收条件

1. 源文件在原工作区仍存在且哈希不变。
2. 目标文件写入 `MATERIAL_MANIFEST.csv`，记录 Idea、实验编号、源路径、目标路径、源／目标 SHA-256 和证据等级。
3. `__pycache__`、虚拟环境、第三方源码、密钥、大型数据和模型权重为零混入。
4. 复制后运行最小的静态导入／路径检查，但不自动重跑大型实验。
5. 每批材料单独提交，提交信息不伪造过去的实验历史。

当前状态：**仅完成迁移计划与研究说明，第一批原始材料尚未复制。**
