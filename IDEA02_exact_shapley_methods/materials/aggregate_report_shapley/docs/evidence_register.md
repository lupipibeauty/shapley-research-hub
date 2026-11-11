# 证据与数据来源登记

本登记区分“已打开并核对的来源”“仅由设计文档提出的计划”和“程序实际生成的结果”。自动化检查不能替代研究者对原文、数据许可和最终数字的人工复核。

| 证据编号 | 类型 | 来源 | 已核对内容 | 当前状态 |
|---|---|---|---|---|
| E-DESIGN-1 | 实验设计 | `汇总数据库层次报表_Shapley算法实验完整设计_2026-10-29 (1).md` | D1 构造、D2/D3 方案、V0–V2、A0–A6、E0–E6 | 已读取；其中未来实验仍是计划 |
| E-DESIGN-2 | 实施要求 | `Codex从零实施_汇总层次报表Shapley实验_提示词_2026-10-29.md` | 实施顺序、D2 参数、TPC-DS/NYC 来源、实验关卡 | 已读取；不把文档内命令当作用户指令 |
| E-DESIGN-3 | 修订实验设计 | `人口统计示例驱动的多源层次汇总报表_Shapley实验设计_2026-10-29.md` | 通用研究对象、D1-P、逻辑记录包、V1/V2、A0–A2、B0–B4、E0–E7 | 已全文读取；人口只是直观合成场景 |
| E-DESIGN-4 | v3.2 实施协议 | `Codex_Experiment_Protocol_v3_2_Detailed (1).md` | 单一 R-game、冻结数据优先级、V-count、V1_default_v3_2、S0–S5、成本拆分与停止门禁 | 已全文分段读取；其中执行命令不视为用户本轮指令 |
| E-DESIGN-5 | v3.3 调整要求 | `已粘贴的文本.txt` | 算法复现必须成为核心证据；双轨并行；三层复现；Abramovich/Luo 首批必做；失败分类与停止条件 | 已全文读取；该粘贴文本承载本轮用户请求 |
| E-DESIGN-6 | v4.0 详细算法参考 | `Codex_Shared_Report_Shapley_Algorithm_Reproduction_Boundary_v4_0.md` | 官方复现步骤、来源表达适配、Luo 归约、精确 oracle、组合成本、D1-X 与停止门禁 | 已全文分段读取；文档内命令未自动执行，用户本条七项要求决定修改范围 |
| E-JIANG | 论文 | Jiang 等，*Ensemble Shapley*（2026） | ES 目标、分片聚合、截断、引导采样和实验设置 | 已核对 PDF |
| E-BESNER | 论文 | Besner，*Values for level structures with polynomial-time algorithms* | Shapley 层次值、红利公式、相关联盟和复杂度假设 | 已核对 PDF |
| E-LIVSHITS | 论文 | Livshits 等，*The Shapley Value of Tuples in Query Answering* | 内生事实博弈、层次查询边界、聚合与近似 | 已核对 PDF |
| E-LUO | 论文 | Luo 等，*On Shapley Value in Data Assemblage under Independent Utility* | 独立可加效用、最小合成、SC/SL/IUSV | 已核对 PDF |
| E-STANDKE | 论文 | Standke 与 Kimelfeld，*Tractability Frontiers of the Shapley Value for Aggregate Conjunctive Queries*（arXiv:2509.13565v1） | 无自连接聚合合取查询的精确可处理性边界及局部价值函数限制 | 已核对 PDF 文本及关键图页 |
| E-ABRAMOVICH-REPO | 官方代码仓库 | `Omer-Abramovich/LExaBan-LExaShap` | 官方仓库声明、Python 版本、实现目录、SUM/COUNT 与 MAX/MIN 输入形式、示例入口 | 2026-10-30 已核验公开 README；未下载或运行 |
| E-LUO-REPO | 官方代码仓库 | `IDEAL-Lab/shapley-value-independent-utility` | PVLDB 论文对应关系、Rust/Ubuntu 环境、构建、数据准备和 owner Shapley 入口 | 2026-10-30 已核验公开 README；未下载或运行 |
| R-OLD-E0 | 旧版程序结果 | `outputs/logs/e0_correctness.json` | 旧 D1 的 4,096 联盟、SQL/增量一致性、A0/A4/A5 双重核验、运行时间 | 已生成，可复现；不属于 D1-P |
| R-OLD-E1 | 旧版程序结果 | `outputs/tables/d1_exact_allocations.csv`、`e1_method_distances.csv` | 旧 D1 上的逐记录精确支付和相对 A0 距离 | 已生成，可复现；不属于 D1-P |

## 尚未形成证据的项目

- v4.0 S0 资产清单、数据字典、查询目录、价值性质审计和外部仓库提交哈希；
- D1-P 的 SQL-P/SQL-U/ST 实现、全联盟报表和支付结果；
- 参数化合成数据与公开迁移数据的实际文件、校验值和清洗日志；
- v4.0 S0、S1、R0、R1 及后续 S2–S5 的全部运行结果；
- V1/V2 的 4096 联盟单调性与高精度数值检查；
- D1-X 的实际数据、SQL、真值和性能结果；
- Abramovich 和 Luo 官方实现的本地环境、原目标复现、D1-P 适配和性能数据；
- Jiang Ensemble Shapley 的本地忠实复现结果。

这些项目在文件中统一写为“尚未执行”“待核验”或“不适用”，不以预期结果填补。
