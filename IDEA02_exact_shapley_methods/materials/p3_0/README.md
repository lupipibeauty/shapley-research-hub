# P3-0 双组汇总报表收益分配与原生精确计算

本阶段只执行历史回溯、完整数据库骨架、13 玩家正确性锚点和原生精确计算审计。规模、多层报表和动态实验未启动。

```powershell
..\..\..\aggregate_report_shapley\.venv\Scripts\python.exe -m pytest -q
..\..\..\aggregate_report_shapley\.venv\Scripts\python.exe run_p3_0.py
```

原生方法从完整数据库的 JOIN witness 构建分层多终端决策图，并对每个玩家计算按联盟大小分层的条件模型计数；它不读取 `anchor_truth.csv` 或任何联盟价值表。完整联盟枚举在原生计算完成后才运行，用作独立 oracle。
