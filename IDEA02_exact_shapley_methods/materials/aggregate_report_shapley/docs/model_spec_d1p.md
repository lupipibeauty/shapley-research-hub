# D1-P 多源层次汇总报表模型规范

状态：v3.2 冻结候选规范，尚未实现或运行。D1-P 为完全合成控制数据，人口统计名称只用于直观解释。

## 通用对象与人口示例

| 通用对象 | 人口示例 | 算法字段 |
|---|---|---|
| 逻辑记录包 | 一个人的基本信息及可选就业记录 | `record_id` |
| 数据所有者 | 城市、机构或跨城市提供者 | `owner_id` |
| 叶节点 | 城市 | `leaf_node_id` |
| 中间节点 | 省份 | `parent_node_id` |
| 根节点 | 全国 | `root_node_id` |
| 类别 A | E1/E2 | `category_a_id` |
| 类别 B | 制造业/服务业 | `category_b_id` |

## 数据库关系

```text
BasicSource_A1(record_id, leaf_node_id, category_a_id)
BasicSource_A2(record_id, leaf_node_id, category_a_id)
BasicSource_B1(record_id, leaf_node_id, category_a_id)
BasicSource_B2(record_id, leaf_node_id, category_a_id)

OptionalAttribute(record_id, attribute_present, category_b_id)
Hierarchy(leaf_node_id, parent_node_id, root_node_id)
CategoryADim(category_a_id, category_a_group)
CategoryBDim(category_b_id, category_b_group)
OwnerMap(record_id, owner_id)
```

基本来源表用 `UNION ALL` 形成统一逻辑视图。只有在 `record_id` 不重复、字段和编码一致、叶节点归属唯一时，分表与合表才预期等价。可选属性使用 `LEFT JOIN`，缺失属性不能删除基本记录。

物理来源分区不自动等于 Shapley 玩家或 owner。第一轮玩家始终是逻辑记录包；`OwnerMap` 只用于把记录支付汇总为收款表，不把 owner 改成玩家。

## 玩家与联盟

一个记录玩家是同一 `record_id` 的内生元组包。维度表为外生固定上下文，不是玩家。联盟只筛选记录包；查询、映射、骨架和价值参数固定。owner 作为玩家属于独立 O-game，不进入 S0/S1。

## 固定报表

节点共 7 个：1 个根、2 个中间节点、4 个叶节点。每个节点保留：

1. `record_count`：总记录数；
2. `category_a_target_count`：类别 A 目标组记录数；
3. `category_a_target_share`：目标组占比；
4. `attribute_present_count`：存在可选属性的记录数；
5. `category_b_target_share`：在存在可选属性的记录中，类别 B 目标组占比。

固定输出为 `7×5=35` 个坐标。空节点保留；计数为 0，占比为 `NULL`。报表状态只保存四个可加基础计数，占比在读取状态时派生。

## D1-P 完整数据校验值

- 记录数：12；
- 类别 A 目标组：6；
- 有可选属性：10；
- 类别 B 目标组：6；
- 根节点目标组占比：`6/12=1/2`；
- 根节点类别 B 目标占比：`6/10=3/5`；
- 联盟数：4,096；
- 每条记录更新 3 个祖先节点。

当前冻结配置使用节点 `COUNTRY/A/B/A1/A2/B1/B2`。四个内部计数的完整值为：

| 节点 | 总数 | E2 | 有属性 | 制造业 |
|---|---:|---:|---:|---:|
| A1 | 2 | 1 | 2 | 1 |
| A2 | 2 | 1 | 1 | 1 |
| B1 | 4 | 2 | 3 | 2 |
| B2 | 4 | 2 | 4 | 2 |
| A | 4 | 2 | 3 | 2 |
| B | 8 | 4 | 7 | 4 |
| COUNTRY | 12 | 6 | 10 | 6 |

该叶节点缺失分布与 v3.2 文档的 fallback 演示不同；因为仓库配置已存在，必须以本表和逐行配置为准。

### 冻结配置的已知联盟断言

固定玩家位序为 `p1..p12`。对 `S={p1,p2,p3}`（位掩码 7）：

- A1：总数2、E2数1、有属性2、制造业1；
- A2：总数1、E2数0、有属性1、制造业1；
- A：总数3、E2数1、有属性3、制造业2；
- B、B1、B2：四个内部计数均为0，两个比例为 `NULL`；
- COUNTRY：总数3、E2数1、有属性3、制造业2。

S1 将来实现时使用该断言，不套用 v3.2 fallback 的 `{r01,r02,r03}` 期望值。

## 价值与分配边界

V-count 是同一完整层次报表上的可解析负对照。V1_default_v3_2 是坐标得分的固定非负加权和，因此标准 Shapley 可对“各坐标得分游戏”利用线性性分解；这不表示比例坐标是原始分子/分母 COUNT 的线性函数。v4.0 的数学预审表明，在满联盟参考值固定、坐标有效性不随联盟变化时，计数覆盖率和带覆盖率的比例得分均单调，V1 因而单调；若各统计族得分单调，V2 的非负算术项与加权几何项也单调。该结论仍须按 `docs/value_property_audit.md` 在全部联盟上程序核验。V2 不能预设可逐族独立分配。报表节点层次不是玩家层次，S0/S1 不计算层次值。

## 必须通过的实现不变量

- 分表 SQL、统一视图 SQL、增量状态对全部 4,096 个联盟逐坐标一致；
- `LEFT JOIN` 后基础记录数不因属性缺失减少；
- 任一连接产生的物理行不会改变逻辑玩家数；
- `COUNT(*)` 与 `COUNT(DISTINCT record_id)` 的差异被显式记录；
- V0 下每条记录支付 `R/12`；
- V-count 下支付与祖先节点闭式公式一致；
- V2(`λ=0`) 与 V1_default_v3_2 完全一致；
- 冻结 V1/V2 若出现负边际、负支付或非单调联盟，原样保留并优先检查实现、NULL、动态归一化和 JOIN 计数单位；
- 每种有效分配的支付总和为 `V(N)-V(∅)`。
