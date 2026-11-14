# 标准技术覆盖审计

## 算术电路反向微分

Baur与Strassen（1983）证明：给定计算函数的算术电路，同时计算函数及其全部一阶偏导只需常数因子的非标量运算开销，核心不依赖“总乘积除以当前因子”。作者论文自身在第12页脚注2明确把该结果列为其梯度方法的基础，并在Theorem 3.6/Algorithm 3中使用bottom-up forward与top-down chain rule。

来源：

- Walter Baur and Volker Strassen, *The Complexity of Partial Derivatives*, Theoretical Computer Science 22 (1983), 317–330, DOI `10.1016/0304-3975(83)90110-X`，原文PDF：<https://web.vu.lt/mif/s.jukna/tropical/Baur-Strassen.pdf>。
- 本地作者论文：`aggregate_report_shapley/external/abramovich/source/LExaBan-LExaShap-main/Advancing_Fact_Attribution_for_Query_Answering.pdf`，第12–15页。

## Prefix/suffix与product tree

prefix/suffix是对结合运算的all-prefix scan在正向和反向序列上的直接应用；卷积是结合运算。Blelloch的经典scan技术报告把all-prefix computation作为通用算法构件，而非Shapley专用新技术。

来源：Guy E. Blelloch, *Prefix Sums and Their Applications*, CMU-CS-90-190 (1990)：<https://www.cs.cmu.edu/afs/cs.cmu.edu/project/scandal/public/papers/CMU-CS-90-190.html>。

平衡product tree及其sibling/complement向下传播同样是标准乘积电路reverse-mode。其作用是在不做逆运算的前提下复用中间乘积。

## 审计标签

`STANDARD_AD_TECHNIQUE`

本轮实现只是把标准乘积梯度技巧应用到作者已存在的 `N_add` 多项式向量，不构成新Shapley算法、数据库算法或新的知识编译方法。
