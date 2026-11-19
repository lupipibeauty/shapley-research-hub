# 组合 07：PLAYER_AND_COMPUTATION（C1 + C2 + D1）

## 一句话问题

业务上合理的玩家粒度是否同时改变来源表示宽度和 all-player 精确 Shapley 的可解性？

## 依赖与删除检验

- 玩家合并会改变游戏，不只是降低 `N`；因此计算优势必须在语义一致的目标下比较。
- 去掉 C1/C2，D1 仍成立；去掉 D1，玩家语义仍需确定。
- 共同机制可能是“受业务约束的合法 quotient game”对电路宽度/依赖度的影响。

## 最强竞争

FGSV、Owen、2D-Shapley、bounded-dependency games、LExaShap/model counting。

## 最大风险

为了计算快而任意打包玩家，改变了研究问题；或合法打包只产生显然的变量减少。

## 当前判断

`NEXT_ROUND_MEDIUM`。先证明哪些打包保持目标语义，再谈复杂度。

