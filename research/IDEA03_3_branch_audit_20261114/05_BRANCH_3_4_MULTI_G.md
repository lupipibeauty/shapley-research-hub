# IDEA-03-3-4：同一报表上的多个价值函数 G

## 判定

`SURVIVES_AUDIT`

## 研究问题

同一 SQL 来源和完整报表 \(Y(S)\) 已固定时，对多个外生价值函数 \(G_1,\ldots,G_K\) 计算精确 Shapley，哪些计算可复用？

## 分情形结论

### 可加 G

若

\[
G_k(Y)=c_k+\sum_m w_{km}g_{km}(y_m),
\]

则 Shapley 线性性直接给出坐标/分量归因的线性组合。Ieong 与 Shoham（EC 2005），PDF p. 5（PDF index 4）Proposition 5，证明 MC-net 各规则 Shapley 可相加；Livshits 等与 Standke--Kimelfeld 在聚合查询中也反复使用相同线性分解。此子情形为 `REDUCTION_COVERED`。

### 非可加 G

非可加 \(G_k\) 共享同一个 \(Y(S)\)，但其玩家边际不是坐标 Shapley 的简单后处理。已有 provenance、LMFAO/F-IVM 和多输出 AD 可共享来源/前向状态；没有找到同一问题下对多个非可加完整报表效用同时给出精确 record-level Shapley 的定理或作者实现。

Stage 2A 证明：不同 G 若分解后产生完全相同 DNF，可通过 complete-key cache 重用；它没有覆盖部分重叠、共同数值状态或多根 coalition-size 反向。

## 为什么暂不单设第三个 gate

本轮总 gate 上限为两个。非可加 multi-G 的决定性机制分别是 3-2 的共同数值状态与 3-3 的多根反向；先通过 GATE-A/B。若二者均无内部计算节约，multi-G 只剩输入/输出缓存和工程编排；若任一通过，再把多个预注册 G 作为其外部有效性场景，而不是新建第三条算法线。

## 保留边界

- 可研究：固定、预注册、具有实际产品含义的多个 G；同一来源状态上的精确复用。
- 不可声称创新：只缓存 SQL 报表、只复用完整相同 DNF、或把多个 G 并行运行。
- 输出 \(KN\) 是不可避免下界，不属于可消除冗余。
