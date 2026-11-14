# 00 历史复用与工具准入

## 本阶段边界

本目录只执行 IDEA-03 阶段2B-0：在玩家、SQL 查询、35坐标报表和冻结价值任务不变的条件下，检验来源证明分布是否稳定改变有序精确表示规模。没有修改 `v_fid`、`v_gap` 或 SQL，没有扩大 N，没有重新枚举联盟，没有重新运行 Harsanyi、LExaShap exactness、TPC-H 或历史 E1。

## 复用证据

| 复用项 | 原始证据 | 本阶段用途 |
|---|---|---|
| 严格 concentrated/balanced N=16 配对 | `../IDEA03_2_cross_region_source_control_v1/` | 固定6个 JOIN witness、16名物理玩家和两个严格实例 |
| 官方 LExaShap 正 DNF 编译 | `../IDEA03_stage2A_mature_source_compilation_20261113/results/source_compilation_metrics.csv` | 复用26/28个 arithmetic DAG 节点的历史观察，不重跑 |
| 阶段2A变量序门槛 | `../IDEA03_stage2A_mature_source_compilation_20261113/results/variable_orders.csv` | 核实作者接口不接受外部变量序 |
| 35坐标与冻结 G | 阶段0、阶段1、阶段2A档案 | 只作为不变研究对象；本阶段不重新求值或求 Shapley |

相对本目录的 `../` 指向 `experiments/`。

## 本地工具门

在当前工程虚拟环境与本机可执行路径中，未发现同时满足下列条件的 OBDD/ROBDD、SDD/d-DNNF 或 VE 工具：直接接收来源因子/DNF、允许外部变量顺序、暴露表示规模、可做独立语义核验。检查范围包括 Python 包 `dd`、`pyeda`、`pysdd`、`sympy`、`networkx`、`pgmpy`、`pyAgrum`，以及 `d4`、`c2d`、`minisat`、`sharpSAT`、`kissat`、`sdd`、`bdd` 可执行程序；均未在本地环境中找到。本阶段没有联网、下载或安装依赖。

官方 LExaShap 是成熟作者实现，但其当前接口不消费外部变量序，不能完成本阶段三序对照。

## 降级实现及适用范围

依据任务授权，使用 `src/run_stage2b0.py` 中的教科书式 sum-product 变量消去适配器，状态明确标记为：

`REFERENCE_DIAGNOSTIC_IMPLEMENTATION`

它直接接收六个来源 witness 因子 `Y_s ↔ (E_e ∧ B_s ∧ H_s)` 和全局 `OR(Y_1,...,Y_6)` 因子，显式消费预注册顺序，报告 frontier、因子表规模、操作数、冷运行时间和 Python 跟踪内存。它不是新 Shapley 算法，不是作者实现，也不用于与作者实现做性能排名。节点数列明确记录为 `NOT_EXPOSED_REFERENCE_VE`。

独立语义校验使用六子句 DNF 的63项容斥计数，不读取16名玩家的65,536联盟真值表。

## 准入结论

工具门结论为 `REFERENCE_DIAGNOSTIC_ALLOWED`。它足以回答“结构效应是否在显式固定顺序后稳定存在”，但不足以把因子单元数直接等同于 OBDD/d-DNNF 节点数。
