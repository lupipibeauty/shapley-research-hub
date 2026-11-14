# RUN REGISTRY

| 记录 | 状态 | 说明 |
|---|---|---|
| `FAILED_ADAPTER_PREFLIGHT_20261113` | `FAILED_ADAPTER_PREFLIGHT` | 首个电路构造前遗漏作者类级 timeout 初始化；无算法结果，详见 `logs/preflight_failure_20261113.md` |
| `STAGE2A_20261113_CANONICAL` | `VERIFIED` | 两个严格N=16实例；官方LExaShap直接来源编译；`v_fid/v_gap`同目标精确适配；oracle仅事后核验 |

`logs/run_events.jsonl` 保留了适配器测量字段完善期间的5次成功执行时间。结果目录采用最新一次规范运行覆盖生成；这些执行不是预注册的独立计时重复，不用于置信区间或性能显著性判断。

规范命令：

```powershell
$env:PYTHONHASHSEED='0'
& D:\python项目\shapley\aggregate_report_shapley\.venv\Scripts\python.exe D:\python项目\shapley\IDEA03_shared_lineage_cost\experiments\IDEA03_stage2A_mature_source_compilation_20261113\src\run_stage2a.py
```

环境：Python 3.11.6，Windows 10 build 26200；作者依赖沿用既有 `aggregate_report_shapley/.venv`，未安装新依赖。

规范原始结果：

- `results/run_manifest.json`
- `results/source_compilation_metrics.csv`
- `results/variable_orders.csv`
- `results/value_components.csv`
- `results/component_boolean_exactness.csv`
- `results/multioutput_reuse_metrics.csv`
- `results/exact_shapley_comparison.csv`

