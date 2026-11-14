# 02 SQL来源结构与数值状态审计

## 1. 两类复杂度严格分开

来源层只有六个三变量见证。令 `w_s=x_E x_B x_H`，全局 Boolean 来源为

\[
W=\bigvee_{s=1}^{6}w_s.
\]

STRICT_CONCENTRATED 与 STRICT_BALANCED 分别只在 `w_3` 中使用 `x_{E1}` 或 `x_{E2}`。两者均为16变量、6子句、18次字面出现、4个企业连通分量、primal graph min-fill width上界2；证明重叠对分别为3和2。

数值层不是 width=2 的 Boolean 图本身。它还需要把见证激活映射为35个统计坐标，再应用绝对误差、比例NULL规则和省际差异评分。因此本轮分别登记来源电路节点与数值分量数量，不用同一个“状态数”混写。

## 2. 28个 COUNT/SUM 坐标

对满联盟目标 `y_q^*>0` 的单调 COUNT/SUM 坐标，固定绝对误差保真度化简为

\[
v_q(S)=w_q\frac{y_q(S)}{y_q^*}.
\]

企业数是企业对象激活 DNF 的和；场所数、就业人数和制造业就业人数是六个见证指示量的加权和。28个坐标中，B2的制造业就业目标为0，该坐标在冻结损失下恒为0；其余27个坐标产生60个原始 Boolean 线性分量。这里不需要玩家联盟真值表。

## 3. 七个 ratio 坐标

每个 ratio 只由六个见证激活位决定。对全部64个见证状态计算冻结的 numerator、denominator、NULL及损失后，对见证位做精确 Möbius 展开：

\[
g(z)=\sum_{T\subseteq\{1,\ldots,6\}}a_T\prod_{s\in T}z_s.
\]

每个 `z_s` 本身是三事实合取；`∏_{s∈T}z_s` 因而仍是一个正 DNF 单子句，外层系数 `a_T` 可以为负。各ratio产生的非零原始分量数为：NAT 63、PA 7、PB 7、A1 2、A2 1、B1 2、B2 1，共83项。与60个线性分量合计，`v_fid` 有143个原始分量，合并完全相同 DNF 后为65个。

这一步枚举的是 `2^6=64` 个见证统计状态，不是 `2^16=65,536` 个玩家联盟。完整 `v_fid` 的分量中106个系数为正、37个为负；带符号线性组合不改变每个 Boolean 分量使用正 DNF 的事实。

## 4. 省际 gap

`v_gap` 同时保留 PA、PB 的制造业就业分子、就业分母和NULL状态：

\[
v_{gap}(z)=1-\ell\!\left(r_{PA}(z)-r_{PB}(z),r^*_{PA}-r^*_{PB}\right).
\]

同样在64个见证状态上做精确 Möbius 展开，得到49个非零、49个唯一 DNF 分量，其中25个正系数、24个负系数。它不是把两个省的单独 Shapley 事后相减，而是先构造联合评分，再利用 Shapley 线性性合并其 Boolean 指示分量。

## 5. 数学与语义核验

- 每个唯一 DNF 的官方 Boolean Shapley 均与独立精确枚举一致，容差 `1e-12`。
- 完整 `v_fid/v_gap` 的直接来源结果再与阶段1 oracle 比较；四个游戏—价值对象的最大误差为 `1.39e-16`。
- oracle 不参与 DNF、系数、缓存键或电路构造。
- NULL 与数值0严格区分；分母0时 ratio 为NULL。
- 结果文件：`value_components.csv`、`component_boolean_exactness.csv`、`exact_shapley_comparison.csv`。

因此本轮证明了“冻结G可被精确归约并求解”，没有证明任意实值整表价值都能用相同数量的分量处理。

