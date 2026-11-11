# v4.0 现有方法覆盖与复现状态表

状态：`DESIGNED / NOT_RUN`。适用性和复现进度是两个独立字段；仓库存在不等于已经复现。

| 方法 | D1-P 对象 | theory_status | code_status | same_game_status | v4.0 必做动作 |
|---|---|---|---|---|---|
| 精确子集 Shapley | 冻结联盟价值表 | `DIRECT` | `NOT_STARTED` | `NOT_TESTED` | S1 的 4096 联盟真值与独立核验 |
| 标准排列蒙特卡洛 | 同一 R-game | `DIRECT` | `NOT_STARTED` | `NOT_TESTED` | 后续小规模对精确真值 |
| Abramovich LExaShap/LExaBan | 单聚合、来源表达、可组合坐标 | `UNVERIFIED` | `NOT_STARTED` | `NOT_TESTED` | R0 官方复现；R1 的 AB-1–AB-6 |
| Luo 独立效用算法 | 可加输出效用及 owner/记录投影 | `UNVERIFIED` | `NOT_STARTED` | `NOT_TESTED` | R0 官方复现；R1 的 LU-1–LU-4 |
| Livshits 等 | 单个 COUNT/SUM 数值查询 | `THEORY_ONLY` | `NOT_STARTED` | `NOT_TESTED` | 适用最小查询上自建并核验 |
| Standke–Kimelfeld | 无自连接聚合合取查询 | `THEORY_ONLY` | `NOT_STARTED` | `NOT_TESTED` | 逐查询定理覆盖，适用特例再实现 |
| Besner | 玩家层次值 | `THEORY_ONLY` | `NOT_APPLICABLE` | `VALUE_MISMATCH` | 不作为标准 Shapley 性能基线 |
| Jiang 等 | Ensemble Shapley | `ASSUMPTION_NOT_MET` | `NOT_APPLICABLE` | `VALUE_MISMATCH` | 只作异目标参考 |

## Abramovich 仓库已核验信息

- 官方仓库公开，README 自称论文官方仓库；
- 要求 Python 3.11 或更高版本；
- 包含 LExaBan、LExaShap、MAX 版本及 ExaBan/ExaShap/AdaBan；
- SUM/COUNT 接收 DNF 与系数列表，MAX/MIN 接收合取集合与系数；
- README 指向 ProvSQL 获取来源表达，并提供示例 notebook。

这些只支持把算法列为强制复现对象。当前没有本地环境、提交哈希、运行日志或结果，因此复现状态仍为 `NOT_STARTED`。

## Luo 仓库已核验信息

- 官方仓库公开并对应 PVLDB 2022 论文；
- README 给出 Ubuntu 20.04、Rust 和 `cargo build --release`；
- 提供数据分配脚本和 owner Shapley 命令入口；
- 源码目录、Cargo.lock、配置和数据链接均公开可见。

当前仍未下载官方数据、构建 Rust 程序或复现论文结果，状态为 `NOT_STARTED`。

## 每种方法必须补全的字段

1. 查询关系原子、聚合、自连接、内生/外生位置和局部价值；
2. 原文定理、公式和定位；
3. 官方代码 URL、提交哈希、许可证和输入格式；
4. 原目标复现的输入、命令、输出、环境与比较依据；
5. D1-P 适配器和目标保持证明；
6. 实际运行状态、失败代码、耗时、峰值内存和中间结构大小；
7. 最终适用性状态及具体理由。
