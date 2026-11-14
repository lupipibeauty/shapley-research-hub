# 01 有序表示诊断器验证

## 预注册顺序

运行前在 `config/stage2b0_protocol.json` 冻结且仅使用三种顺序：

1. `PHYSICAL_E_B_H`：E1–E4、B1–B6、H1–H6；
2. `MIN_FILL_SOURCE`：来源 primal graph 上确定性 min-fill，平局按新增边数、当前度数、玩家编号处理；
3. `ENTERPRISE_COMPONENT_GROUPED`：按企业分量，先逐站点消去 B、H，再消去该企业 E。

没有根据结果增加第四种顺序。

## 语义验证

12个非同构来源代表 × 3种顺序共36次执行全部满足：

`VE model count = 六子句 DNF 容斥 model count`

两种企业度序列对应的精确满足赋值数分别为34,323和34,911；同一来源实例的三种顺序结果完全一致。验证记录见 `results/semantic_validation.csv`。这证明顺序只改变中间表示，不改变布尔来源语义。

## 严格配对结果

| 实例 | 企业度序列 | 顺序 | 玩家阶段最大 frontier | 最大乘积因子单元 | 生成因子单元 | 冷运行时间 |
|---|---:|---|---:|---:|---:|---:|
| concentrated | 3/1/1/1 | PHYSICAL_E_B_H | 9 | 1,024 | 3,364 | 79.62 ms |
| concentrated | 3/1/1/1 | MIN_FILL_SOURCE | 5 | 64 | 556 | 9.63 ms |
| concentrated | 3/1/1/1 | ENTERPRISE_COMPONENT_GROUPED | 3 | 16 | 448 | 7.64 ms |
| balanced | 2/2/1/1 | PHYSICAL_E_B_H | 6 | 128 | 1,018 | 17.29 ms |
| balanced | 2/2/1/1 | MIN_FILL_SOURCE | 4 | 32 | 514 | 7.43 ms |
| balanced | 2/2/1/1 | ENTERPRISE_COMPONENT_GROUPED | 3 | 16 | 442 | 6.13 ms |

时间只是一轮描述性冷运行，不用于显著性检验或实现性能排名；frontier和因子单元是本阶段的主要诊断量。

## 对阶段2A 26/28节点的核验

阶段2A的官方 LExaShap arithmetic DAG 是 concentrated 26、balanced 28；本阶段的参考 VE 不暴露同一种 DAG 节点，因此不能把26/28作为同指标数值“复现”。在三个显式顺序下，concentrated 的中间表示从不小于 balanced：物理顺序和 min-fill 下明显更大，分量顺序下最大因子相同、总生成单元只差6。

因此，26/28不是企业集中度在固定顺序下的表示规律。证据支持它是“作者内部 d-tree/算术电路构造与该输入结构的交互结果”，但由于编译表示不同，不能进一步把两节点差异单因果归结为某一条未暴露的作者启发式。

## 自检

- 输入是否为直接来源因子：是。
- 是否读取联盟真值表：否。
- 顺序是否在运行前冻结：是。
- 三序语义是否一致：是，36/36通过。
- 是否把参考适配器称为成熟作者算法：否。
- 是否把单次计时当复杂度结论：否。
