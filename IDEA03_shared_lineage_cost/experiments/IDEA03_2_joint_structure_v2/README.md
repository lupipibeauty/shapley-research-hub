# IDEA-03-2 RQ3 联合结构实验 V2

本目录是独立的新实验，不修改 P3、D1-P、H3、H5 或历史复现结果。

状态：`E0_VERIFIED / E1_VERIFIED / E2_RESOURCE_LIMIT / E3_E4_NOT_STARTED`。

研究判断：当前没有得到稳定的“共同来源 × 联合价值”额外成本证据；后续诊断证明当前 lineage 为企业中心低宽度森林，G 只使用2/35坐标且可由 Harsanyi/LExaShap 精确分解。N=24 的阻塞来自 H3-S6 未利用企业分量的全局状态表示，而不是游戏本身或 High+Joint 特有困难。详见 `PREVIOUS_EXPLORATION_DIAGNOSIS.md`。

主要入口：

```powershell
& D:\python项目\shapley\aggregate_report_shapley\.venv\Scripts\python.exe scripts\run_rq3.py --stage E0
& D:\python项目\shapley\aggregate_report_shapley\.venv\Scripts\python.exe scripts\run_rq3.py --stage E1
& D:\python项目\shapley\aggregate_report_shapley\.venv\Scripts\python.exe scripts\run_rq3.py --stage E2
```

E2 已在 E0/E1 的非枚举精确基线通过后执行首个资源门，并按停止条件停止。所有生成资产写入各时间戳 `runs/`；旧实验只读引用。

证据状态使用：`VERIFIED`、`REPORTED_ONLY`、`INPUT_UNSUPPORTED`、`ENV_BLOCKED`、`RESOURCE_LIMIT`、`FAILED_CORRECTNESS`。

有效运行与失败运行的取舍见 `RQ3_RUN_REGISTRY.md`。原六份主交付与补充诊断 `PREVIOUS_EXPLORATION_DIAGNOSIS.md` 均位于本目录根部。

