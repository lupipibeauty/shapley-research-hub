# 最强先验工作攻击

## 攻击 1：价值层已经成熟

Blackwell 与 Abbas–Hazen 已说明信息强弱和跨任务价值排序；Data Shapley 已说明给定任务 utility 后用 Shapley 归因。若贡献只是“给完整报表选择一个 `G`”，则不足。

**尚存问题**：可观察的完整统计产品买方任务如何映射为逐联盟 `G(Y(S))`，以及这种任务结构是否与关系来源产生新性质。

## 攻击 2：玩家/组层已经成熟

FGSV Theorem 1 说明 faithful group value 是个体 Shapley 之和；Owen value 处理先验联盟；2D-Shapley 处理样本×特征块。若贡献只是“记录按 owner 求和”或“把数据分块”，则高度覆盖。

**尚存问题**：owner 直接作为玩家、事实包作为不可分割供给单位和记录后汇总是三个不同游戏；业务控制关系与 SQL 多表 witness 如何共同限制合法边界。

## 攻击 3：非可加交互已有通用表示

MC-nets、Harsanyi dividends、Boolean 门槛分解和模型计数能表示/求解大量显式交互。若 `G` 只是二项乘积、min 或门槛，A3 容易被归约。

**尚存问题**：由真实多指标任务诱导、同时跨 DISTINCT 身份和数值聚合的结构化交互是否仍能被现有表示紧凑处理。

## 攻击 4：数据库 Shapley 已有精确复杂度理论

Livshits、Standke–Kimelfeld、Abramovich、Kara 等已给 tuple/aggregate/circuit Shapley 的广泛可解与困难边界。不能以旧实现慢或状态多宣布新瓶颈。

**尚存问题**：完整报表整体 `G`、多根共享和多任务在线复用是否落入现有单根/局部聚合模型；需要同目标精确归约审计。

## 攻击 5：多任务/动态复用已有框架

Yang 2026 直接使用 player-by-task matrix；Xia 2025 处理数据添加删除；F-IVM/LMFAO 处理动态/批量分析。

**尚存问题**：固定 SQL 来源、多个非可加 `G` 的精确 all-player Shapley 是否有任务无关充分状态；属性修订下哪些联盟边际可证明不变。

## 攻击 6：复制鲁棒市场已有因果解决方案

Falconer et al. Proposition 4.5 在特定回归市场中用 interventional lift 获得严格复制鲁棒。若 A2/C1 指的是伪身份复制特征，该文是强覆盖。

**尚存问题**：层次小计重复、同一事实多证明、所有者拆分和特征复制不是同一复制语义，必须逐类建模。

