# IDEA-03-3-3：多输出、全玩家 Shapley 反向共享

## 判定

`UNCLEAR_NEEDS_ONE_GATE`

## 研究问题

给定一个共享算术/知识编译 DAG 和 \(M\) 个报表根，能否共享 coalition-size 前向消息与反向消息，在不可避免的 \(MN\) 输出之外减少逐根重复计算？

## 最强已有工作

1. Baur 与 Strassen（Theoretical Computer Science 22, 1983，PDF pp. 1--2）：对一个标量有理函数，函数值及其全部一阶偏导的 straight-line complexity 至多是原函数的常数倍（论文主结果写为 \(L(f,\partial f/\partial x_1,\ldots,\partial f/\partial x_n)\le 3L(f)\)）。这是“单根、全输入梯度”的强攻击，不是完整 Jacobian 的免费计算定理。
2. Abramovich 等（PVLDB 2025），Theorem 3.6：给定一个 d-tree \(T\)，全部变量 Banzhaf 为 \(O(|T|)\)，Shapley 为 \(O(|T|\,|vars(T)|^2)\)。Algorithms 2--3 的实现和本地作者代码均从一个根执行 backward；其 Shapley 消息包含 coalition-size 概率向量，不等同于普通标量 AD。
3. ProvSQL 当前文档 `shapley_all_vars(token, ...)`：一个 provenance token/root 输入、输出该根的全部变量贡献；文档未提供多 token 的联合 Jacobian API。
4. LMFAO Section 3.5：多个聚合根可共享前向扫描/视图，但不计算 Shapley。

## 下界与未决点

- 显式坐标归因矩阵必然写出 \(MN\) 个数；任何声称次于 \(MN\) 的总运行时间都必须采用压缩输出，不能与显式矩阵比较。
- 单根 all-player 已被成熟算法直接覆盖。
- 仍未找到正文证明：多个根共享同一子 DAG 时，LExaShap 的 coalition-size 反向消息可以在输出下界之外按公共子图复用，或证明这种复用不可能。

## 唯一 gate：GATE-B

冻结一个共享 DAG、固定 \(N\) 和一组预先定义的 \(M\) 个根，比较：

1. 每根独立执行作者单根 backward；
2. 公共前向只计算一次、按根批处理的精确反向；批处理可以输出稠密 \(M\times N\) 矩阵，但不得更改消息语义。

计时必须拆分 DAG 构造、共享前向、反向传播、结果 materialization；另报告公共节点比例、根到节点可达矩阵稀疏度、消息元素数和 oracle 误差。只有在扣除 \(MN\) 写出后，内部消息量随共享子图而显著低于逐根和，才支持独立研究空间。否则归类为 `ENGINEERING_ONLY`。
