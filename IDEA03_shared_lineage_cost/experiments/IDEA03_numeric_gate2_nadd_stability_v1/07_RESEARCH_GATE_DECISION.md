# 研究门最终判断

## 最终状态

`LOCAL_IMPLEMENTATION_CHOICE_ONLY`

## 十五个问题

1. `N_add._backward()`需要 sibling product，是因为OR满足分布对child满足分布的导数等于其余child不满足分布的卷积积。
2. 作者使用反卷积是因为forward已保存总不满足乘积，可由“总积÷当前项”恢复sibling product；这是源码事实。降低内存或实现方便等动机未被论文说明。
3. 数学上不需要反卷积；需要的是`Q_-i`。
4. prefix/suffix在精确算术下完全等价，冻结对象上也逐项匹配oracle。
5. product tree同样完全等价。
6. 两种替代均在float64下修复N=60。
7. 修复后效率和恢复为1。
8. symmetry spread恢复为0。
9. 巨大阶乘梯度仍存在，但在正确sibling message下只产生约`1.7e-16`相对舍入，不再破坏最终结果。
10. 原失败点卷积数从11增至prefix/suffix 32、product tree 31；固定次数64、r=32时为31对92/91。
11. 原失败点峰值工作cells从117增至862/543；固定次数64、r=32时从128增至2241/773。
12. 显式message实现保持多项式同阶语境，但product tree保守分析可能带log r层因子；标准reverse-mode通过乘积电路可保持常数因子梯度开销，因此不存在必须接受反卷积的理论原因。
13. 不破坏lifting或d-tree共享；替换仅发生在单个`N_add`节点内部。
14. prefix/suffix scan、product tree和算术电路reverse-mode均是标准已有技术，标签为`STANDARD_AD_TECHNIQUE`。
15. 当前问题是作者局部实现选择。诊断实现存在有限缓存差异，但没有证据支持值得独立研究的稳定性—效率缺口。

## 停止决定

prefix/suffix与product tree以普通float64直接修复原失败点；product tree操作量为当前约1.55倍、缓存为有限局部增加，辅助运行时间没有变慢。更一般的reverse-mode算术电路结果说明全部偏导不需要除法型逆运算或超出常数因子的固有成本。

因此停止该数值稳定性研究方向，不执行结构族扩展、Q9重跑、完整报表、2C/2F，也不提出新算法。诊断替代保留为复现说明与潜在上游patch依据，但不覆盖作者源码。
