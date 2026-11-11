# Luo（2024）H3-J2 DISTINCT 的 DNF 后端适配审计

## 1. 本轮目标

上一关证明了 Luo 官方 TPC-H tuple 前端会把两个共享业务 key 的 grounding 当作 `COUNT(*)`，不能直接得到 `COUNT(DISTINCT key)`。本轮进一步检查：在不修改作者官方 checkout 的前提下，是否可以把多个 grounding 合并成一个 Boolean DNF，再调用作者原始递归分解后端。

## 2. 本地 DNF 适配器

适配器位于：

`adapters/luo_dnf_adapter/official_fork/`

它只是作者 checkout 的独立本地 fork，新增一个输入入口 `cal_dnf_adapter`。核心计算直接调用作者源码中的：

```rust
alg::proposed::proposed_method
```

没有修改 `official_checkout`，也没有替换 Luo 的递归分解、IEC/IECE 或 Shapley 求解逻辑。

输入：

```json
{"clauses": [[0, 4, 8], [1, 4, 9]]}
```

表示：

\[
g_1=p_1\land p_5\land p_9,
\qquad
g_2=p_2\land p_5\land p_{10},
\qquad
q= g_1\lor g_2.
\]

## 3. 正确性结果

独立 32 联盟枚举得到 `COUNT(DISTINCT key)` 精确 Shapley：

| 玩家 | DNF 后端 | 精确值 | 绝对误差 |
|---|---:|---:|---:|
| p1 | 0.133333333333333 | 0.133333333333333 | (5.55\times10^{-17}) |
| p2 | 0.133333333333333 | 0.133333333333333 | (5.55\times10^{-17}) |
| p5 | 0.466666666666667 | 0.466666666666667 | (5.55\times10^{-17}) |
| p9 | 0.133333333333333 | 0.133333333333333 | (5.55\times10^{-17}) |
| p10 | 0.133333333333333 | 0.133333333333333 | (5.55\times10^{-17}) |
| 合计 | 1 | 1 | — |

效率性通过，最大误差仅为浮点舍入。

结果文件：

- `runs/R2_h3_j2_distinct/dnf_adapter_correctness.csv`
- `runs/R2_h3_j2_distinct/raw_metrics/dnf_adapter.json`
- `runs/R2_h3_j2_distinct/raw_logs/dnf_adapter.log`

## 4. 关键判断

本轮把上一关的“接口不支持”进一步拆成两层：

1. **官方数据库前端不支持**：作者 CLI 会按 joined tuple 生成独立游戏，不能自动按业务 key 合并 OR。
2. **作者递归分解后端可以处理**：只要外部前端正确构造同目标 DNF，作者原始 `proposed_method` 能精确计算 distinct 游戏。

因此，当前证据不支持“Luo 方法不能处理 COUNT DISTINCT”的说法。更准确的结论是：

> Luo 的数学后端能够处理该 Boolean DNF，但从真实 SQL grounding 到按业务 key 合并 DNF 的前端转换尚未由作者官方程序提供。

这属于“已有算法后端可复用、数据库语义前端需要适配”的结果，不是新算法创新。

## 5. 构建与版本

- 作者源码 commit：`2a514fb4a0e3d45365d6dffe6435f93499afd7e3`。
- Rust：1.75.0 GNU Windows toolchain。
- 本地构建命令：`cargo build --release --bin cal_dnf_adapter --locked --offline -j 1`。
- 构建耗时：约 1,241 秒；二进制 SHA-256：`27EAC70BCCCD77872A04F002CE4DAAE28B1835B34C8C90769B3AD3DF3468329C`。
- 运行耗时：约 0.936 秒（含进程启动和 JSON I/O）。
- 构建记录：`runs/R2_h3_j2_distinct/dnf_adapter_build.json`。

首次中文路径构建发生 Windows 工具链 `拒绝访问 (os error 5)`，随后在 ASCII 临时 fork 中成功。该环境问题与算法正确性分开登记。

## 6. 研究边界

本轮只验证了一个最小 `COUNT DISTINCT` OR-DNF 控制游戏，没有声称：

- 已完成 H3-JV 35 坐标的自动 SQL 前端；
- 已处理多 key、多层层次汇总；
- 已处理 V1 比例评分或 V2 联合价值；
- 已证明大规模编译成本可接受。

下一步最有价值的是把 `J2-DISTINCT` 扩展到 4 个 key 的 H3-JV 固定实例，测量 grounding→key-OR DNF 构造、DNF 去重、Luo 后端求解和端到端成本，并与 B0/B3 精确真值逐记录比较。
