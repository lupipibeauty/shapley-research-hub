# LIT-007 模型与命题审计

Data Shapley 的重要贡献是把下游任务性能明确作为联盟 utility，并用标准 Shapley 公理给训练样本公平权重。它支持 A1 的基本主张“价值依赖用途”，但不把性能值自动解释为货币成交价。本项目额外给定固定收入 `R`，只用归一化贡献分配该收入。

论文的计算方法是近似：TMC 依赖随机排列与截断，Gradient Shapley 依赖可微训练。它们不利用 SQL lineage，也不保证本项目的精确 record-level Shapley。

对 A3，论文允许任意性能 metric，但没有为完整报表的跨指标互补建立经济来源；把任意 `G` 填入 Data Shapley 框架只是应用，不是新理论。
