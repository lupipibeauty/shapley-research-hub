# Abramovich 原生 SQL 适配实验协议（AB-N1—AB-N5）

版本：2026-10-31  
本轮执行边界：只执行 AB-N1 必要最小验证；AB-N2—AB-N5 只完成设计，不启动大规模实验。

## 一、共同目标与冻结对象

- `[USER-INPUT]` 玩家固定为 D1-P 的12个逻辑记录包 `p1...p12`；物理来源分表、可选属性表和 `OwnerMap` 不改变玩家定义。
- `[USER-INPUT]` 联盟数据库只保留联盟内记录包；层级表、类别关系、SQL、满表参考值和评分参数固定。
- `[PAPER-EVIDENCE]` 官方方法的原生 Boolean 输入是 SQL 输出 tuple 的正 DNF lineage；每个 grounding 形成一个合取子句，每个内生数据库事实对应一个 Boolean 变量（论文第2.2节，第6页）。
- `[PAPER-EVIDENCE]` 对 SUM/COUNT，聚合 lineage 是 `Σ_i φ_i⊗m_i`，Shapley 可按 `Σ_i Shapley(φ_i,x)m_i` 线性合成（论文第4.1节，第15页）。
- `[USER-INPUT]` 精确正确性 oracle 是冻结 D1-P 的全部4096联盟价值与标准记录级 Shapley；oracle 只能在来源表达构造完成后用于验收。

## 二、SQL 到来源表达的统一构造

1. 对物理来源表执行 `UNION ALL`，核验 `record_id` 全局唯一。
2. 将 `Hierarchy`、类别关系和固定映射表视为外生关系，不创建玩家变量。
3. `BasicSource` 与同一 `record_id` 的 `OptionalAttribute` 绑定到同一变量 `p_i`；不能把物理行拆成两个玩家。
4. 对每个聚合输出 tuple 执行其 SPJ grounding 查询。每个 grounding 的内生变量集合成为一个 DNF 合取子句；多个 grounding 成为析取。
5. COUNT 的系数为1；SUM 的系数为对应输出 tuple 数值。零系数组件可删除，但要记录删除数。
6. 把 DNF 和系数直接交给官方 LExaShap；禁止读取联盟价值表或精确支付来反推系数。
7. 来源表达和官方支付完成后，才运行4096联盟 SQL oracle 做逐联盟等价和支付核验。

这是一条待逐步扩展的受限 lineage compiler 路径，不等同于完整 ProvSQL，也不宣称支持任意 SQL。

## 三、正确性关卡

| 关卡 | 验收内容 | 失败分类 |
|---|---|---|
| G0 冻结性 | 配置、SQL、官方源码哈希固定；历史结果只读 | 实现尚未完成/材料变化 |
| G1 玩家身份 | 每个 `record_id` 恰好绑定一个变量；外生关系无变量；LEFT JOIN 不删除基础记录 | 输入绑定错误 |
| G2 构造独立性 | 来源表达构造日志中没有4096联盟值、Harsanyi系数或支付答案 | 目标泄漏 |
| G3 联盟等价 | 对4096个联盟，原始SQL值与来源表达值逐个相同 | 数学表示困难或编译错误 |
| G4 支付一致 | 官方输出与精确记录 Shapley 最大误差≤`1e-10`，效率性残差≤`1e-10` | 算法/归一化/数值错误 |
| G5 成本口径 | 分开报告SQL grounding、来源编译、d-tree编译、反向求解、oracle时间；oracle不计入算法时间 | 计时口径错误 |
| G6 阶段推进 | 当前阶段全部通过后才进入下一阶段；失败后先分类，不用换目标绕过 | 研究边界错误 |

## 四、分阶段实验

### AB-N1：单层 COUNT/SUM

输入构造：选择叶节点 A1，运行单层聚合：

- `COUNT(*)`；
- `SUM(CASE WHEN category_a_id='E2' THEN 1 ELSE 0 END)`。

grounding 查询从四张冻结来源分表经 `UNION ALL` 和外生 `Hierarchy` JOIN 直接得到 `p1,p2`。预期来源表达为：

- COUNT：`p1⊗1 + p2⊗1`；
- 条件 SUM：`p2⊗1`。

本轮状态：`PASSED_MINIMAL_NATIVE_VALIDATION`。实际3个组件、3个子句、3个变量出现；联盟价值误差0，支付误差0。该步骤没有使用 OptionalAttribute，因此尚未覆盖记录包跨物理表绑定。

### AB-N2：多城市、多层级 COUNT/SUM

输入构造：每条记录通过 `Hierarchy` 展开到叶/中间/根三个节点；为 `(node,metric,output tuple)` 生成 lineage。对 record count、E2 count、attribute-present count 分别生成 COUNT/SUM BNP。

关键新增关卡：

- 同一玩家在三个层级重复出现，但仍是同一个变量；
- LEFT JOIN OptionalAttribute 后同一 `record_id` 的多个物理字段只绑定一个变量；
- 一个记录在不同输出坐标中的重复贡献通过外层线性求和处理，不复制玩家；
- 每个节点和完整加权和都通过4096联盟等价检查。

预计线性组件数：record count 36、E2 count 18、attribute-present count 30，共84个单记录贡献；实际数量以 grounding 输出为准。状态：`DESIGNED_NOT_RUN`。

### AB-N3：35坐标完整报表的可加评分

先把35坐标分为：

- 21个 COUNT/SUM 型坐标：7节点×3个计数指标；
- 14个比例型坐标：7节点×2个比例指标。

外层“固定权重相加”只有在每个坐标本身已有同目标来源表达时才能使用线性性。它不能把比例坐标自动变成 SUM/COUNT。因此本关分两步：

1. N3-L：对21个线性坐标及其固定加权和执行原生编译；
2. N3-F：要求14个比例坐标也保持原语义后，才允许把结果称为“35坐标完整报表”。

若 N3-L 通过而 N3-F 未通过，总状态只能是 `PARTIAL_COVERAGE`，不能把21坐标结果写成完整报表结果。状态：`DESIGNED_NOT_RUN`。

### AB-N4：V1 比例评分

冻结 V1 的比例坐标不是简单的“分子除以满表常数”。以类别A比例为例，当前联盟计数为 `(c,t)`、满表计数为 `(C,F)` 时：

\[
score(c,t)=\frac{t}{F}\left(1-\left|\frac ct-\frac CF\right|\right)
=\frac tF-\frac{|cF-tC|}{F^2}.
\]

它包含对两个 SUM/COUNT 结果的绝对值非线性变换。官方 LExaShap 的发布接口接受正 DNF 及线性 SUM/COUNT 系数，没有提供“聚合结果除法/绝对值”的 Shapley 接口；仓库中的 MAX 实现又是 LExaBan，不是 LExaShap。

因此 N4 首先做“来源语言可表示性”关卡：若不能从 SQL grounding 直接生成官方可处理表达，就登记为 `MATHEMATICAL_REPRESENTATION_LIMIT + SOURCE_INTERFACE_LIMIT`。不得退回先枚举4096联盟再做 Harsanyi 展开；历史4023/4095非零项只作为指数展开密度证据。状态：`DESIGNED_NOT_RUN`，高风险。

### AB-N5：V2 统计族交互评分

V2(λ=0.5) 把四个统计族得分的算术项与加权几何项组合。几何项是跨统计族的非线性交互，不满足论文对 SUM/COUNT 使用的线性分解。关卡顺序：

1. 先复用 N4 检查各族内部比例评分能否原生表示；
2. 再检查官方来源语言是否能表示跨族几何组合；
3. 只有两者都通过，才进入4096联盟和支付核验。

历史4094/4095非零 Harsanyi 项说明固定12玩家上可指数表达，但该表达被本协议明确禁止作为“原生适配”。状态：`DESIGNED_NOT_RUN`，最高风险。

## 五、成本与资源记录

每阶段必须输出：

- 输入关系行数、输出坐标数、grounding数；
- DNF组件数、子句数、变量出现次数、序列化字节数；
- SQL grounding时间、来源表达组装时间、d-tree编译时间、Shapley反向求解时间；
- 端到端时间和峰值内存；
- post-hoc 4096联盟 oracle 时间（单列，不能计入算法时间）。

资源风险：

- AB-N1/2 的表达规模预计随 grounding 数近似线性，风险低。
- AB-N3 的21个线性坐标仍较小；14个比例坐标的主要风险是表示能力而不是内存。
- AB-N4/5 若只能通过一致基展开，表达会接近4095项；这属于被禁止的指数预计算路径。
- 官方构造器把 d-tree 构建与 backward 连在一次调用中。本项目可用独立计时 harness 分开测量，但必须与未修改构造器结果逐值交叉核验。

## 六、失败登记格式

每个失败只能使用以下一个或多个标签，并附证据：

- `MATH_REPRESENTATION_LIMIT`：同目标函数不在论文/官方来源表达语义内；
- `SOURCE_INTERFACE_LIMIT`：数学上有表达，但发布代码没有相应输入或求解接口；
- `EXPRESSION_SCALE_LIMIT`：表达可构造但编译规模/时间/内存不可接受；
- `IMPLEMENTATION_INCOMPLETE`：协议允许且接口可用，但本轮编译器尚未实现；
- `CORRECTNESS_FAILURE`：联盟等价或支付核验不通过。

不得把上述任一失败直接称为新算法问题；需继续结合查询归约和相关文献判断。

