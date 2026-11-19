# LIT-008 定理审计

## 核心定义

对数据分布 `D`、potential `U` 和目标样本规模 `m`，distributional Shapley 取随机背景数据集上的 Data Shapley 期望。它解决固定样本集依赖和对未见点估值的问题。

## 核心定理

- Theorem 2.3：把 distributional Shapley 写成随机规模背景集上加入点 `z` 的期望边际。
- Theorems 2.7–2.8：在 `beta(k)`-Lipschitz stability 下，对分布/点扰动给出稳定性界；Theorem 2.8 的点稳定界为 `E_k[beta(k)] d(z,z')`。
- Theorem 3.1：D-Shapley 的 Monte Carlo 估计无偏，并给出对所有待估点的高概率误差界。

## 对 IDEA-03 的边界

它是“跨数据集可迁移价值”的强理论，但本项目的记录是固定数据库中的物理事实，目标是一次完整产品销售的固定玩家游戏。除非研究问题转向从某个记录生成分布估计未见记录的期望价值，否则不能用 distributional Shapley 直接归约。它仍要求任务/算法/potential 固定，不能代替 A1/B1 中 `G` 的经济识别。
