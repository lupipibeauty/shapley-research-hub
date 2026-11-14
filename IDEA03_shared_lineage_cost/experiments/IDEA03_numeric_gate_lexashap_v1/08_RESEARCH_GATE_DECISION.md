# 研究门判断

## 最终状态

`FINITE_PRECISION_FAILURE_SUPPORTED`

## 直接回答

1. 60 玩家失败可由纯解析 DNF 独立复现，数值与历史失败一致。
2. 失败与 Q9、SQL、数据库及 provenance adapter 无关。
3. 作者 raw backward 在 wrapper 归一化前已经错误。
4. 本地 wrapper 公式无误。
5. 玩家标签、位置和对象 identity 730/730 一致。
6. 未发现简单索引、shape 或 branch bug。
7. float64 在 N=55 正确、N=60 突发失败；高精度显示其本质是随规模恶化的精度边界。
8. 50 位和 100 位均恢复 N=60。
9. 50 位把 loose failure 推迟到 N=100；100 位在冻结 N≤100 网格全部正确。
10. 首个异常出现在根 `N_add._backward()` 的反卷积商索引 24。
11. 存在明显减法 cancellation，并由阶乘梯度继续放大。
12. 不同结构的稳定边界未测试：已按“发现原因即可终止”停止，不能声称结构依赖。
13. ExaShap 本地实现不可用，未交叉运行。
14. 这是当前 LExaShap 实现路径的有限精度故障；不能据此称为单纯 wrapper bug或一般算法逻辑 bug。
15. 已支持“该递推存在有限精度稳定性问题”，尚不支持“一般性的 Shapley 数值稳定性研究问题”。

## 准入结果

该证据达到 `FINITE_PRECISION_FAILURE_SUPPORTED`，但没有达到 `STRUCTURE_DEPENDENT_NUMERIC_FAILURE` 或 `GENERAL_NUMERICAL_STABILITY_RQ_SUPPORTED`。因此本轮收口，不执行 SHARED_HUB/BALANCED_HIERARCHY、Q9 大规模、完整报表、2C/2F，也不提出新算法。
