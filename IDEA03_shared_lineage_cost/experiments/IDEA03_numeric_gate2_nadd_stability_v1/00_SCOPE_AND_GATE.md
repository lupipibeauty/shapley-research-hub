# 范围与研究门

本轮只审计 LExaShap `Value.N_add._backward()` 中反卷积的数学必要性，并比较当前反卷积、prefix/suffix sibling product 和平衡 product tree。不得修改作者源码、重跑 Q9、扩大数据库规模或把诊断替代称为新算法。

上一轮已确认 float64 失败始于根 OR 节点的多项式反卷积。本轮不重复扫描失败边界，只使用冻结 `N=10,30,55,60` 正确性对象以及固定总次数64、child数 `2,4,8,16,32` 的机制成本对象。

停止门：若标准 sibling-product 方法在 float64 恢复 N=60，保持同阶复杂度、有限额外存储且不破坏 lifted d-tree，则判定为局部实现选择并停止该研究方向。

实验网格冻结、停止门和证据分层参考了 Scientific Agent Skills 的实验设计与科学批判性分析流程：Timothy Kassis, Vinayak Agarwal, Yuhuan He, Darshil Patel, and Aubrey M. Brueckner, *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*, arXiv:2609.00065 (2026), <https://doi.org/10.48550/arXiv.2609.00065>。
