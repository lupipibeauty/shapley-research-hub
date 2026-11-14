# RQ3 实验协议 V2

## Material Passport

- `artifact_id`: IDEA03-2-RQ3-PROTOCOL-V2
- `artifact_type`: code experiment protocol
- `status`: FROZEN_FOR_E0_E1
- `date`: 2026-11-13
- `scope`: E0/E1 execution and conditional E2 feasibility

## 研究问题

在固定 E/B/H 物理玩家、完整 35 坐标报表和配对来源结构中，跨地区共同来源与坐标联合价值是否产生超过两因素单独作用的额外精确计算成本；该成本位于来源、转换、编译还是求解阶段。

## 设计

- 独立实验单位：由一个 seed 生成的一对 low/high fixture；计时重复不是独立实例。
- 主因子：跨省共享 low/high；价值 additive/joint。
- 分层重复：local 坐标对与 cross 坐标对分别计算 2×2 交互。
- 主交互：`Delta_T=(T_D-T_C)-(T_B-T_A)`；四格均有正、可测时间时才计算 `K_T=(T_D/T_C)/(T_B/T_A)` 与 `log(K_T)`。
- E0：N=10、16 全联盟 SQL/Python/精确 Shapley。
- E1：三组 N=20 配对实例，Python 全联盟真值与非枚举 H3 evidence-state 精确基线。
- E2：仅在 E1 同目标精确基线通过时尝试 N=24；资源上限触发后保存 `RESOURCE_LIMIT`，不自动扩大 cap。

## 冻结语义

玩家为 E、B、H 的每条物理事实；D 固定。报表采用 E-B-H 全 JOIN，固定年度、全国/两省/四市七节点以及企业、场所、就业、制造就业、制造就业占比五指标。SQL 对零就业比例保留 NULL，价值层不使用 NULL 参与乘积主例。

local 坐标对固定为 PA 企业数与 PA 制造业就业；cross 坐标对固定为 PA 企业数与 PB 企业数。主值函数为

\[
G_{add}=1000(f_1+f_2)/2,
\quad
G_{joint}=1000\{0.5(f_1+f_2)/2+0.5f_1f_2\}.
\]

主游戏使用 low/high 配对满联盟的逐坐标最大值作为共同参考尺度；各结构自身满联盟参考值另算补充支付结果。`lambda=0` 必须逐联盟退化为 additive。

## 正确性与停止门

1. fixture 玩家数、度数、城市/行业边际、就业值和 witness 数必须配对一致。
2. N=10、16 的 DuckDB 全联盟 35 坐标与独立 Python evaluator 必须一致。
3. exact subset Shapley 与 H3 evidence-state S6 的逐玩家最大误差不超过 `1e-9`。
4. 两个价值输入均有多个可达值；乘积残差非恒定；cross 高共享的目标 provenance overlap 必须大于 low。
5. 未通过者停止后续规模；状态 cap 触发记 `RESOURCE_LIMIT`，不解释为复杂度定理。

## 方法与边界

本轮实现 B0 向量化全联盟 oracle 与复用 H3/H5-R `StateGame + S6ReverseMultilinearAD` 的见证状态基线。P3 MTBDD、Abramovich/LExaShap、Luo、通用 d-DNNF 未完成本游戏适配，分别按证据记录为 `INPUT_UNSUPPORTED` 或 `ENV_BLOCKED`，不填模拟性能。

## 统计解释

E1 只有三个独立配对实例，只报告实例级交互、分布和中位数，不进行确认性显著性检验。重复计时仅描述运行噪声。E2/E3 未完成前，不作稳定总体效应结论。

## 工作流来源

实验设计遵循配对、独立重复与防止伪重复原则；分析明确区分效应估计与运行噪声。程序性工作流参考：Kassis et al. (2026), *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*, arXiv:2609.00065, DOI:10.48550/arXiv.2609.00065。

