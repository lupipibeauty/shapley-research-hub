# 03 来源表示、联盟游戏与记录贡献比较

## Material Passport

- 阶段：IDEA-03 阶段1，实验3。
- 目的：只检查来源/价值表示，不做求解器速度排名。
- 状态：`VERIFIED_LOCAL_STRUCTURE_RESULTS`。
- 电路节点：`NOT_MEASURED_NO_ELIGIBLE_DIRECT_COMPILER`。

## 1. 来源结构

| 实例 | 重复进入见证的玩家 | 跨省 E | 重叠证明对 | primal 边 | 连通分量 | min-fill width上界 | raw DNF出现 | 唯一子句 | 唯一分量DNF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| STRICT_CONCENTRATED | 1 | 1 | 3 | 18 | 4 | 2 | 63 | 6 | 8 |
| STRICT_BALANCED | 2 | 1 | 2 | 18 | 4 | 2 | 63 | 6 | 8 |
| RELAXED_NO_CROSS | 2 | 0 | 2 | 18 | 4 | 2 | 63 | 6 | 8 |
| RELAXED_ONE_CROSS | 2 | 1 | 2 | 18 | 4 | 2 | 63 | 6 | 8 |

所有实例均有6个最小见证、18次变量出现和64个完整报表状态。

严格配对给出一个重要负面结果：重复玩家数从1增至2时，重叠证明对反而从3降至2；但图宽、DNF计数与 Harsanyi 数量均不变。因此“共享玩家更多”不是单一的表示规模参数。共享的集中程度、每个玩家度数和地区标签位置必须分开。

## 2. 冻结价值表示

| 实例 | G | G状态 | 非零联盟 | Harsanyi项 | 最高阶 | `v(N)` |
|---|---|---:|---:|---:|---:|---:|
| STRICT_CONCENTRATED | `v_fid` | 64 | 34,323 | 63 | 16 | 71/72 |
| STRICT_BALANCED | `v_fid` | 64 | 34,911 | 63 | 16 | 71/72 |
| STRICT_CONCENTRATED | `v_gap` | 25 | 8,045 | 49 | 16 | 1 |
| STRICT_BALANCED | `v_gap` | 25 | 7,457 | 49 | 16 | 1 |
| RELAXED_NO_CROSS | `v_fid` | 64 | 34,911 | 63 | 16 | 71/72 |
| RELAXED_ONE_CROSS | `v_fid` | 64 | 34,911 | 63 | 16 | 71/72 |
| RELAXED_NO_CROSS | `v_gap` | 25 | 6,561 | 49 | 16 | 1 |
| RELAXED_ONE_CROSS | `v_gap` | 25 | 7,457 | 49 | 16 | 1 |

严格配对的 `v_fid` 有10,304个联盟不同，`v_gap` 有2,268个联盟不同。两个价值下16名玩家的 Shapley 全部变化，排序后的多重集也不同；最大单玩家绝对变化分别约0.06809与0.05264。

放宽配对的对应数字为29,280和6,047，最大 Shapley 变化约0.09205与0.09182。但该比较同时包含 PB 企业数目标/尺度变化，只能作为结构变化对照。

## 3. 哪些统计坐标使用了来源差异

严格配对改变 S3 的 E 依赖。来源差异进入15个坐标：NAT、PA、A2 各自的 enterprise count、site count、workers、mfg workers 和 mfg share。满联盟数值仍完全相同，但联盟内激活条件不同。PB数值来源未修改；跨省 E1 使 PA 变化与 PB 来源发生玩家级耦合，因此 gap 也改变。

放宽配对的来源差异进入19个坐标：NAT、PB、B1 的五类指标，加上 B2 的 enterprise/site/workers/share。完整报表只有 PB enterprise count 改变，其余18个坐标体现的是“满联盟结果相同但来源证明不同”。

证据：`new_source_object_differences.csv` 与 `new_source_coordinate_differences.csv`。

## 4. Harsanyi、DNF 与图指标的解释

虽然联盟游戏和 Shapley 明确改变，四个实例的 `v_fid` Harsanyi 项都为63，`v_gap` 都为49；raw/unique DNF、primal 边、连通分量和 width 上界也完全相同。这说明：

1. 项数相同不代表项的玩家集合和系数相同；
2. 来源非同构不保证任一粗粒度规模计数变化；
3. 当前夹具的每个 witness 都是三变量合取，超图按企业形成4个低宽分量，成熟因式分解很可能直接利用；
4. Harsanyi 项数不应被当作通用计算难度代理。

本轮没有调用真值表 ADD 节点数，也没有把 Möbius 构造时间当性能结果。现有官方 LExaShap 适配只覆盖预先分解的 Boolean 分量；冻结新 G 尚无经验证的直接 provenance 编译器，因此电路节点记为未测，而不是0。

## 5. 成熟方法可能已解决的部分

- F0 的6个见证可按企业分成4个连通分量，min-fill width上界为2；常规模型计数、VE、d-DNNF/OBDD 在合适顺序下应能利用该低宽结构。
- 主保真度可按35坐标线性分解；ratio/gap 可在有限统计状态上精确处理。
- 完全相同的 Boolean 分量可由历史 LExaShap 缓存复用。

尚未验证的是：一个直接从 SQL provenance 构造的多输出编译器，是否会对 `[3,1,1,1]` 与 `[2,2,1,1]` 的度数集中产生不同 DAG 节点或中间 frontier。这个问题不能用本轮真值表/Harsanyi 结果替代。

原始证据：`new_source_metrics.csv`、`new_value_metrics.csv`、`new_pair_comparisons.csv`、`new_shapley_pair_differences.csv`。
