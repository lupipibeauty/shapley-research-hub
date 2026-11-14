# RUN REGISTRY

## 历史复用

| ID | 状态 | 本轮动作 |
|---|---|---|
| `SHARED_20261113_175706` | `VERIFIED` | 复用 E1 第一组输入与390次 SQL 结论；未重跑旧 SQL |
| `SHARED_20261113_180500` | `VERIFIED` | 复用 ROADD/LExaShap 正确性边界；未重跑求解器 |
| `SHARED_20261113_181356` | `VERIFIED` | 复用 G1/GR、k=2 与 E0 SQL 结论 |
| `SHARED_20261113_181253` | `VERIFIED_STRUCTURAL_ONLY` | 复用 TPC-H 跨地区 supplier 结构事实；未重建 |

## 本轮运行

| 运行 | 命令 | 状态 | 结果 |
|---|---|---|---|
| `STAGE1_ENV_PREFLIGHT` | 全局 `py -3.11` 导入 DuckDB | `ENV_CHECK_FAILED_RESOLVED` | 全局解释器缺 DuckDB；未安装依赖，改用项目已有 Python 3.11.6 / DuckDB 1.5.6 venv |
| `STAGE1_E1_NEW_G` | `aggregate_report_shapley/.venv/Scripts/python.exe src/run_stage1.py --step experiment1` | `VERIFIED` | 只计算旧 E1 第一对的新 G；满足停止规则，不运行第2/3对 |
| `STAGE1_CROSS_REGION_PAIRS` | 同解释器，`--step new-pairs` | `VERIFIED` | 严格配对通过；放宽配对记为 `LOCAL_OBSERVATION`；260个新 SQL/Python 样本一致 |
| `STAGE1_FINALIZE` | 同解释器，`--step finalize` | `VERIFIED` | 生成差异表、SHA-256 manifest 和阶段门判断输入 |

运行事件见 `logs/run_events.jsonl`。实验1约从22:27:57至22:31:43；新配对约从22:34:04至22:44:20。时间仅用于运行登记，不作算法性能比较。

## 输入与哈希

- 协议：`config/stage1_protocol.json`
- 冻结 G：`../IDEA03_stage0_fidelity_freeze_20261113/config/frozen_value_function.json`
- SQL：`sql/report_f0_frozen.sql`
- 玩家/事实：`results/new_player_mapping.csv`、`new_fixture_records.csv`
- 机器可读哈希：`results/stage1_manifest.json`

## 状态声明

- oracle 真值表只用于 N≤16 正确性和表示审计，未作为结构化算法输入；
- 未重复旧实验；
- 未执行 Git add、commit、push；
- 阶段2未启动。
