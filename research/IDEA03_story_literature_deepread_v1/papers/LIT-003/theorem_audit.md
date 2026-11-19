# LIT-003 定理审计

## Theorem 1

在论文五条组估值公理下，组 `S0` 的唯一值为：

\[
FGSV(S_0)=\sum_{i\in S_0} SV(i).
\]

附录 A.2 先用个体 Shapley 公理固定单例值，再由 faithfulness 固定外部划分变化，最后用 efficiency 得到组内求和。证明不使用 SQL、JOIN 或报表结构。

## 算法定理

引理/分解按 coalition size 与组内外人数整理 utility 系数；Theorem 2 使用一阶有限差分近似，Theorem 3 在稳定性条件下给出高概率误差与约 `O(n poly(log n))` utility 调用。它不是对任意数据库特征函数的精确多项式算法。

## 对 C1/C2 的覆盖边界

- 直接覆盖：在记录级游戏已经正确给定且 owner 只要求事后汇总时，FGSV 给出抗外部组拆分的组支付。
- 不直接覆盖：owner 自身作为可控制供给单位时的 owner-level characteristic function；跨表事实包的业务不可分割性；公共维表的外生/内生边界。
- 因而，FGSV 是 C1 的强反例和基线，但不能单独决定真实玩家单位。
