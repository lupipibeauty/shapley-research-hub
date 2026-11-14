# 03 实验A：成熟方法直接编译来源

## Material Passport

- 规范运行：`STAGE2A_20261113_CANONICAL`。
- 状态：`VERIFIED_EXACT_ADAPTATION`。
- 编译器：官方 LExaShap `DNFCircuit` 的 lifting、d-tree 与 `Value` 梯度。
- 输入：六个冻结 JOIN 见证及其正 DNF 分量。

## 1. 固定变量顺序的接口审计

预注册了物理顺序 `0..15` 和确定性 min-fill 顺序；两实例的 min-fill width 均为2，具体顺序见 `variable_orders.csv`。但作者 `DNFCircuit` 通过 DNF lifting、独立OR/AND和启发式 exclusive-OR 展开，不接受外部变量顺序参数。因此两种顺序均记为 `INPUT_UNSUPPORTED_AUTHOR_INTERFACE`。

本轮没有通过修改集合迭代、变量重命名或自写 OBDD 来伪装“顺序实验”。实际作者路径固定 `PYTHONHASHSEED=0`，结果标记为 `AUTHOR_DTREE_HEURISTIC`。

## 2. 直接来源表示

作者 lifting 会把本例根节点压成一个复合 `Value`，所以 d-tree 外壳节点数均为1；有区分力的实际表示指标是内部 arithmetic DAG 节点。

| 实例 | 全局6见证 arithmetic DAG | 四个企业分量DAG合计 | 全局冷编译(s) | 全局Boolean求解(s) | 语义核验 |
|---|---:|---:|---:|---:|---|
| STRICT_CONCENTRATED | 26 | 24 | 0.00357 | 0.05082 | VERIFIED |
| STRICT_BALANCED | 28 | 26 | 0.00456 | 0.05754 | VERIFIED |

节点数是确定表示结果；时间是一次规范冷运行的描述值，不构成统计性能结论。进程峰值工作集在整次运行中约99–101 MB，属于累积进程指标；逐分量 Python heap 峰值另见原始 CSV，不能与进程RSS直接相加。

两实例 width=2、子句数6、变量数16完全相同，但 arithmetic DAG 相差2个节点。差异来自企业分量形状：集中实例为一个3见证/7变量分量加三个单见证分量；均衡实例为两个2见证/5变量分量加两个单见证分量。作者 lifting 对前一种集中结构复用了更多内部组合，因而集中实例反而略小。

这是一项单配对的结构观察，不是复杂度定理，也不能由毫秒级时间差宣称加速。

## 3. 同目标精确求解与多输出复用

| 实例/价值 | 原始分量 | 合并后唯一DNF | 唯一分量DAG节点合计 | 全运行顺序中的完整DNF命中/新编译 | 最大oracle误差 |
|---|---:|---:|---:|---:|---:|
| concentrated / `v_fid` | 143 | 65 | 620 | 0 / 65 | 8.33e-17 |
| concentrated / `v_gap` | 49 | 49 | 515 | 49 / 0 | 1.25e-16 |
| balanced / `v_fid` | 143 | 65 | 625 | 43 / 22 | 1.11e-16 |
| balanced / `v_gap` | 49 | 49 | 523 | 49 / 0 | 1.39e-16 |

解释：

- `v_fid` 内部把143个原始分量合并为65个唯一 DNF，证明完整相同分量缓存有效。
- concentrated 的49个 gap DNF 均已出现在其 `v_fid` 分量库中，因此无需新编译；这是完整键缓存，不是部分子图共享。
- balanced 与 concentrated 玩家ID一致且是严格配对，65个 `v_fid` DNF 中43个完全相同、22个新出现。
- 官方接口没有跨输出的部分公共子表达式DAG，也没有共同 numerator/denominator 数值状态；这两项分别记录为 `NOT_SUPPORTED_BY_AUTHOR_INTERFACE` 和 `NOT_IMPLEMENTED`。

## 4. 实验A自核

1. **是否绕过全联盟真值表？** 是。算法输入只含六个见证、冻结权重和64个见证状态。
2. **是否同一算法与配置？** 是。两实例均使用同一官方实现、相同适配器、`PYTHONHASHSEED=0`。
3. **编译结果是否不同？** 是，arithmetic DAG为26对28；企业分量合计24对26。
4. **差异是否来自变量顺序？** 当前不能判断；作者接口不消费预注册顺序。
5. **是否充分因式分解四个低宽分量？** 对单根 Boolean DNF，作者 lifting 已明显利用企业分量；对跨35输出部分子图共享，尚未实现。
6. **现有指标能否解释？** width相同不能解释2节点差异；企业见证度数分布与分量形状能解释方向，但只有一个配对，尚不能建立一般规律。

