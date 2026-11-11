# H3-JV 数据模型与玩家映射

## 业务场景

平台将基础业务对象、事件事实和实体关联记录连接为地区层次报表，并按固定收益池计算输入记录的标准记录级 Shapley。D1-JV 是独立实验数据集，不修改 D1-P。

## 关系

- `BasicSource`：4个基础对象事实，玩家 p1--p4。
- `EventSource`：4个事件事实，玩家 p5--p8。
- `RelationSource`：8条实体—事件边；每两条边绑定为一个逻辑记录包，玩家 p9--p12。
- `J0Fact`：同一12玩家的独立事实控制视图，仅用于无跨玩家JOIN对照。
- `Hierarchy`：A1/A2→PA、B1/B2→PB、四叶→NAT，固定外生。
- `CategoryDimension`：C1为目标类别、C2为非目标类别，固定外生。
- `PlayerMap`：物理行到逻辑玩家的冻结映射。

联盟选择逻辑玩家；关系记录包的两条物理边始终同进同出。JOIN grounding从未成为玩家。

## 查询

- J0：每个玩家独立产生一个统计事实。
- J1：`BasicSource JOIN RelationSource` 与 `RelationSource JOIN EventSource` 两个二关系分支并集；每个输出需要两个玩家。
- J2：`BasicSource R(x) JOIN RelationSource S(x,y) JOIN EventSource T(y)`；每个输出需要三个玩家，同一基础/事件玩家参与多条grounding，同一业务key可由多条路径支持。

## 报表坐标

7个节点×5个指标，共35坐标：bag count、distinct key count、amount sum、目标类别bag count、目标类别distinct key count。SQL原始 `SUM` 的空组为NULL；进入价值层时显式归一化为0，原始列与归一化列均保存。

## 价值函数

- G0：35个满表归一化线性坐标的等权和。
- G1：每节点前4个覆盖率加目标比例绝对偏差评分，35坐标等权相加。
- G2：count、distinct、amount、target-share四统计族；`R=1000`，`lambda=0.5`，算术平均与几何平均各占一半。

三个游戏均满足 `V(空)=0`、`V(满)=1000`。不同游戏的支付差异不是算法误差。

