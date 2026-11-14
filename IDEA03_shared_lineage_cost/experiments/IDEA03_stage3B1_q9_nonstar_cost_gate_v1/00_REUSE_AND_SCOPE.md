# 00 历史复用与研究边界

## Material Passport

- Artifact type: experiment gate report
- Evidence status: protocol frozen before Stage 3B-1 execution
- Source stage: `IDEA03_stage3A_q9_nonstar_gate_v1`
- Scope: TPC-H Q9 Boolean positive-DNF source representation only

## 继承对象

本轮严格复用Stage 3A已经冻结的：

- P1：PART、SUPPLIER、PARTSUPP、LINEITEM、ORDERS为玩家；NATION外生；
- P2：PARTSUPP、LINEITEM、ORDERS为玩家；PART、SUPPLIER、NATION外生；
- `results/q9_l_witnesses.csv` 和 `results/q9_h_witnesses.csv` 的既有顺序；
- Q9-L/Q9-H真实物理键，不重新选择、搜索或修改。

每个L/H序列只取前4、8、12条，形成12个固定对象。价值对象固定为“至少一个完整witness被支持”的正DNF Boolean游戏。

## 方法路径

1. 官方LExaShap `DNFCircuit`：直接接收正DNF，不使用联盟真值表；每个对象运行前清除作者Value缓存。
2. Stage 2B-0参考VE诊断器：直接接收witness因子，状态为 `REFERENCE_DIAGNOSTIC_IMPLEMENTATION`，不称为新算法。
3. 本地ordered compiler门：`dd/pyeda/pysdd`及d4/c2d/sdd/bdd/sharpSAT/minisat/kissat均未发现，状态为 `NO_ELIGIBLE_ORDERED_COMPILER_LOCAL`。

## 禁止边界

不修改P1/P2、Q9、真实键、Q9-L/Q9-H或G；不枚举玩家联盟；不做完整报表、多输出共享、性能排名、SF1、JOB/IMDB、TPC-DS或Git操作。
