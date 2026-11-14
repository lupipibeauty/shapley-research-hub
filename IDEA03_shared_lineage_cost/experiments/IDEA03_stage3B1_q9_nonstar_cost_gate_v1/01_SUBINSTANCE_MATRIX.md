# 01 子实例矩阵

## Material Passport

- Input: Stage 3A冻结的Q9-L/Q9-H顺序
- Objects: 2 families × 3 prefix sizes × 2 player boundaries = 12
- Selection changed after results: no

| 对象 | 玩家 | witness | 最大玩家度 | 最大overlap | overlap≥2 | 分量 | incidence cycle rank | incidence/primal width上界 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| L4-P1 | 20 | 4 | 1 | 0 | 0 | 4 | 0 | 1/4 |
| L8-P1 | 40 | 8 | 1 | 0 | 0 | 8 | 0 | 1/4 |
| L12-P1 | 60 | 12 | 1 | 0 | 0 | 12 | 0 | 1/4 |
| H4-P1 | 11 | 4 | 4 | 3 | 6 | 1 | 6 | 3/4 |
| H8-P1 | 21 | 8 | 8 | 3 | 16 | 1 | 12 | 3/4 |
| H12-P1 | 31 | 12 | 12 | 3 | 21 | 1 | 18 | 3/4 |
| L4-P2 | 12 | 4 | 1 | 0 | 0 | 4 | 0 | 1/2 |
| L8-P2 | 24 | 8 | 1 | 0 | 0 | 8 | 0 | 1/2 |
| L12-P2 | 36 | 12 | 1 | 0 | 0 | 12 | 0 | 1/2 |
| H4-P2 | 9 | 4 | 4 | 1 | 0 | 1 | 0 | 1/2 |
| H8-P2 | 18 | 8 | 6 | 1 | 0 | 2 | 0 | 1/2 |
| H12-P2 | 27 | 12 | 6 | 1 | 0 | 3 | 0 | 1/2 |

P1每个witness包含5个玩家，因此即使L系列完全不共享，primal图仍含5-clique，宽度下界为4。真正区分L/H的是incidence cycle、overlap和分量连接，而不能只比较primal width。

原始结构、玩家和witness映射见 `results/subinstance_structure.csv`、`player_map.csv`、`witness_map.csv`。
