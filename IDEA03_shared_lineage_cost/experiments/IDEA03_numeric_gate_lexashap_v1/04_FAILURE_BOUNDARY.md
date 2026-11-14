# 失败边界

固定 `k=5`、扫描 `m=1..20`：

- `N=5..55`：全部 `PASS_STRICT`；
- `N=60`：首次 loose failure、首次 catastrophic failure，无中间 drift 点；
- `N=60` 的效率和 `-1480319323.8877158`，与 Stage 3B-1 历史异常独立复现；
- `N=65..100`：持续 catastrophic failure，绝对量级继续增长。

失败表现对 float64 是突发的，但源码没有 N=60 分支。结合精度实验，突发边界来自条件不良递推越过当前精度可承受范围，而不是离散索引分支。

完整数据见 `results/analytic_family_results.csv` 和 `results/failure_boundary.csv`。
