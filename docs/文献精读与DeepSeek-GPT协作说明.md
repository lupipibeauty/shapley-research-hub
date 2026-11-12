# 文献精读与 DeepSeek—GPT 协作说明

## 1. 三个目录的职责

- `D:\python项目\shapley`：研究主工作区。Idea、实验设计、代码、结果和本地文献知识库都在这里持续发展。
- `D:\python项目\shapley-research-hub`：GitHub 档案镜像。保存研究历史、Idea 演变、实验脉络、可复现的小型代码和结果，使空白窗口可以先读仓库了解进展。
- `D:\python项目\shapley\tmp\researchlab_v2\Codex_Research_Lab_v2`：文献精读工具和协议工程。不要把 `.env`、API Key、虚拟环境和完整 Zotero 数据库提交到 GitHub。

## 2. 已有 Research Lab 入口

工具代码在：

```text
tmp/researchlab_v2/Codex_Research_Lab_v2/src/
├─ deepseek_research.py   # DeepSeek API：scan/deep/synthesize/audit
├─ research_cards.py      # 论文卡片初始化与检查
├─ knowledge_integrate.py # 将核验后的卡片整合进知识库
├─ research_kb.py         # 知识库查询/维护
└─ zotero_local_api.py    # 本地 Zotero 读取
```

提示词在 `tmp/researchlab_v2/Codex_Research_Lab_v2/prompts/`，协议和验收规则在 `.../docs/`。

单篇论文的实际输出位于：

```text
tmp/researchlab_v2/Codex_Research_Lab_v2/workspace/deepread/<paper_id>/<pdf_sha256>/
```

其中包含扫描结果、切片深读结果、阅读档案、失败状态和源文件元数据。不要用一个没有 PDF 哈希的摘要覆盖历史版本。

## 3. DeepSeek PDF 切片与深读流程

### 第一步：登记并固定原文

先确认 Zotero 条目、DOI、作者、年份、PDF 路径和 SHA-256。PDF 缺失、哈希变化或存在多个候选版本时先停下，标记 `PDF_MISSING` 或 `PDF_CHANGED`，不要自动猜版本。

### 第二步：结构化扫描（DeepSeek Flash）

在 Research Lab v2 目录执行：

```powershell
.\.venv\Scripts\python.exe src\deepseek_research.py read --paper <paper_id> --stage scan --allow-external-api
```

`scan` 的作用是把 PDF 按章节、页码、公式、图表和实验位置拆解，生成后续切片任务。扫描输出只能作为草稿，不能代替原文核验。

### 第三步：分片深读（DeepSeek V4 Pro）

扫描完成后执行：

```powershell
.\.venv\Scripts\python.exe src\deepseek_research.py read --paper <paper_id> --stage deep --allow-external-api
```

深读提示词要求每个关键断言绑定 `paper_id / pdf_page / section / evidence_id`，分别记录研究问题、数据、玩家/变量定义、模型公式、定理、算法、图表、实验条件、限制和未来工作。图表没有逐图打开核验时必须标记 `VISUAL_PENDING`。

### 第四步：DeepSeek 独立整合与审阅

```powershell
.\.venv\Scripts\python.exe src\deepseek_research.py synthesize --paper <paper_id> --allow-external-api
.\.venv\Scripts\python.exe src\deepseek_research.py audit --paper <paper_id>
```

`synthesize` 只整合已有切片，不补写原文没有的结论；`audit` 检查页码、证据 ID、章节定位和缺失项。DeepSeek 的输出始终是待审草稿，不等于人工确认。

## 4. GPT/Codex 的整合方式

GPT/Codex 不直接把 DeepSeek 摘要当作事实，而是按以下顺序工作：

1. 读取 `workspace/deepread/<paper_id>/<pdf_hash>/` 的扫描、深读、失败记录和原文元数据。
2. 回到本地 PDF，核对公式、定理、算法和图表的物理页码。
3. 用 `research_cards.py` 生成或检查论文卡片：

   ```powershell
   .\.venv\Scripts\python.exe src\research_cards.py init <paper_id>
   .\.venv\Scripts\python.exe src\research_cards.py check <paper_card.json>
   ```

4. 将通过证据门禁的结构化内容写入本地知识库或对应 Idea 的 `design/`、`evidence/`，保留 `VERIFIED`、`AGENT_AUDITED`、`HUMAN_REVIEW_REQUIRED`、`UNVERIFIED` 等状态。
5. 只有在完成来源核验后，才把文献结论用于研究问题、模型设计或实验假设；不能把文献观点、数学推断和本项目新假设混写。

## 5. 每次新窗口推荐提示词

### 扫描

```text
读取本地论文 <paper_id> 的完整 PDF 和元数据。先核对 PDF SHA-256 与页数，再调用 Research Lab v2 的 scan 阶段。输出章节地图、关键公式/定理/算法/实验/图表页码和缺失证据，不要写论文总结，不要补全原文没有的内容。
```

### 深度精读

```text
在 scan 已完成且 PDF 哈希未变化的前提下，调用 deep 阶段。逐节核对研究问题、数据与玩家定义、价值函数、模型公式、算法步骤、实验条件、限制和未来工作；每条关键断言绑定 evidence_id、PDF 页码和章节。无法核验的内容标记 UNVERIFIED 或 VISUAL_PENDING。
```

### GPT/Codex 整合

```text
读取该论文的 scan、deep、synthesize、audit 输出和本地 PDF。先区分原文事实、数学推断与本项目假设，再生成论文卡片和“与 IDEAxx 的关系”说明。保留证据 ID、页码、版本哈希和未决问题，不把 DeepSeek 草稿直接写成定论。
```

### 写入知识库前检查

```text
请检查这份论文卡片是否每个高影响结论都有 paper_id、pdf_page、section 和 evidence_id；检查公式、定理、算法、图表是否完成原文核验；列出缺口和 HUMAN_REVIEW_REQUIRED 项。未通过检查不要写入最终知识库。
```

## 6. API 与安全边界

DeepSeek 由 `src/deepseek_research.py` 单独调用；默认 `scan` 使用 `deepseek-flash`，`deep`/审阅使用 `deepseek-v4-pro`。API Key 只放在本地 `.env` 或环境变量中，不进入源代码、日志、研究档案或 GitHub。没有 API Key、PDF 缺失或哈希变化时，保留失败状态并停止对应步骤，不伪造 DeepSeek 输出。

## 7. 与 Idea 研究线的连接

文献精读的最终产物不是泛泛综述，而是可追溯的研究输入：

```text
PDF/DOI → DeepSeek scan → DeepSeek deep → audit → GPT/Codex 证据整合
      → 论文卡片/知识库 → IDEAxx/design → 实验代码与结果 → Git 档案镜像
```

文献卡片和精读原始输出留在本地研究工作区；GitHub 只保留适合长期阅读的协议、索引、研究判断和必要的小型证据摘要，避免上传私有 PDF、API Key、虚拟环境和大型缓存。
