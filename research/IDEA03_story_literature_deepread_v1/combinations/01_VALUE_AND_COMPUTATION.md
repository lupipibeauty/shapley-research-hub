# 组合 01：VALUE_AND_COMPUTATION（A1 + A3 + D1）

## 一句话问题

真实买方决策诱导的跨指标互补，是否形成一种可被 SQL 来源结构利用、但不能由坐标独立归因直接得到的精确记录 Shapley 游戏？

## 依赖与删除检验

- A1 决定 `G` 的经济来源；A3 说明 `G` 的联合边际；D1 研究精确计算。
- 去掉 A1，A3 容易退化为任意造非线性函数；去掉 A3，价值可能可按坐标线性拆分；去掉 D1，仍是一项价值建模研究。
- 因而三者有依赖，但 D1 不是价值理论成立的必要条件；论文可以是“价值主线+算法贡献”，不能声称三者天然统一。

## 最强竞争

Abbas–Hazen、Data Shapley、MC-nets/Harsanyi、Standke–Kimelfeld、LExaShap/model counting。

## 最大风险

任务 `G` 可被标准 Boolean/MC-net 分解，数据库算法直接处理；剩下只是一套应用流程。

## 当前判断

`NEXT_ROUND_HIGH`。先冻结真实/可审计任务，再用成熟分解进行强攻击。

