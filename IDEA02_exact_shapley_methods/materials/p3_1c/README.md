# P3-1C：既有 Shapley 算法复现与 C1/C2 覆盖验证

本目录只读取冻结的 `P3_0/` 与 `P3_1B/`，没有修改历史源码、fixture 或结果。正式状态：

- Abramovich R1：`R1_REPRODUCED`
- P3 H1/H2 同目标 R2：`R2_SAME_TARGET_REPRODUCED`
- C2 最小语义实验：`C2_MINIMAL_SEMANTICS_VERIFIED`
- Luo 2024：`R1_ENV_BLOCKED`
- ProvSQL：`ENV_BLOCKED`

重跑主实验：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
..\..\aggregate_report_shapley\.venv\Scripts\python.exe -m pytest -q tests
..\..\aggregate_report_shapley\.venv\Scripts\python.exe run_p3_1c.py
```

主实验只接受 fixture、JOIN witness、玩家映射和 P3-1B 的来源构造逻辑。8192 联盟 oracle 仅用于结果核验，不用于竞争算法输入。
