# 阶段0运行登记

## 1. 本阶段运行

| 运行标识 | 命令/环境 | 状态 | 说明 |
|---|---|---|---|
| `STAGE0_PREFLIGHT_PY37` | `python src/validate_frozen_values.py`；PATH 指向 Python 3.7.9 | `ENV_BLOCKED` | 历史模块使用 Python 3.9+ 的内置泛型语法；在导入时停止，未形成研究结果。未安装依赖，改用本机已有 Python 3.11。 |
| `STAGE0_VALIDATION_DRAFT` | Python 3.11 | `NONCANONICAL_QA` | 初稿分别暴露运行时预算和 CSV 异构字段写出问题；均在写出完整结果前停止，不作研究解释。修复仅作用于新阶段验证脚本。 |
| `STAGE0_FID_20261113_CANONICAL` | `py -3.11 src/validate_frozen_values.py` | `VERIFIED_STAGE0` | 12玩家、4096联盟；4个冻结价值设置全部通过 v0/vN、坐标分解、Shapley效率、收入守恒和退化审计。无性能结论。 |

## 2. 输入与输出

- 冻结配置：`config/frozen_value_function.json`
- 配置 SHA-256：`e05c7a9fc5a53a9b9f1493a556a48f21b3bebae0a78bf4bd792f6bf76708f591`
- 验证脚本：`src/validate_frozen_values.py`
- 结果清单：`results/validation_manifest.json`
- 结果表：`value_validity_summary.csv`、`coordinate_decomposition.csv`、`full_report_and_scales.csv`、`player_mapping.csv`、`shapley_allocations.csv`
- 解释器：Python 3.11.6；未安装新依赖。

## 3. 历史 canonical 引用（未重跑、未覆盖）

| 证据 | canonical run | 状态 |
|---|---|---|
| F0/F1/F2 joint deepening | `DEEP_20261113_155744` | `VERIFIED` |
| 历史 G 等价性与 k=2 E0 | `SHARED_20261113_181356` | `VERIFIED` |
| 省内集中/分散控制 | `SHARED_20261113_175706` | `VERIFIED_WITH_CONTROL_LIMITATION` |
| 精确 solver/caching | `SHARED_20261113_180500` | `VERIFIED` |
| TPC-H SF0.1 结构 | `SHARED_20261113_181253` | `VERIFIED_STRUCTURAL_ONLY` |
| wrapper 非原子残留 | `SHARED_20261113_164908` | `RESOURCE_LIMIT_ORCHESTRATION_ABORTED` |
| 全六夹具重复重编译 | `SHARED_20261113_175906` | `RESOURCE_LIMIT` |

## 4. 声明

本阶段没有执行 Git add/commit/push，没有修改历史 canonical run，没有运行阶段1算法比较，也没有把真值表交给结构化求解器。
