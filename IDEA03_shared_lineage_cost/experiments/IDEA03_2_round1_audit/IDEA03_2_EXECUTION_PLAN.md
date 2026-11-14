# IDEA-03-2 分阶段执行计划

状态：`PLANNED_NOT_EXECUTED`  
日期：2026-11-13  
本文件中的命令均为未来入口契约，目前对应模块尚未创建，本轮没有执行任何命令。正式运行前需先由研究者批准 fixture、价值函数和资源上限。

## 1. 预期环境与复用清单

建议从历史主环境起步，但新建独立环境清单，不复用未冻结的全局环境：

- Python 3.11.x；
- DuckDB 1.5.6（先与历史结果保持一致）；
- NumPy/pandas/SciPy 仅在分析需要时加入并锁定；
- 进程 RSS 采样器与 Python `tracemalloc` 分开记录；
- Windows 本机为首轮平台，作者算法若要求 Linux/Rust/ProvSQL，单独记环境，不混入自有 Python 基线。

预计复用但不修改：

- S1：全联盟 SQL、独立状态和子集 Shapley 的三方校验结构；
- P3：物理玩家 manifest、fixture hash、SQL/Python oracle 与算法输入隔离；
- H3-JV/H3-CONTROL：JOIN grounding、见证就绪状态、结构指标、适用性矩阵；
- H5-R：Shapley 权重、缓存、S4/S5/S6 外壳、计时与失败记录；
- AB/P3-1C：作者算法的输入边界、source/compile/solve 成本拆分。

不直接复用：D1-P 玩家数据、P3 冻结 fixture、M3 报告数字、任何未归档外部作者源码。

## 2. 阶段 0：目录、环境与冻结协议

### 目标

建立独立目录和只含设计/配置的小型基线；记录环境，不运行联盟枚举。

### 未来命令

```powershell
cd D:\python项目\shapley-research-hub\IDEA03_shared_lineage_cost\experiments\IDEA03_2_joint_structure
py -3.11 -m idea03_2.env_audit --output runs\env_manifest.json
py -3.11 -m idea03_2.freeze_protocol --config configs\experiment_v1.yaml --check-only
```

### 产物与门

- `env_manifest.json`、依赖锁定说明、CPU/RAM/OS；
- schema、玩家、SQL、A/J 公式、权重、λ、停止条件的 hash；
- `--check-only` 不得生成实验结果。

未解决：hub 当前没有统一可复现锁文件；作者源码未完整迁入。若环境信息不全，只允许继续自有 Python/DuckDB smoke，不运行作者基线。

## 3. 阶段 1：E/B/H/D fixture 与玩家映射

### 目标

先生成 N=9/12 的基础实例，再通过度数保持重连生成 low/high 配对。D 固定外生。

### 未来命令

```powershell
py -3.11 -m idea03_2.build_fixture --config configs\fixture_n12_v1.yaml --seed 9301 --out fixtures\ebhd_v1\pair_9301
py -3.11 -m idea03_2.audit_fixture --fixture fixtures\ebhd_v1\pair_9301 --strict
py -3.11 -m idea03_2.hash_fixture --fixture fixtures\ebhd_v1\pair_9301 --out fixtures\ebhd_v1\pair_9301\manifest.json
```

### 检查

- E/B/H 每行恰好一个 player_id，D 无 player_id；
- low/high 玩家集合、行数、每个 eid 度数、每城市 B 数、行业边际、H 值完全一致；
- low 的跨省企业比例为 0；high 达到预设阈值；
- 保存每次 2-switch 和前后映射；
- 不生成与历史 P3/D1-P 同名的 fixture。

预计任务量：每个 pair 两个小 CSV/JSON fixture，体量 KB–MB。若无法在保持边际下构造 high，停止并修改生成约束，不进入 SQL。

## 4. 阶段 2：SQL 语义与 exact oracle

### 目标

在 N=9/12 上完成全部联盟的 DuckDB SQL、独立 Python lineage 和 exact Shapley 三方核验。

### 未来命令

```powershell
py -3.11 -m idea03_2.build_sql --fixture fixtures\ebhd_v1\pair_9301 --sql sql\report_v1.sql --check-only
py -3.11 -m idea03_2.enumerate_coalitions --fixture fixtures\ebhd_v1\pair_9301 --structure low --sql sql\report_v1.sql --out runs\oracle_n12_9301_low
py -3.11 -m idea03_2.enumerate_coalitions --fixture fixtures\ebhd_v1\pair_9301 --structure high --sql sql\report_v1.sql --out runs\oracle_n12_9301_high
py -3.11 -m idea03_2.validate_oracle --runs runs\oracle_n12_9301_low,runs\oracle_n12_9301_high --values configs\values_v1.yaml --tolerance 1e-10 --strict
```

### 预计任务量

- N=12：每种结构 4096 个联盟、固定报表坐标；A/J 从同一 `Y(S)` 派生，不重复执行 SQL。
- 一个 pair：8192 次结构-联盟查询输出，四格为 16384 个价值，但 SQL 只做两套结构。
- 建议批量 mask SQL/向量化 lineage，避免每联盟重建数据库。

### 正确性门

1. 所有联盟所有坐标 SQL=Python；
2. `v_A`、`v_J` 空联盟 0、满联盟 1000；
3. `λ=0` 时 J=A；
4. 子集公式与 N≤9 完整排列一致；
5. 效率、构造 dummy/symmetry 通过。

任一失败立即停止，不运行算法性能。

## 5. 阶段 3：现有方法适配审计

### 目标

只建立同游戏资格，不做规模竞赛。适配按“自有 exact 状态→P3/AB 作者路径→近似对照”顺序。

### 未来命令

```powershell
py -3.11 -m idea03_2.audit_method --method h3_evidence_state --fixture fixtures\ebhd_v1\pair_9301 --oracle runs\oracle_n12_9301_low --strict
py -3.11 -m idea03_2.audit_method --method h5r_shared_shell --fixture fixtures\ebhd_v1\pair_9301 --oracle runs\oracle_n12_9301_low --strict
py -3.11 -m idea03_2.audit_method --method lexashap --fixture fixtures\ebhd_v1\pair_9301 --value A --check-environment
py -3.11 -m idea03_2.audit_method --method luo --fixture fixtures\ebhd_v1\pair_9301 --value A --check-environment
py -3.11 -m idea03_2.audit_method --method p3_mtbdd --fixture fixtures\ebhd_v1\pair_9301 --check-interface
```

这些名称是计划接口，不表示已有模块。

### 方法状态规则

- `VERIFIED_SAME_GAME`：所有联盟值或严格归约证明一致，逐玩家 Shapley 对 oracle 通过；
- `INPUT_UNSUPPORTED`：作者输入或价值假设不覆盖；
- `ENV_BLOCKED`：依赖/作者源码/服务缺失；
- `RESOURCE_LIMIT`：输入正确但超过预设资源；
- `INCORRECT_OUTPUT`：同目标和环境均成立后仍不正确。

只有第一类进入性能表。H5-R 必须经 H3 JOIN evidence state 适配，不能直接把 E/B/H 记录编码为旧 `delta`。通用 d-DNNF 与 M3 变量排序保持 `MISSING`，本阶段不实现。

## 6. 阶段 4：N=12 四格 pilot

### 目标

运行 3 个独立 pair，验证分配指标、成本字段和交互计算是否可解释。

### 未来命令

```powershell
py -3.11 -m idea03_2.run_factorial --config configs\factorial_n12_v1.yaml --seeds 9301,9302,9303 --resume-safe
py -3.11 -m idea03_2.audit_factorial --run-root runs\factorial_n12_v1 --strict
py -3.11 -m idea03_2.summarize_factorial --run-root runs\factorial_n12_v1 --out runs\factorial_n12_v1\summary
```

### 预计任务量

- 3 pair × 2 结构 × 4096 SQL 报表 = 24576 个结构-联盟输出；
- 同一输出派生 A/J，因此四格价值 49152 个；
- B0 exact 每格一次；通过资格的方法同一 frozen instance 计时 3 次；
- 3 个 pair 是结构变异样本，3 次计时只是运行噪声样本，二者不得合并。

### 资源建议

- 单任务 15 分钟、8 GiB；
- 原始逐联盟数据优先压缩/分区，Git 只保存 config、manifest、summary、hash 和小型 correctness 表；
- 进程 RSS 与 `tracemalloc` 分列。

## 7. 阶段 5：N=16 主确认

### 前置条件

N=12 三个 pair 的 SQL/oracle 全部通过；至少 B0 与一个非枚举 exact 基线达到 `VERIFIED_SAME_GAME`，或明确记录只有 B0 可用；pilot 的配对指标没有边际混杂。

### 未来命令

```powershell
py -3.11 -m idea03_2.run_factorial --config configs\factorial_n16_v1.yaml --seeds 9401,9402,9403,9404,9405 --resume-safe
py -3.11 -m idea03_2.audit_factorial --run-root runs\factorial_n16_v1 --strict
py -3.11 -m idea03_2.summarize_factorial --run-root runs\factorial_n16_v1 --paired-analysis --out runs\factorial_n16_v1\summary
```

### 预计任务量

- 5 pair × 2 结构 × 65536 SQL 报表 = 655360 个结构-联盟输出；
- 由其派生 1,310,720 个四格价值；
- 对每个合格方法、四格、5 pair 做一次 correctness，固定首个 pair 做 3 次性能重复；若资源允许，再扩大性能实例数。

### 资源建议

- 单任务 60 分钟、16 GiB；
- 允许分 pair、分结构断点续跑，但每个分片记录 config/hash；
- 不把未完成单元静默排除，统一写入 `failure_records.csv`。

## 8. 阶段 6：扩展实验（需单独批准）

只有主确认显示稳定且未被成熟方法完全覆盖时，才按单因子扩展：

1. N=18 exact 边界；
2. 城市/省份坐标数 2/4/8；
3. sharing low/medium/high；
4. `λ=0,.25,.5,.75`；
5. 多年度 H。

未来命令契约：

```powershell
py -3.11 -m idea03_2.run_extension --config configs\extension_<factor>_v1.yaml --resume-safe
py -3.11 -m idea03_2.audit_extension --run-root runs\extension_<factor>_v1 --strict
```

每次只改变一个主因子；多年度不与 N、维度同时扩展。N≥20 不默认做完整联盟 oracle，且不得由状态数接近联盟数推导普遍复杂度结论。

## 9. 总资源估计

| 阶段 | SQL/联盟主量级 | CPU/RAM 预期 | 磁盘策略 | 退出条件 |
|---|---:|---|---|---|
| smoke N=9 | 每 pair 2×512 | 单核分钟级；<4 GiB | 全量可留小表 | 任一语义差异 |
| pilot N=12 | 24576 结构-联盟输出 | 分钟至小时；≤8 GiB | 原始压缩，Git 留摘要 | 15 分钟/任务或状态 cap |
| main N=16 | 655360 结构-联盟输出 | 小时级；≤16 GiB | 分片+hash，大表不进 Git | 60 分钟/任务、16 GiB |
| boundary N=18 | 每 pair 2×262144 | 需先测；可能小时级 | 仅批准后生成 | 资源上限或无新增信息 |
| N≥20 | 不预设全联盟 | 方法依赖 | 只留 manifest/摘要 | 无 exact 资格即不运行 |

这里是保守计划，不是实测承诺。历史 H3/H5 耗时只能用于安排顺序，不能外推本游戏性能。

## 10. 结果目录与最小交付

每个正式 run 至少包含：

```text
run_config.yaml
environment.json
fixture_manifest.json
sql_hashes.json
player_mapping.csv
structure_metrics.csv
correctness_summary.csv
method_applicability.csv
raw_timing.csv
performance_summary.csv
failure_records.csv
research_judgment.md
```

逐联盟原始输出若过大，存于 Git 外的受控数据目录，并在 manifest 中保存路径去标识化描述、大小和 SHA-256；不能只保留报告结论。

## 11. 尚待研究者确认

1. 首轮企业数/场所数是否必须依赖 H 的存在。本设计选择统一全 JOIN；若业务语义不同需另版 SQL。
2. `mfg_share` 的零分母政策和比例得分公式是否接受。
3. high-sharing 的目标阈值（建议至少 50% 多场所企业跨省）是否可由小 N fixture 达到。
4. G_J 的乘积结构与 `λ=0.5` 是否只作为受控函数使用；不得解释成已验证的商业价值。
5. 主确认是否接受 N=16、5 个配对实例以及 60 分钟/16 GiB 单任务上限。
6. 作者源码是否允许在后续阶段重新接入；在此之前 Abramovich/Luo/ProvSQL 的相应路径保持 `ENV_BLOCKED`。

## 12. 本轮停止点

本轮止于资产审计与 V1 设计。未创建上述实验目录，未生成 fixture，未运行 SQL、oracle 或算法，未提交或推送 Git。
