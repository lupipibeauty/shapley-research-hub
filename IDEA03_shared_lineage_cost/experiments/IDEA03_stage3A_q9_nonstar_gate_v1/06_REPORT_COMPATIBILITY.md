# 06 完整统计产品兼容性

## 自然输出骨架

当前Q9基础行天然提供 `nation × order_year` 分组。NATION含固定 `regionkey`，因此无需改变内生JOIN即可形成：

`Global → RegionKey → Nation`

Year作为横向分组。若需要地区名称，只需对外生REGION维表做标签映射，不改变P1/P2来源玩家。

正式数据覆盖：5个regionkey、21个nation、7个year，共126个非空nation-year组。

## 可自然产生的指标

同一批Q9基础行直接支持：

- `distinct_order_count`
- `distinct_supplier_count`
- `lineitem_count`
- `quantity_sum`
- `revenue_sum`
- `supply_cost_sum`
- `profit_sum`
- `profit_margin = profit_sum / revenue_sum`

所有126个组的revenue均非零。示例计算结果保存在 `results/report_compatibility_groups.csv`；该文件只证明字段和分组可构造，不是冻结的新价值函数。

## 适用性边界

Q9原始业务问题的核心输出是nation-year利润，其他计数与金额指标都来自同一事实集合，属于合理经营/供应链统计，而不是为了凑35坐标添加的无关量。层次扩展利用NATION已有regionkey，也不是人为增加桥表。

因此Q9具有完整统计产品兼容性，不触发 `REPORT_ADAPTATION_TOO_ARTIFICIAL`。但是否采用全部指标、层级权重和fidelity/ratio/gap仍需下一阶段单独冻结；本轮没有设计新G。
