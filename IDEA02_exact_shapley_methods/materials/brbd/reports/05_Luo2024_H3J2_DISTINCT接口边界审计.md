# Luo（2024）H3-J2 DISTINCT 接口边界审计

## 1. 最小控制游戏

本轮使用两个不同的 JOIN grounding：

\[
g_1=p_1\land p_5\land p_9,
\qquad
g_2=p_2\land p_5\land p_{10}.
\]

两个 grounding 的业务 `key` 都是 `K1`，但连接路径不同。关系数据为：

- `R(X1,p1)`、`R(X2,p2)`；
- `S(X1,Y1,K1,p5)`、`S(X2,Y2,K1,p5)`；
- `T(Y1,p9)`、`T(Y2,p10)`。

实际 DuckDB SQL 得到：

- `COUNT(*) = 2`；
- `COUNT(DISTINCT key) = 1`。

结果保存在 `runs/R2_h3_j2_distinct/sql_truth.json`，SQL 保存在 `runs/R2_h3_j2_distinct/distinct.sql`。

## 2. 两个目标的精确 Shapley

### COUNT(*) bag 游戏

\[
v_{bag}(S)=1[g_1\text{ 被满足}]+1[g_2\text{ 被满足}].
\]

Luo 官方 RDSV 在合成 TPC-H 连接链上生成 2 个简单游戏，输出：

| 玩家 | COUNT(*) 支付 |
|---|---:|
| p1 | 0.3333333333 |
| p2 | 0.3333333333 |
| p5 | 0.6666666667 |
| p9 | 0.3333333333 |
| p10 | 0.3333333333 |
| 合计 | 2 |

### COUNT(DISTINCT key) Boolean OR 游戏

\[
v_{distinct}(S)=1[g_1\text{ 被满足}\lor g_2\text{ 被满足}].
\]

独立枚举 32 个联盟得到：

| 玩家 | COUNT(DISTINCT key) 支付 |
|---|---:|
| p1 | 0.1333333333 |
| p2 | 0.1333333333 |
| p5 | 0.4666666667 |
| p9 | 0.1333333333 |
| p10 | 0.1333333333 |
| 合计 | 1 |

逐玩家差异均为 0.2。官方 RDSV 的 bag 输出不能直接当成 distinct 输出。

## 3. 结论

这不是 Luo 数学公式错误，而是官方输入前端的语义边界：

- 对 bag `COUNT(*)`，每个 grounding 是独立简单游戏，Luo RDSV 可直接运行；
- 对 `COUNT(DISTINCT key)`，同一 key 的多个 grounding 必须先按 Boolean OR 合并；
- 当前 Luo TPC-H 前端按 joined tuple 生成游戏，没有把多个 joined tuple 按业务 key 合并为一个 DNF 游戏。

因此本轮结论是：

> `COUNT DISTINCT` 在数学上可以表示为 Boolean DNF 游戏，但 Luo 官方发布接口不能直接表达本控制游戏的 OR 合并。将官方 bag 输出直接用于 distinct 会产生确定性的目标错误，而不是随机误差或数值误差。

## 4. 研究边界

本轮没有修改 Luo 官方源码，也没有把自写 OR 归约器称为作者实现。官方二进制只运行了 Q1 bag 目标；Q2 distinct 使用独立 SQL 和完整联盟真值核验。

证据文件：

- `scripts/build_h3_j2_distinct_r2.py`
- `runs/R2_h3_j2_distinct/distinct.sql`
- `runs/R2_h3_j2_distinct/sql_truth.json`
- `runs/R2_h3_j2_distinct/source_expression.json`
- `runs/R2_h3_j2_distinct/q1_vs_q2_shapley.csv`
- `runs/R2_h3_j2_distinct/raw_metrics/q1_bag_r2.json`
- `runs/R2_h3_j2_distinct/raw_logs/q1_bag_r2.log`

## 5. 对下一步的含义

下一步可以有两个严格区分的方向：

1. **适配器方向**：把同一业务 key 的多个 grounding 编译为一个 DNF 输入，再调用 Luo 的递归分解后端；这需要单独证明输入转换保持联盟价值等价。
2. **报表方向**：在 distinct OR 已正确表示后，再测试多个节点、多个指标和 V1/V2 的联合价值；不能把本轮 Q1 结果外推到完整报表。
