# P3-1B：R1/R2 复现准备与阈值分解证据

本目录是独立于 `P3_0/` 的准备工作区。它只读取 P3-0 的冻结 fixture、联盟 oracle 和 G1 Shapley CSV；不会写入或替换 P3-0 的任意文件。

## 重跑

```powershell
..\..\aggregate_report_shapley\.venv\Scripts\python.exe -m pytest -q tests
..\..\aggregate_report_shapley\.venv\Scripts\python.exe run_p3_1b.py
```

`src/threshold_lineage.py` 仅从 `P3_0/fixtures/anchor_13_players.json` 形成 JOIN witness 和 H1/H2 最小获胜联盟。`run_p3_1b.py` 先写入构造结果，再打开 `anchor_truth.csv` 进行最终核验；oracle 不参与算法输入或最小联盟生成。

## 产物

- `results/minimal_winning_coalitions.csv`：H1/H2 最小获胜联盟；应分别为 9 和 4 个。
- `results/threshold_shapley.csv`：两个二元阈值游戏的精确记录级 Shapley。
- `results/oracle_validation.csv`：8192 个联盟的后验 SQL oracle 核验。
- `results/g1_shapley_decomposition.csv`：逐玩家 `phi(H1)+phi(H2)=phi(G1)`。
- `results/P3_1B_manifest.json`：输入哈希、运行口径和输出哈希。
- `reports/P3_1B_R1_R2_复现准备报告.md` 与 `results/algorithm_material_audit.csv`：作者源码、历史本地适配与后续 R1/R2 的边界。
