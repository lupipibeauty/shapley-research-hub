# `N_add` 数学还原

## 论文定义

作者论文第12–15页把 d-tree 解释为概率算术电路。Table 3 对独立 OR（`⊕`）给出

\[
\Pr[T]=1-\prod_{i=1}^r(1-\Pr[T_i]),
\qquad
\frac{\partial\Pr[T]}{\partial\Pr[T_i]}
=\prod_{j\ne i}(1-\Pr[T_j]).
\]

Shapley 版本把单个概率扩展为按联盟大小索引的向量，并把独立变量集合的组合变为多项式卷积。论文 Theorem 3.6 给出的总复杂度为 `O(|T|·|vars(T)|²)`；Algorithm 3 使用 bottom-up probability 与 top-down chain rule。

## 代码中的向量

对 child `i`，令变量数为 `n_i`：

- `a_i[s]=C(n_i,s)/2^{n_i}`：从该 child 变量中选择恰好 `s` 个的全部赋值质量；
- `p_i[s]`：其中使 child 公式成立的赋值质量；
- `q_i[s]=a_i[s]-p_i[s]`：使 child 不成立的赋值质量。

作者 `N_add` 的 forward 计算

\[
A=*_{i=1}^r a_i,qquad Q=*_{i=1}^r q_i,qquad p=A-Q,
\]

其中 `*` 是离散卷积。因此节点保存的是按联盟大小归一化的 satisfying distribution，而不是单一概率或原始模型数。

## backward

对 child `i`，由 `p=A-Q` 且 `q_i=a_i-p_i`，有

\[
\frac{\partial p}{\partial p_i}=*_{j\ne i}q_j=:Q_{-i}.
\]

`Q_{-i}` 定义了一个 Toeplitz 卷积线性算子；其转置乘父梯度得到 child 梯度。当前代码先保存总不满足分布 `Q`，再调用

\[
Q_{-i}=Q/q_i
\]

的浮点多项式反卷积恢复 sibling product，随后由 `compute_grad_for_conv_base_and_base_val` 构造转置卷积作用。

结论：数学上必须的是 `Q_{-i}`，不是“除法”或“反卷积”本身。
