# RUN REGISTRY

## Canonical run

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 协议 | `IDEA03_STAGE3A_Q9_NONSTAR_GATE_V1` |
| 状态 | `VERIFIED` |
| Python | 3.11.6 |
| DuckDB | 1.5.6 |
| 数据库模式 | `read_only=True` |
| witness | 402 |
| P1/P2玩家 | 918 / 854 |
| Shapley计算 | 否 |
| 联盟枚举 | 否 |
| 外键修改 | 否 |
| Git操作 | 否 |

执行命令：

```powershell
aggregate_report_shapley\.venv\Scripts\python.exe IDEA03_shared_lineage_cost\experiments\IDEA03_stage3A_q9_nonstar_gate_v1\src\run_q9_gate.py
```

运行一次成功，数量预检3/3匹配。此前会话中的一次PowerShell内联命令在进入DuckDB前因括号解析失败，不属于canonical run，未修改文件或数据库；随后以标准输入只读查询完成预检查。

## 结果入口

- `results/q9_witnesses.csv`
- `results/precheck_validation.csv`
- `results/part_supplier_edges.csv`
- `results/part_supplier_metrics.csv`
- `results/provenance_metrics.csv`
- `results/witness_player_edges.csv`
- `results/player_map_p1.csv`
- `results/player_map_p2.csv`
- `results/player_witness_degree.csv`
- `results/witness_overlap_distribution.csv`
- `results/overlap_examples_and_components.csv`
- `results/q9_l_witnesses.csv`
- `results/q9_h_witnesses.csv`
- `results/subinstance_metrics.csv`
- `results/report_compatibility_groups.csv`
- `results/run_manifest.json`

最终研究状态：`Q9_NONSTAR_DEPENDS_ON_PLAYER_BOUNDARY`。
