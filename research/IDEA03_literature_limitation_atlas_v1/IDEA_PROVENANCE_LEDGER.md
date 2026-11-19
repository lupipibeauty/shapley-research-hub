# Idea 来源账本

## 来源标签

- `USER_SEED`：研究者主动提出的直觉、矛盾或现实判断。
- `PAPER_EXPLICIT`：原文明确提出的问题或未来工作。
- `THEOREM_BOUNDARY`：由原文假设、定义或定理条件推导的边界。
- `CROSS_PAPER_INFERENCE`：跨论文比较形成的接缝。
- `EXPERIMENT_TRIGGER`：历史实验反常结果或失败机制。
- `CODEX_EXTENSION`：Codex 对研究者种子的形式化、变体或机制扩展。

## 记录规则

Idea 的“提出者”不是简单的人名，而是记录思想链条。例如：

`USER_SEED → CODEX_FORMALIZATION → LITERATURE_AUDIT → USER_DECISION`

Codex 不得把 `CROSS_PAPER_INFERENCE` 或 `CODEX_EXTENSION` 写成作者原文结论；也不得把研究者未确认的扩展并入用户种子。

## 当前候选链条

| 候选 | 当前来源链 | 当前状态 | 仍由研究者决定的核心问题 |
|---|---|---|---|
| R1 表示冗余与真实互补 | `PAPER_EXPLICIT(Blackwell/Signals) + CROSS_PAPER_INFERENCE + EXPERIMENT_TRIGGER` | 候选 | 产品价值是否包含使用便利；希望保持哪一种等价 |
| R2 多任务精确复用 | `USER_SEED + CROSS_PAPER_INFERENCE(LMFAO/F-IVM/D-Shap)` | 候选 | 什么是真实而非人为构造的任务族 |
| R3 决策诱导互补 | `USER_SEED + THEOREM_BOUNDARY(决策价值/MC-net)` | 候选 | 研究真实行动价值还是结构压力测试 |
| R4 合法玩家边界 | `USER_SEED + THEOREM_BOUNDARY(FGSV/Owen)` | 候选，Owen 正文缺失 | 技术贡献玩家还是可议价供给玩家优先 |
| R5 动态精确归因 | `EXPERIMENT_TRIGGER + THEOREM_BOUNDARY(dynamic/F-IVM)` | 候选 | 修订后玩家身份是否保持 |
| R6 任务域稳健贡献 | `CROSS_PAPER_INFERENCE(Signals/Abbas--Hazen)` | 候选 | 希望跨哪些实际任务保持排序 |
| R7 SQL 到游戏的可认证编译 | `EXPERIMENT_TRIGGER + THEOREM_BOUNDARY(MC-net/model counting)` | 候选 | 编译器还是求解器是主要研究对象 |
| R8 语义依赖上界与发现 | `CROSS_PAPER_INFERENCE(provenance/dependency)` | 候选 | 需要最小依赖图还是保守可计算证书 |
| R9 两级所有权结算 | `USER_SEED + CROSS_PAPER_INFERENCE(Owen/markets)` | 候选 | 真实合同权利结构是什么 |
| R10 三账本收益分配 | `CROSS_PAPER_INFERENCE(markets/database Shapley)` | 候选 | 最终解释买方支付、平台净收入还是来源份额 |
| R11 公开规则驱动多G基准 | `CODEX_EXTENSION + BUSINESS_EVIDENCE_TRIGGER` | 候选工具方向 | 公共任务是否符合研究者希望解释的产品场景 |
| R12 背景信息敏感区间 | `CROSS_PAPER_INFERENCE(Signals/incomplete games)` | 候选，原文缺口大 | 研究点估计、区间还是稳健排序 |

上述来源链是 V1 审计结果，不表示 Codex 对创新性或优先级作出结论。研究者可以修改来源链和核心问题。

