# 历史实验索引说明

本目录中的 `experiment_index_round1.csv` 是第一轮从 62 项历史记录整理的索引快照，原字段与归一化标签予以保留。

**注意**：第二轮已对部分第一轮判断作出修正。查询下面的研究记录时必须以 `research/ROUND2_FACTS.md` 和 `evidence/round2/` 的原始报告为准：
- GNN 玩家映射不是不存在，而是嵌入在 JSONL 内；仍需单独导出与 DB 版本证据。
- GNN 消息方向已经确认，只有正向边。
- P3 的 R1/R2/C2 不是一个连续参数版本；各自具有不同的任务目标。
- M3 属于未执行的方案；P3 MTBDD 不可代用。
- LExaShap 91 项未完成已有原因分类，但未完成全面修复验证。

不允许静默改写原始行。未来迁移时可新增 `experiment_index_current.csv`，增加 `evidence_note`、`verified_in_round2` 等字段，并保留来源与修改日志。
