# IDEA-03 文献局限性图谱 V1

## 本轮唯一任务

把已有精读文献中的局限、定理适用边界、实验未覆盖项和跨论文理论断层整理成可追溯材料，作为研究者产生 Idea 的刺激源，而不是由 Codex 自动宣布创新或关闭方向。

本轮不重新生成已有论文的全文精读，不运行 Shapley 实验，不调用 DeepSeek，不进行 Git 操作。

## 文件说明

- `01_CORPUS_SCOPE_AND_EVIDENCE_STATUS.md`：说明现有文献批次、重复关系和证据状态。
- `LITERATURE_LIMITATION_ATLAS.csv`：逐项记录文献边界及其证据等级。
- `CROSS_PAPER_THEORY_TENSIONS.md`：把局限组织为跨论文理论接缝，不进行创新等级判定。
- `RESEARCHER_IDEA_SEEDS.md`：供研究者先独立表达直觉，防止被 AI 候选方向锚定。
- `IDEA_PROVENANCE_LEDGER.md`：记录 Idea 来自用户、原文、跨论文推导还是实验现象。
- `RUN_REGISTRY.md`：记录本轮实际执行范围。

## 系统整理 V2（原文优先）

- `02_AUTHOR_EXPLICIT_LIMITATIONS.md`：只收录能够回到原文页码或章节定位的作者明确局限/未来工作。
- `03_ORIGINAL_SCOPE_BOUNDARY_MATRIX.csv`：逐篇分开记录原始问题、已解决对象、定理边界、实验边界和证据状态。
- `04_RESEARCH_MATURITY_DASHBOARD.md`：按价值、玩家、来源、精确计算、近似学习、动态维护六层展示研究成熟度。
- `05_CRITICAL_QUESTION_AND_DIVERGENCE_BANK.md`：从原文边界生成质疑问题，不预设答案。
- `06_IDEA03_MAPPING_AFTER_ORIGINAL_EVIDENCE.md`：最后一步才映射 R1--R12，避免项目视角污染原文整理。
- `07_AUTHOR_EXPLICIT_EXTRACTION_BATCH1.csv`：对31篇已有全文审计论文逐页回补作者自述局限的证据台账；含定位、版本与未找到记录。

`03_ORIGINAL_SCOPE_BOUNDARY_MATRIX.csv` 与 `04_RESEARCH_MATURITY_DASHBOARD.md` 是当前主入口。早先的 `LITERATURE_LIMITATION_ATLAS.csv` 仅保留为39项项目视角首版快照，不再作为全库覆盖统计。

## 局限证据等级

- `E0_SOURCE_GAP`：全文、版本或关键附件缺失；只能记录证据缺口，不能判断理论覆盖。
- `L0_EXPLICIT`：作者原文明示的局限或未来工作，必须有原文页码或章节。
- `L1_THEOREM_BOUNDARY`：由定义、输入、假设或定理条件直接得到的适用边界。
- `L2_EVALUATION_GAP`：论文的实验、代码或数据没有覆盖某对象。
- `L3_CROSS_PAPER_TENSION`：比较多篇文献后发现的对象、假设或目标断层。
- `L4_RESEARCH_HYPOTHESIS`：本项目提出、尚待证明的研究设想。

`L0--L2` 可以描述已有证据边界；`L3` 只能称为理论接缝；`L4` 不能写成领域空白或创新结论。`E0` 仅表示材料不足。

## 使用原则

1. 先让研究者从 `CROSS_PAPER_THEORY_TENSIONS.md` 选择有兴趣的矛盾。
2. 研究者先在 `RESEARCHER_IDEA_SEEDS.md` 写下直觉，Codex 暂不提供候选解法。
3. Codex 再把研究者种子形式化为数学对象、可反驳命题和最小验证。
4. 最后才回到最强竞争原文做覆盖审计。
5. 某篇论文研究了相似术语，不等于覆盖同一玩家、同一价值函数、同一信息集和同一分配目标。

## 推荐阅读顺序

1. 先读 `04_RESEARCH_MATURITY_DASHBOARD.md`，用六层地图快速判断各领域研究到哪里。
2. 再读 `02_AUTHOR_EXPLICIT_LIMITATIONS.md`，只看作者自己承认的局限和未来工作；需要逐篇页码时查 `07_AUTHOR_EXPLICIT_EXTRACTION_BATCH1.csv`。
3. 对感兴趣的论文查 `03_ORIGINAL_SCOPE_BOUNDARY_MATRIX.csv`，区分作者问题、已解决对象、定理边界和实验边界。
4. 在 `05_CRITICAL_QUESTION_AND_DIVERGENCE_BANK.md` 标出想反驳或继续追问的问题。
5. 最后才读 `06_IDEA03_MAPPING_AFTER_ORIGINAL_EVIDENCE.md`，判断这些问题如何与现有 R1--R12 相连。

## 本轮综合的限制

- 这是对本地既有精读库的证据综合，没有重新做外部数据库检索，因此不能声称文献检索完备。
- 本轮由单一 Codex 会话整理，没有第二名独立审阅者；矩阵适合研究导航，不替代研究者回到 PDF 的最终验收。
- mono、dual、预印本、工作论文、扩展摘要和无全文条目均保留不同证据状态，没有统一升级为“全文已人工核验”。

