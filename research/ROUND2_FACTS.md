# 第二轮审计：已核实事项和保留缺口

> 本文件是上传的 Codex 第二轮四份报告的简化摘要。第二轮属于已有文件和源码的只读核验，并未重跑科学实验。

| 编号 | 纠正后的判断 | 原始证据位置（相对于 Windows 项目根目录） | 剩余缺口 |
|---|---|---|---|
| P0-01 | 主体项目没有可恢复 Git 历史；BRBD 有两份 Luo 作者 checkout | `tmp/researchlab_v2/workspace/BRBD_v1/sources/luo_2024/official_checkout/`；`adapters/luo_dnf_adapter/official_fork/` | 如另有原远端或 `.git` 备份，可隔离再核实；否则新仓库历史从新基线起算 |
| P0-02 | GNN 玩家映射存在于冻结 JSONL 的 players、relation_key、links、metadata | `course_paper_gnn/src/course_paper_gnn/tpch.py`；`data/final/tpch_g1000_v2.jsonl` | 独立映射清单、输入 DuckDB 哈希 |
| P0-03 | 图只用正向边，玩家局部状态不接收下游消息 | `course_paper_gnn/src/course_paper_gnn/{graph.py,data.py,model.py}` | 运行时 trace 可选，不影响当前源码级结论 |
| P0-04 | 3 个 checkpoint 可沿配置追到一个数据路径 | `course_paper_gnn/runs/final_rpv_v2_seed*/run_config.json` | 缺训练当时数据哈希、命令、代码提交；当前哈希不可冒充训练时记录 |
| P0-05 | P3-1B 阈值准备、P3-1C R1 官方 Boolean 最小复现、R2 H1/H2 同目标适配、C2 语义控制需分别标识 | `projects/aggregate_report_shapley_structure_v12/P3_1B/` 和 `P3_1C/` 下 manifests/results | 不等于已完成新的结构参数 2×2 性能实验 |
| P1-01 | LExaShap 91 失败已分类为 90 项位数限制、1 项 divisor 异常 | `tmp/researchlab_v2/workspace/BRBD_v1/runs/R1_abramovich/raw_metrics/formal/` | compatibility smoke 一例仍为非有限值，不能写 91 已修复 |
| P1-02 | M3 是设计未执行，与 P3 MTBDD 是不同系列 | `aggregate_report_shapley/docs/experiment_log.md`；`config/d1p_design.yaml` | 禁止将历史 P3 运行结果倒填为 M3 |

其他保留缺口：GNN 完整输入来源与训练标签生命周期；Luo 原环境内存界限；早期 M1/M2 原始证据；真实整表价值的经济依据；完整报表与知识编译强基线的同目标成本对照。

## 证据约束
- “存在文件”与“已运行”不同；“能找到记录”与“本轮重跑通过”不同。
- 一次实验成功不代表研究假设成立；实验失败不代表方法族不存在。
- 本轮只将第一轮提出的部分缺口改为“已核对”或“部分核对”，不能抹掉来源限制。
