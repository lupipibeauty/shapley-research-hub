# IDEA-03-2 联合价值深化实验 v1

本目录是 `IDEA03_2_joint_structure_v2` 的独立后续阶段，不修改历史 fixture、代码或结果。

- `F0_EBH`：原 E/B/H 企业中心来源。
- `F1_SITE_LINK`：场所级独立地区关联事实，同一场所—地区有多条合法证明。
- `F2_ENTITY_LINK`：企业级地区关联事实，同一证明由多个场所与多个统计指标共享。
- `G0/G1/G2`：坐标可加、地区内联合、跨地区门槛联合价值。

运行：

```powershell
& ..\..\..\aggregate_report_shapley\.venv\Scripts\python.exe scripts\run_deepening.py
```

本地 `ROADD` 仅用于第三种表示的结构诊断，未实现从 ADD 直接求全部玩家 Shapley，因而不是合格求解基线，也不代表优化后的 ADD/BDD 算法家族性能。
