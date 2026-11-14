# 精度诊断

Windows 当前环境的 `numpy.longdouble` 与 float64 相同：mantissa 均为 52 bits，epsilon 均为 `2.220446049250313e-16`，不能充当更高精度对照。环境未安装 mpmath，且本轮未安装新依赖。

采用 Python `Decimal` 以 50 位和 100 位复刻同一卷积、降幂多项式长除法、阶乘梯度传播和最终归一化；算法结构未改变，标记为 `HIGH_PRECISION_DIAGNOSTIC_ONLY`。

结果：

- float64：首次失败 `N=60`；
- 50 位：`N=60` 恢复，误差约 `6.73e-26`/player；直到 `N=95` 仍通过 loose 门，`N=100` 才出现 `2.258e-5` 的效率漂移；
- 100 位：`N=5..100` 全部恢复到记录精度，`N=60` 精确返回 `1/60`。

失败阈值随有效精度显著后移，符合 `PRECISION_DEPENDENT_FAILURE_BOUNDARY`，支持有限精度原因，而不支持简单 shape/index/branch bug。
