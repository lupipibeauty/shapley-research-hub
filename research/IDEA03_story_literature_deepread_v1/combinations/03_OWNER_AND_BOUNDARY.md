# 组合 03：OWNER_AND_BOUNDARY（C1 + C2 + A2）

## 一句话问题

当同一事实跨表、跨层次重复出现时，真实控制边界与信息等价性如何共同约束记录、事实包和所有者的固定收入份额？

## 依赖与删除检验

- C1 是玩家粒度；C2 是内外生边界；A2 是重复表示/信息等价。
- 去掉 A2，仍有标准 owner-vs-record 问题；去掉 C2，仍有记录打包；去掉 C1，A2 仍是价值表示问题。
- 当前尚未出现不可分割的共同定理，更多像三个边界审计的组合。

## 最强竞争

FGSV、Owen value、2D-Shapley、provenance 的 endogenous/exogenous tuples、replication-robust markets。

## 最大风险

业务合同先验决定玩家与收入池，数学部分只剩标准敏感性分析；或 FGSV/Owen 已覆盖主要规范要求。

## 当前判断

`NEXT_ROUND_MEDIUM`。必须先补 Owen 原文和真实供给/撤回规则；暂不作为主算法题。

