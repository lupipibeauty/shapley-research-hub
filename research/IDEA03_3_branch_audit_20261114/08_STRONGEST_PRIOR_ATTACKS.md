# 对 IDEA-03-3 的最强先行工作攻击

## 攻击 1：这只是 provenance 公共子式消除

成立部分：Green/Amsterdamer 的 provenance 代数以及标准 DAG hash-consing 已覆盖公共表达表示；若贡献只在共享子 DAG，创新不足。

未成立部分：现有直接证据没有把多个报表根的 coalition-size Shapley backward 合并。故 3-1 本身降为表示层，问题收缩到 3-3。

## 攻击 2：多聚合早已由 LMFAO/F-IVM 解决

成立部分：共享 join、扫描、view、向量聚合和多个 group-by 输出是成熟数据库技术。

未成立部分：这些系统没有物理事实联盟、Shapley 权重或全玩家输出。它们是 GATE-A 必须击败的强前端，而不是 L5 的直接覆盖。

## 攻击 3：自动微分一次就能给出全部贡献

成立部分：Baur--Strassen 和 Abramovich Theorem 3.6 说明单根 all-input 梯度/归因可以高效反向，不应逐玩家重跑。

未成立部分：完整报表要求多根、coalition-size 向量消息和显式 \(M\times N\) 输出。普通 scalar AD 定理不能直接推出完整 Jacobian 免费；但输出下界也限制了可宣称的收益。GATE-B只检验中间消息复用。

## 攻击 4：稀疏交互图就是 MC-net/有界依赖度游戏

基本成立。若价值已显式分解为局部因子之和，MC-net 加法分解和 Shapley 线性性已经给出精确算法；玩家 dependency degree 还提供参数化边界。因此 3-5 不保留为独立创新。

## 攻击 5：多个 G 只是多次调用同一算法

对可加 G 成立；对非可加 G 只证明了 \(KN\) 输出下界和可共享前端，尚未找到精确归因层的直接覆盖。3-4保留，但其可证机制必须来自 GATE-A/B，而不是“业务上有多个 G”这一事实。

## 攻击 6：已有阶段已经证明共享更快

不成立。Stage2A 只证明完全相同 DNF 的缓存；Stage3B1 反而表明表示选择会改变方向，不能从单一 solver 的结果推断固有复杂度。

## 最保守的可发表主张边界

当前不能声称“提出了完整报表多输出 Shapley 算法”。最多能说：现有证据留下两个精确问题——异构聚合的 coalition-size 联合状态，以及共享 DAG 的多根 Shapley 消息——需要两个小型判别 gate；非可加 multi-G 是它们的应用场景，而非第三个无依据算法点。
