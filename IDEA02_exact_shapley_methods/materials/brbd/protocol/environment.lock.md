# BRBD_v1 环境锁定

- 锁定日期：2026-11-06（Asia/Shanghai）。
- 本机：Windows 10（内核版本 `10.0.26200`），AMD Ryzen 7 5800H，8 核 16 线程，13.87 GiB RAM。
- 本地作者算法环境：`aggregate_report_shapley/.venv`，Python 3.11.6；实际运行前以导入结果再次记录 NumPy/SciPy 版本。
- 固定执行：单进程、`PYTHONHASHSEED=0`；确定性性能实验重复 3 次，随机算法使用协议中的 5 个种子。
- 论文环境（原文物理页 19）：Linux Debian 14.04、1 TB RAM、Intel Xeon Gold 6252 @ 2.10 GHz。
- 论文失败判据（物理页 20–21）：单 lineage 实例超过 1 小时视为失败。
- 直接跨机器绝对耗时只作复现差异，不用于宣称论文结果错误；方法排名只在同机、同输入、同游戏下比较。
- 当前没有冻结可用的 ProvSQL 服务；因此预计算 lineage 的算法内核复现与 SQL→lineage 端到端复现分开报告。

证据类型：上述本机信息为 `AUTHOR_CODE_OBSERVED`/本地系统观测；论文环境为 `PAPER_REPORTED`。
