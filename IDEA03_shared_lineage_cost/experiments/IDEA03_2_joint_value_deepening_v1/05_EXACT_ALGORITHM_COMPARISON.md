# 05 同目标精确算法比较

## 基线资格

|方法|输入|是否输出同一记录 Shapley|本轮资格|
|---|---|---|---|
|B0 full-coalition oracle|直接枚举 (v(S))|是|仅 N≤16 的正确性 oracle；不作为可扩展算法|
|Sparse Harsanyi from provenance|从阈值 DNF 分量做 inclusion–exclusion|是|`VERIFIED`；不读取 oracle 表|
|官方 LExaShap Boolean components|同一组加权 Boolean DNF|是|`VERIFIED`；官方源码 SHA `63855c...d68fe`|
|H3-S6|全局 evidence state|新 G 适配未完成|`INPUT_UNSUPPORTED`；历史状态结果仅作背景|
|本地 ROADD 诊断器|递归规约的实值决策图|本轮只编译、未从 ADD 直接求全部 Shapley|`REPRESENTATION_ONLY_NOT_SOLVER`，不得用于算法排名|

## 正确性与规模

共 5 个游戏 × 3 个 G。两个合格结构方法 30 个单元全部通过：

- `SPARSE_HARSANYI_FROM_PROVENANCE` 最大绝对误差 (2.78\times10^{-17})；
- `OFFICIAL_LEXASHAP_BOOLEAN_COMPONENTS` 最大绝对误差 (5.55\times10^{-17})；
- B0 以同一 Python evaluator 穷举到 N=16；结构方法不读取其联盟表。

表示规模：

|游戏|G0 Harsanyi|G1 Harsanyi|G2 Harsanyi|G2 最大次数|
|---|---:|---:|---:|---:|
|F0|6|4|8|10|
|F1 balanced|14|12|48|16|
|F1 concentrated|18|16|44|16|
|F2 balanced|18|12|72|14|
|F2 concentrated|24|16|56|14|

G2 的 Boolean 原始分量仍为 6，但 AND 门槛和共享证明使每个分量的 DNF 更宽，展开项增加。这是代数可分解与紧凑计算成本不同的直接证据。

## 计时解释

15 个单元的观测中位求解时间：B0 约 2.55 s、Sparse Harsanyi 约 0.00079 s、官方 LExaShap 约 0.0246 s、本地 ROADD 编译约 0.0745 s（后者不含 Shapley solve，不能排名）。这些数字只适用于当前最小 fixture，且 Python 计时未做独立进程冷启动和 RSS 重复测量，不能外推算法家族性能。

## 尚未完成

1. H3-S6 尚未适配 G0/G1/G2 的六维终端评分，不能标成失败或较慢。
2. 没有可核验的 d-DNNF/通用 VE 作者实现直接接收当前实值 G；这是实现缺口，不是理论空白。
3. ROADD 需要加入按联盟大小的加权模型计数/梯度，才能成为第三个合格全玩家求解器。

