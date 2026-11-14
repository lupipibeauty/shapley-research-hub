# 阶段1实验准入约束

本文件只规定准入，不启动阶段1。

## 1. 不得变化的对象

### 正确性入口

- 游戏 ID：`FID_F0_N12`，来源夹具 `E0_F0_K2_N12`。
- 玩家：E/B/H 每条物理行一名玩家；D、nodes 固定外生。
- SQL：`report_f0.sql` 的全 JOIN、eligible DISTINCT、全国/省/市展开语义。
- 统计坐标：固定35个；空组数值0、ratio 分母0为 NULL。
- G：`config/frozen_value_function.json`，主权重和两套敏感性均已冻结。
- 收入：`R=1000`，仅在 Shapley 后按 `v(N)` 归一化。

任何玩家绑定、JOIN 口径、NULL 规则、权重或尺度变化都必须创建新的 Q/G 版本，不能覆盖本阶段。

## 2. 正确性门

阶段1候选算法必须：

1. 在 `FID_F0_N12` 上逐玩家与 `results/shapley_allocations.csv` 的 exact fraction 一致，容差路径只用于浮点实现；
2. 对主保真度与 gap 分别报告，不得用一个 G 的正确性代替另一个；
3. 不读取4096联盟真值表、历史 Shapley 或本阶段支付作为输入；
4. 明确记录 SQL→lineage、value transform、compile、solve 四阶段；
5. 保存玩家映射、Q/G hash、命令、环境、原始错误和停止状态。

## 3. 结构研究的递进门

### IDEA-03-2B：来源结构与表示规模

先从 F0 的 disjoint enterprise witness 分量开始，再预注册改变 OR 证明交叠、来源图宽或共享物理事实的夹具。玩家数增长与结构宽度增长必须分开。H3-S6 在 N=24 的414,736状态发生在 G 应用前，只能作为“全局 evidence-state 表示不合适”的证据，不能当作游戏困难下界。

### IDEA-03-2C：多统计分量共享编译

比较“逐坐标/逐 Boolean 分量单独编译”与“一次来源编译、多终端/多分量复用”。必须冷启动与 warm cache 分开；只有完全相同 canonical DNF 才能记为缓存命中。F-IVM/LMFAO/多输出 FAQ 属于竞争思想，需补齐原文与实现证据。

### IDEA-03-2D：共享增加但表示缩小

不得复用 E1 省内集中/分散作为跨省共享结论。新对照必须分别控制：玩家数、每实体度数、witness 数、单对象替代证明数、跨坐标共同物理来源、primal/incidence width。集中可能减少城市状态或 DNF 条件，方向不能预设。

### IDEA-03-2F：同一 Q 服务不同 G

固定 SQL lineage，分别运行主 fidelity、gap 和保留的历史压力 G。共享的是来源构造/编译，不是事后复用 oracle。报告首个 G 的冷启动和后续 G 的增量 transform/solve 成本。

## 4. 阶段1可使用与禁止使用的基线

可进入适配队列：

- 官方 LExaShap Boolean 分量；
- sparse Harsanyi/Möbius，仅用于 N≤16 oracle 与表示诊断；
- P3 MTBDD 思路，在同一新 G 完成适配后；
- 直接 lineage→d-DNNF/OBDD/VE 的成熟实现（若能保存配置与证明同目标）；
- H5-R 的共享权重与前后缀机制，在新充分状态证明成立后。

禁止列为合格非枚举基线：

- 从完整真值表构造的 Reduced ADD；
- 不同玩家、Q 或 G 的历史运行时间；
- `ENV_BLOCKED` 作者实现；
- 只有摘要/类别引用而未核对条件的 LMFAO 等方法；
- 旧程序的 `RESOURCE_LIMIT` 记录本身。

## 5. 停止条件

出现以下任一情况即停止扩大实验并保存否定结果：

1. 候选实现不能在 N≤12 通过逐玩家 exactness；
2. 所谓共享优势只来自读取真值表、预热缓存或不对称预处理；
3. 结构操纵同时改变多个未记录参数，无法解释；
4. 成熟归约在同目标上已完全覆盖，且没有新的共享编译或参数化问题；
5. 运行触发资源上限，且尚未定位到 source/transform/compile/solve 的具体阶段。

## 6. 仍值得验证的困难

1. F1/F2 中 G2 的 Harsanyi 项由8增至44--72，是否可由共享 Boolean 子电路显著压缩。
2. 同一 SQL lineage 的35坐标及多个 G 能否只编译一次，而不是逐分量重复。
3. 共享来源增加时，OR 吸收或城市条件减少是否反而缩小表示；其充分条件是什么。
4. 图宽、证明交叠、对象度数与终端状态数之间哪个参数决定实际编译规模。
5. TPC-H supplier 跨地区共享在严格配对数据上是否仍产生这些结构效应。

这些是阶段1候选，不是阶段0已证明结论。
