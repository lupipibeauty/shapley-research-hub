# RUN REGISTRY

## Canonical run

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 协议 | `IDEA03_STAGE3B1_Q9_NONSTAR_COST_GATE_V1` |
| 进程状态 | `COMPLETED` |
| 结构对象 | 12 |
| 官方LExaShap编译 | 12/12完成 |
| 官方Boolean效率核验 | 11/12通过 |
| 参考VE运行 | 24/24完成并匹配容斥model count |
| ordered compiler | `NO_ELIGIBLE_ORDERED_COMPILER_LOCAL` |
| 联盟枚举 | 未执行 |
| 完整报表G | 未执行 |
| Git操作 | 未执行 |

命令：

```powershell
aggregate_report_shapley\.venv\Scripts\python.exe IDEA03_shared_lineage_cost\experiments\IDEA03_stage3B1_q9_nonstar_cost_gate_v1\src\run_stage3b1.py
```

## 异常记录

1. ordered-compiler预检的首个PowerShell命令在解析阶段因`foreach`空管道语法失败，未执行环境检查；随后用只读数组语法完成检查，没有安装依赖。
2. 派生比率首次显示命令发生同类PowerShell解析失败，未修改任何结果；随后只读计算成功。
3. `Q9_L12_P1`官方DNFCircuit完成73节点电路构造，但backward返回错误效率和，标记 `FAILED_NUMERIC_STABILITY`。没有自动重跑或修改作者实现。

## 证据文件

- `results/subinstance_structure.csv`
- `results/player_map.csv`
- `results/witness_map.csv`
- `results/lexashap_metrics.csv`
- `results/lexashap_shares.csv`
- `results/lexashap_correctness_audit.csv`
- `results/ve_metrics.csv`
- `results/correctness_checks.csv`
- `results/representation_comparison_summary.csv`
- `results/postrun_status_audit.json`
- `results/run_manifest.json`
- `logs/run_events.jsonl`

最终研究判断：`REPRESENTATION_DEPENDENT_EFFECT`。
