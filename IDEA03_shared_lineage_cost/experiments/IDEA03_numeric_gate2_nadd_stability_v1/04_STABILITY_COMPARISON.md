# 稳定性比较

## 冻结正确性对象

对 `F_{m,5}` 的 `N=10,30,55,60`，三种方法输入完全相同，Decimal 100位同递推作为 backward message 与最终Shapley oracle。

结果：

- `N=10,30,55`：三种方法均通过严格门；
- `N=60` 当前反卷积复现每人 `-24671988.73146193`、效率和 `-1480319323.8877158`；
- `N=60` prefix/suffix 与 product tree 均返回每人 `0.016666666666666666`、效率和 `1.0`、symmetry spread `0.0`；
- 两个替代方法的 sibling message 对 Decimal100 最大绝对误差均为0（转成float64比较）；
- backward vector相对误差约 `1.70e-16`，属于正常舍入；
- 当前反卷积 sibling message 最大误差 `4.0851e-8`，backward vector相对误差约 `1.03e7`。

因此记录：`STABLE_ALTERNATIVE_CONFIRMED_ON_FAILURE_CASE`。

## 中间数值

N=60时三者 sibling message 的真实动态范围约 `2.91e15`。prefix/suffix和product tree虽面对同样动态范围，但只做正向乘加，最大中间误差为0；当前反卷积出现约5639的减法消去比并在索引24产生商误差。

去掉反卷积后，后续巨大阶乘梯度没有继续造成错误：最终效率和与对称性均严格恢复。因此不支持 `DEEPER_BACKWARD_STABILITY_PROBLEM`。

完整数据见 `results/method_correctness.csv`、`intermediate_numeric_metrics.csv` 和 `failure_case_comparison.csv`。
