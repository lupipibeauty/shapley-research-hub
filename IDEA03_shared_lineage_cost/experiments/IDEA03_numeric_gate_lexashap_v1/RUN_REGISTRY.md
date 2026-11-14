# RUN REGISTRY

## 执行记录

| 顺序 | 命令/动作 | 状态 | 说明 |
|---:|---|---|---|
| 1 | 读取 Stage 3B-1 报告、CSV 与官方源码 | VERIFIED | 只读，历史文件未修改 |
| 2 | `python -m py_compile ...run_numeric_gate.py` | COMPLETED | 语法通过 |
| 3 | `python ...run_numeric_gate.py` | COMPLETED | 20 个冻结解析实例 |
| 4 | 检查 mpmath | ENV_UNAVAILABLE | 未安装；未安装新依赖 |
| 5 | `python -m py_compile ...run_precision_diagnostic.py` | COMPLETED | 语法通过 |
| 6 | `python ...run_precision_diagnostic.py` | COMPLETED | Decimal 50/100 位及 N55/N60 trace |
| 7 | 增加 cancellation 只读诊断后重跑 precision diagnostic | COMPLETED | 同一冻结输入，不改变门槛 |

## 停止点

已由纯解析输入独立复现；输入/映射/wrapper 排除；错误定位到作者 `N_add` 浮点反卷积；提高精度恢复且推迟失败边界。按 `EARLIEST_CONFIRMED_CAUSE` 停止，不运行结构扩展和数据库实验。

最终状态：`FINITE_PRECISION_FAILURE_SUPPORTED`。
