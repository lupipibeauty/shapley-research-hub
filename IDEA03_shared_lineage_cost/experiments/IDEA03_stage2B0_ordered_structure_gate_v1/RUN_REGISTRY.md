# RUN REGISTRY

## Canonical run

| 字段 | 值 |
|---|---|
| 日期 | 2026-11-14 |
| 协议 | `config/stage2b0_protocol.json` |
| 状态 | `VERIFIED` |
| 实现身份 | `REFERENCE_DIAGNOSTIC_IMPLEMENTATION` |
| Python | 3.7.9, Windows 10/11 build 26100 |
| 候选重连 | 4096 |
| 合法标记重连 | 288 |
| 非同构代表 | 12 |
| 有序诊断运行 | 36 |
| 独立语义核验 | 36/36通过 |
| 新依赖 | 无 |
| 联盟真值表输入 | 无 |

执行命令：

```powershell
python IDEA03_shared_lineage_cost\experiments\IDEA03_stage2B0_ordered_structure_gate_v1\src\run_stage2b0.py
```

## 结果文件

- `results/legal_labelled_assignments.csv`
- `results/structure_space.csv`
- `results/ordered_compilation.csv`
- `results/semantic_validation.csv`
- `results/source_coordinate_summary.csv`
- `results/source_coordinate_details.csv`
- `results/run_manifest.json`
- `logs/run_events.jsonl`

## 失败与资源记录

本 canonical run 无执行失败、超时或资源上限触发。工具门未找到合格成熟 ordered compiler，属于预期准入结果，不记为运行失败；已按协议使用参考诊断适配器。未执行 Git add、commit 或 push。

## 冻结说明

三种顺序、合法性条件和同构去重规则在运行前写入配置。没有依据表示结果筛选实例、增加顺序或删除失败运行。计时仅一次，不作统计推断。
