# 反卷积必要性审计

## 三条等价路径

给定 `q_1,...,q_r`：

1. `CURRENT_DECONVOLUTION`：先算 `Q=*q_i`，再逐项 `Q/q_i`；
2. `PREFIX_SUFFIX`：令 `L_i=*_{j<i}q_j`、`R_i=*_{j>i}q_j`，直接 `Q_{-i}=L_i*R_i`；
3. `PRODUCT_TREE`：平衡构造乘积树，从根向下把“祖先外部乘积 × sibling product”传播给每个叶，叶的外部乘积即 `Q_{-i}`。

三者在精确算术下完全相同。后两者只有卷积与乘加，不需要逆运算；它们不改变 d-tree、lifting、child `Value` 对象或最终链式法则。

## 作者选择原因的证据等级

- 论文支持：梯度法通过链式法则一次计算所有事实，并声明 Shapley 总复杂度 `O(|T|n²)`；这是 `SUPPORTED_BY_SOURCE`。
- 源码支持：实现已经持有总乘积 `Q`，逐 child 反卷积得到 sibling product；这是 `SUPPORTED_BY_CODE`。
- “作者为了降低存储、避免构造 prefix/suffix 或实现方便而选择反卷积”：论文和源码注释没有说明，只能标记 `INFERRED_FROM_IMPLEMENTATION`，不得当作作者明示动机。

因此，反卷积是当前实现复用总乘积的一种局部方式，而非数学定义要求。
