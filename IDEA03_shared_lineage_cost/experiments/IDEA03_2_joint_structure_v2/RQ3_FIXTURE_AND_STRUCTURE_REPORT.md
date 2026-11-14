# RQ3 Fixture 与结构核验报告

## 1. 核验范围

本报告只记录实际生成和执行过的对象。有效运行是：

- E0：`runs/E0_20261113_033545/`，N=10、16。
- E1：`runs/E1_20261113_033650/`，N=20，seed 9201、9202、9203。
- E2 资源门：`runs/E2_20261113_120846/`，N=24，seed 9241。

`E0_20261113_031352`、`E1_20261113_033615` 和 `E2_20261113_034151` 是保留的失败/排除运行，不进入有效结果汇总。

## 2. 玩家与查询对象

每个 fixture 均保存 E、B、H、D、玩家映射和重连日志。E、B、H 的每条物理记录分别是独立玩家，D 固定；没有把企业、场所和就业事实合并成逻辑包。每条 B 使用唯一 sid，并与固定年度的一条 H 对应。

报表固定 NAT、PA、PB、A1、A2、B1、B2 七个节点和五项指标，共35个坐标。SQL 保留空骨架，零分母的 `mfg_share` 为 NULL。主实验使用完整 E JOIN B JOIN H 语义。

## 3. 配对生成结果

低/高共享只改变 B.eid。下列对象在配对中保持不变：玩家 ID、E/H 事实、sid、城市、行业、workers、城市场所数、企业度数和 JOIN witness 数。每个高共享 fixture 的具体交换保存在 `fixtures/<pair_id>/high/rewiring_log.csv`。

E1 三个 N=20 配对均得到：

- Low：`cross_province_eid_rate=0`，跨省企业数坐标的共同物理变量为0。
- High：`cross_province_eid_rate=1.0`，跨省企业数坐标共同包含4个物理变量，Jaccard 为0.2；每个 fixture 执行2次受约束重连。
- PA、PB 的满联盟去重企业数均由 Low 的2变为 High 的4。
- 全国和城市去重企业数、场所数、就业人数、制造业就业人数及比例的配对控制通过。

因此不能声称 Low/High 的完整报表值完全相同；省级 `COUNT DISTINCT eid` 的变化是已记录的结构后果。

## 4. 非退化检查

E1 三个 fixture 的 local/cross、Low/High 均通过机制适用门：两个输入都有多个可达值，乘积残差不恒定，联合状态不退化为单一指标。跨省来源重叠在 Low 为0、High 为4，符合反证设计。

N=10 的 Low/High local 对不满足“联合状态多于任一单指标状态”的条件。它只作为语义 smoke test，不进入机制判断；此性质记录为 `mechanism_eligible=False`，不再错误标记为程序正确性失败。

E2 使用精确见证子集表示检查报表状态。因每条 witness 有唯一 B/H，任意 witness 子集都可由其 E/B/H 并集实现，故枚举 `2^10=1024` 个 witness 子集可完整覆盖可达报表状态，而没有枚举 `2^24` 个玩家联盟。等价性已在 N=10 与全联盟状态集合对照通过。

## 5. 证据路径

- 生成器与评价器：`src/rq3_core.py`
- SQL：`sql/report_v1.sql`
- 单元测试：`tests/test_rq3_core.py`
- 原始 fixture：各有效运行的 `fixtures/`
- 结构指标：各有效运行的 `results/structure_metrics.csv`
- 配对控制：`results/pair_checks.csv`
- 非退化诊断：`results/nondegeneracy.csv`

