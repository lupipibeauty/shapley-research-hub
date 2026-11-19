# IDEA-03-3-5：统计坐标交互图的稀疏性

## 判定

`REDUCTION_COVERED`

## 研究问题

若完整报表价值可写成局部因子之和

\[
G(Y)=\sum_{r=1}^{R}g_r(Y_{C_r}),
\]

其中每个 \(C_r\) 只涉及少量坐标，坐标交互图稀疏是否产生独立的 Shapley 算法问题？

## 最强覆盖

1. Shapley 的加法性直接给出 \(\phi_i(G)=\sum_r\phi_i(g_r)\)。Ieong--Shoham（EC 2005）Proposition 5 在规则分解上给出线性输入规模的 Shapley 计算；它不依赖因子来自 SQL。
2. Igarashi、Izsak 与 Elkind（AAAI 2018），印刷 pp. 1063--1070，Theorem 8（p. 1067）：给定依赖图与价值 oracle，Shapley 对依赖度参数是 FPT。该图是玩家语义依赖图，不是统计坐标图，因此是相邻而非直接同题覆盖。
3. MC-net 的 agent graph 和有界依赖度游戏说明：一旦局部因子已显式给出，局部交互的归因已是成熟紧凑博弈表示问题。

## 对本题的含义

坐标交互图稀疏本身不构成独立缺口：若局部因子显式可得，按 Shapley 线性性精确分解即可。剩余难点是每个局部因子的 SQL provenance 是否共享、数值状态如何建立、以及多个根如何联合反向；这些分别属于 3-1、3-2、3-3。

## 不应混淆

- Myerson communication graph 约束联盟可行性，不是报表坐标交互图。
- 玩家 dependency graph 描述玩家边际依赖，也不等于坐标图。
- 如果 \(G\) 不是局部因子之和，而只是经验上 Hessian 稀疏，则不能直接使用加法分解。

本分支作为独立方向收尾；可作为 GATE-A/B 的结构参数，但不另设 gate。
