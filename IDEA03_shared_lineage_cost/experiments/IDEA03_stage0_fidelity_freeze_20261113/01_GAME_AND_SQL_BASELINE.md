# Q、G 与玩家集合基线

## 1. 不可混同的历史游戏

| 系列 | 实际玩家 | SQL / Q | 外生对象 | 统计输出 | 价值与 oracle | 已有求解器与可复用部分 |
|---|---|---|---|---|---|---|
| D1-P | 12个逻辑 `record_id` 包；不是逐物理行 | 四个 BasicSource `UNION ALL`，`LEFT JOIN OptionalAttribute`，再按固定层次展开 | Hierarchy、CategoryDimension、owner mapping | 全国/2省/4市 × 5指标 = 35坐标：记录数、E1目标数与占比、属性存在数、E2目标占比 | V1 坐标评分；V2 四统计族算术/几何联合；4096联盟与 exact targets | 增量充分统计、B0--B3、H5/H5-R。只能复用“充分状态/生成函数/共享求解”思想与程序部件，不能复用玩家映射 |
| P3 | 13个物理事实：4 Entity、6 Link、3 Attribute | `Entity JOIN Link JOIN Attribute` 后按 A/B 分组 `COUNT DISTINCT entity` | Group 与 owner map；owner 仅事后汇总 | `q_A,q_B` 两坐标 | `G0=q_A+q_B`、`G1=min(q_A,q_B)`；8192联盟 SQL/Python oracle | 原生 MTBDD；H1/H2 Boolean 分解后的官方 LExaShap。可复用 DISTINCT lineage 和 Boolean 组件适配 |
| H3-JV | 12个逻辑玩家；RelationSource 的两条物理边绑定成一个玩家 | J0 独立事实；J1 两个二关系 JOIN 分支并集；J2 三关系链 JOIN | Hierarchy、CategoryDimension | 7节点 × bag count、distinct key、amount sum、目标 bag/distinct = 35坐标 | G0线性、G1坐标评分、G2四族联合；每单元4096联盟 | H3/H5 状态与共享算法；玩家绑定和统计族均与本阶段不同 |
| F0 | E/B/H 每条物理行独立；D不参与 | `B JOIN E USING(eid) JOIN H USING(sid) JOIN D USING(city)`；eligible `DISTINCT sid,eid,city,industry,workers`；全国/省/市展开 | D(city,province)、nodes 报表骨架 | 7节点 × enterprise/site distinct、workers/mfg sum、mfg share = 35坐标 | 历史 G0/G1/G2 或 GR/GL/GC；E0 有4096联盟 SQL oracle | `report_python`、SQL、来源 DNF、官方 LExaShap adapter、Harsanyi；本阶段主入口 |
| F1 | 2E+4B+4H+6个 R1 site-city 物理事实，N=16 | 在 F0 上增加 `JOIN active_r R1 USING(sid)` | D、nodes | 同35坐标 | G0/G1/G2；仅65个确定性 SQL 样本/游戏 | 适合研究 site-location 证明，但尚无新保真度的完整同目标适配 |
| F2-deep | 2E+4B+4H+4个 R2 entity-city 物理事实，N=14 | 在 F0 上增加 `JOIN active_r R2 USING(eid)` | D、nodes | 同35坐标 | G0/G1/G2；仅65个确定性 SQL 样本/游戏 | 形成同一实体到多个城市的共享来源；适合阶段1结构扩展 |
| F2-controlled | 2E+4B+4H+6个 R2，N=16 | 同 F2；集中/分散只改变省内城市重连 | D、nodes | 同35坐标 | 历史 GC；390个 SQL/Python mask 检查 | 不是跨省控制；省级 GC DNF 不变，不能作为 03-2D 的充分操纵 |
| TPC-H SF0.1 | Order/Lineitem/Supplier/Part 物理事实 | 保存的自然抽取与 supplier74 压力抽取 | Customer/Nation/Region | 地区/国家结构指标及历史价值 | N≤16 oracle | 只作为外部结构存在性证据；不是冻结主游戏 |

## 2. 阶段1的主要算法实验起点

冻结入口命名为 `FID_F0_N12`，引用而不改写历史夹具 `E0_F0_K2_N12`：

- 4条 E、4条 B、4条 H，共12个独立物理事实玩家；
- D 与7节点报表骨架外生；
- 使用 `report_f0.sql` 的全 JOIN 语义和35坐标；
- 历史 canonical 已逐一核验4096个联盟 SQL 与 Python 报表；
- 阶段0只替换 G，不改变 Q、玩家、数据或历史阈值实验。

选择它是为了建立无歧义的正确性入口，不是因为它代表困难实例。阶段0审计显示新主保真度在该夹具上只有16个不同值和15个非零 Harsanyi 项；因此阶段1若研究表示规模，必须在通过 `FID_F0_N12` 正确性门后，转到保持同一 G 定义的 F1/F2 或其他预先冻结结构夹具。不能用 F0 的容易性宣布一般结论。

## 3. 冻结 SQL 口径

主 SQL：

`IDEA03_2_joint_value_deepening_v1/sql/report_f0.sql`

固定语义：

1. 联盟分别过滤 E、B、H 玩家表。
2. `B JOIN E` 通过 `eid`，`B JOIN H` 通过 `sid`，再连接固定 D。
3. eligible 层对 `(sid,eid,city,industry,workers,province)` 去重。
4. 每条 eligible 行展开到全国、省、市三个节点。
5. `COUNT(DISTINCT eid)`、`COUNT(DISTINCT sid)`、`SUM(workers)`、条件 `SUM(workers)`。
6. 空组的四个数值指标输出0；分母为0的 `mfg_share` 输出 SQL `NULL`，不提前改写为0。

这不是 D1-P 的逻辑记录包 SQL，也不是后续“分指标 JOIN”稳健性口径。任何口径变化都必须生成新的 Q 版本。

## 4. 来源构造复用边界

可直接复用：

- `joint_game.py` 的 F0 active rows、35坐标 evaluator、site-city DNF；
- `study.py` 的 N=12 物理玩家夹具、精确 Shapley、Möbius/Harsanyi 审计；
- P3 的 Boolean DNF→官方 LExaShap 适配模式；
- H5-R 的基数条件权重、前后缀和多输出共享正确性检查思想。

不可直接复用：

- D1-P/H3 的玩家包映射；
- 历史 G0/G1/G2/GC 的结果作为新 G 的 oracle；
- 从真值表构建的 Reduced ADD 作为非枚举算法；
- TPC-H 历史值的运行时间作为本游戏排名。
