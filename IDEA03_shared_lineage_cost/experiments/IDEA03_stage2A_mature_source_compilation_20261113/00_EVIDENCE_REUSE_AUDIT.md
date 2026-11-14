# 00 已完成证据与冻结输入复用审计

## Material Passport

- 阶段：IDEA-03 阶段2A。
- 状态：`VERIFIED_INPUT_REUSE`。
- 研究对象：两个严格配对 N=16 物理事实游戏。
- 禁止输入：全联盟价值真值表、Harsanyi 系数及由二者反推的电路。

## 1. 实际复用对象

| 对象 | 证据路径 | 本轮用途 |
|---|---|---|
| 阶段1协议与严格配对映射 | `../IDEA03_2_cross_region_source_control_v1/config/stage1_protocol.json` | 冻结研究对象，不重新生成随机夹具 |
| 玩家—物理事实映射 | `../IDEA03_2_cross_region_source_control_v1/results/new_player_mapping.csv` | 读取16名玩家的稳定编号 |
| 六个 JOIN 见证 | `../IDEA03_2_cross_region_source_control_v1/results/new_fixture_records.csv` | 直接构造正 DNF 来源 |
| 阶段1来源与价值结论 | `../IDEA03_2_cross_region_source_control_v1/03_SOURCE_AND_VALUE_COMPARISON.md` | 核对见证度数、重叠与 width=2 |
| 阶段2准入条件 | `../IDEA03_2_cross_region_source_control_v1/04_STAGE2_GATE_DECISION.md` | 限定为成熟直接来源编译门槛 |
| 冻结价值定义 | `../IDEA03_stage0_fidelity_freeze_20261113/config/frozen_value_function.json` | 固定 `v_fid`、`v_gap`、NULL及权重规则 |
| 精确 Shapley oracle | `../IDEA03_2_cross_region_source_control_v1/results/new_shapley.csv` | 仅在直接来源求解完成后比较 |
| 官方作者实现 | `../../../aggregate_report_shapley/external/abramovich/source/LExaBan-LExaShap-main/` | DNF→d-tree→Boolean Shapley |

所有输入与作者实现的 SHA-256 已写入 `results/run_manifest.json`。规范运行未读取阶段1的全联盟价值 CSV 作为算法输入，也未读取 Harsanyi 多项式。

## 2. 本轮只保留两个严格实例

玩家编号固定为 E 事实0–3、B事实4–9、H事实10–15。六个见证为：

| 场所 | STRICT_CONCENTRATED | STRICT_BALANCED |
|---|---|---|
| S1 | `{0,4,10}` | `{0,4,10}` |
| S2 | `{1,5,11}` | `{1,5,11}` |
| S3 | `{0,6,12}` | `{1,6,12}` |
| S4 | `{0,7,13}` | `{0,7,13}` |
| S5 | `{2,8,14}` | `{2,8,14}` |
| S6 | `{3,9,15}` | `{3,9,15}` |

因此两实例只差 S3 的企业事实依赖；企业见证度数分别为 `[3,1,1,1]` 与 `[2,2,1,1]`。`RELAXED_ONE_CROSS` 未作为第三个样本进入本轮。

## 3. 历史证据的使用边界

- 历史 ROADD 从全联盟真值表构造，本轮不把它当作直接来源编译器。
- 历史 LExaShap 只证明 Boolean 分量可解；本轮重新建立冻结 `v_fid/v_gap` 到正 DNF 分量的精确归约。
- 阶段1的65,536联盟值与 Shapley 只承担事后 oracle 角色。
- 阶段0/1、旧 E1、TPC-H 和 RESOURCE_LIMIT 运行均未重跑或覆盖。

首次启动因适配器遗漏作者类级 timeout 初始化而在首个电路构造前失败，已单独保存于 `logs/preflight_failure_20261113.md`；它不是算法失败或资源上限结果。

