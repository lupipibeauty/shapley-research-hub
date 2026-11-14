# IDEA-03-2：联合价值、来源表示与共享编译

本目录是 2026-11-13 的独立后续实验，不修改 `IDEA03_2_joint_value_deepening_v1` 及更早历史对象。

执行顺序：

1. `python scripts/run_study.py --stage e0`
2. `python scripts/run_study.py --stage e1`
3. `python scripts/run_study.py --stage e2`
4. `python scripts/run_study.py --stage tpch`
5. `python scripts/run_study.py --stage reports`

`--stage all` 依次执行全部阶段。每次运行写入新的 `runs/RUN_*`，不会覆盖旧运行。

状态口径：`VERIFIED` 表示已由本轮代码和原始输出核验；`INPUT_UNSUPPORTED` 表示算法与冻结目标不匹配；`ENV_BLOCKED` 表示依赖或作者环境不可用；`REPORTED_ONLY` 仅表示历史报告陈述。

