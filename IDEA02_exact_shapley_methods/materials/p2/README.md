# P2 修订版实验

本目录独立于 P0/P1。运行顺序：

```powershell
..\..\..\aggregate_report_shapley\.venv\Scripts\python.exe -m pytest -q
..\..\..\aggregate_report_shapley\.venv\Scripts\python.exe run_p2.py
```

P2 使用 12 个记录玩家、同一 Q2-NH、4+4+4 事实和 4 个满联盟 groundings 构造 F0/F1/F2/F5。F2 与 F5 在 H1/H2 的满联盟报表完全匹配，但证据复用结构不同。

P2-B 的 `G2-JOINT-TASK-COMMON` 是冻结 G2 的行动 A1，用作 H1/H2 共有坐标控制；完整冻结 G2 只在 H2 的 A3 中运行。两者不能混称为同一游戏。
