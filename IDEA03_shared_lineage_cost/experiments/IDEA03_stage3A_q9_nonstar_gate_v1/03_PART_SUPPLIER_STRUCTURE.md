# 03 PART–SUPPLIER结构

## 二部图结果

| 指标 | 结果 |
|---|---:|
| PART节点 | 13 |
| SUPPLIER节点 | 51 |
| 实际pair边 | 52 |
| 连通分量 | 12 |
| 最大分量节点/边 | 9 / 8 |
| 最大节点度 | 4 |
| cycle basis大小 | 0 |
| min-fill width上界 | 1 |

度分布为：50个节点度1、1个节点度2、13个节点度4。完整边及每条边的witness数见 `results/part_supplier_edges.csv`。

## 解释

PART–SUPPLIER图本身是森林，不存在二部环；因此“Q9关系多、JOIN长”不能直接推出这一级图复杂。每个合格PART连接4个SUPPLIER，大部分SUPPLIER只连接一个PART，只有一个SUPPLIER连接两个PART。

但它也不是52个完全独立pair：同一PART自然连接4条pair边，另有一个共享SUPPLIER连接两个PART。进一步地，两条ORDERS记录各自连接了不同pair的witness，使完整来源分量从pair级52个合并为P2下50个、P1下10个。

因此，重复PARTSUPP只是第一层共享；P1的跨pair连接主要由PART/SUPPLIER主记录产生。二部图无环是限制条件，不能把本结果描述成高宽任意多对多网络。
