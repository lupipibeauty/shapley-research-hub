# RUN REGISTRY

| 日期 | 类型 | 对象 | 状态 | 说明 |
|---|---|---|---|---|
| 2026-11-18 | 继承 | `IDEA03_story_literature_deepread_v1` | COMPLETE_READ_ONLY | 保留十张卡和R1–R5，不改旧档 |
| 2026-11-18 | DeepSeek Flash ping | 本地现有接口 | ENV_BLOCKED | APIConnectionError / WinError 10061；未发论文请求、未消耗论文分析 token |
| 2026-11-18 | DeepSeek Flash ping（复测） | 同一接口，当前进程清除阻断代理 | VERIFIED | `deepseek-flash` 成功；29 tokens |
| 2026-11-18 | Flash 全文 scan | LIT-012、013、023、024 | SCAN_AND_DEEP_COMPLETE_DRAFT（仅scan） | 77页、30切片、115,743 tokens；29 DRAFT + 1 RAW；未调用Pro |
| 2026-11-18 | Flash 自动审计 | 四篇 scan | PARTIAL | 三篇完成文本覆盖审计但逐字引文不足；LIT-023 因一个结构异常块触发审计器类型错误 |
| 2026-11-18 | 原文精读 | LIT-023 Comparisons of Signals | FULLTEXT_THEOREM_VERIFIED | 作者PDF 33页 |
| 2026-11-18 | 原文精读 | LIT-012 Marginal Contribution Nets | FULLTEXT_THEOREM_VERIFIED | 官方/作者PDF 10页 |
| 2026-11-18 | 原文精读 | LIT-013 Bounded Dependency | FULLTEXT_THEOREM_VERIFIED | AAAI会议版8页；长版待核 |
| 2026-11-18 | 原文精读 | LIT-024 Markets for Information | FULLTEXT_MODEL_VERIFIED | 作者PDF 23页，综述 |
| 2026-11-18 | 原文访问 | LIT-011 Owen 1977 | FULLTEXT_UNAVAILABLE | Springer元数据/摘要；正文订阅受限 |
| 2026-11-18 | 官方任务核验 | CBB/BDS、HPSA、CDRZ、Opportunity Zones | FIRST_PASS | 仅规则与数据入口，不是业务成交证据 |
| 2026-11-18 | Shapley实验/算法/Git | 全部 | NOT_RUN | 按用户约束停止在理论与原文阶段 |

