# 01 玩家语义冻结

状态：`FROZEN_BEFORE_PROVENANCE_METRICS`

冻结日期：2026-11-14（Asia/Shanghai）。本文件和 `config/stage3a_q9_protocol.json` 在正式来源统计之前建立；后续不得根据宽度、overlap或准入结果修改玩家集合。

## P1：完整物理事实玩家

玩家关系：`PART`、`SUPPLIER`、`PARTSUPP`、`LINEITEM`、`ORDERS`。外生固定：`NATION`。

每条witness为：

`{P_partkey, S_suppkey, PS_(partkey,suppkey), L_(orderkey,linenumber), O_orderkey}`。

业务依据：

- `PART` 是独立存储的产品主记录，提供Q9的产品名称过滤；记录缺失会使对应交易无法进入产品条件。
- `SUPPLIER` 是独立存储的供应商主记录，提供供应商—国家归属；它可以与交易行、产品和供货关系由不同数据主体维护。
- `PARTSUPP` 是独立存储的产品—供应商关联事实，具有复合主键并提供供应成本；它不是JOIN输出行。
- `LINEITEM` 是独立交易明细事实，提供数量、价格、折扣和物理行标识。
- `ORDERS` 是独立订单事实，提供订单年份；同一订单可以包含多条交易明细。
- `NATION` 仅作稳定分类维表，不参与本轮收益分配。

P1适用于“购买并整合产品、供应商、供货关系和交易事实后生成统计产品”的数据产品边界。这是一种有业务意义但并非唯一正确的分配边界；不能将其自动外推到只购买交易数据的场景。

## P2：保守玩家定义

玩家关系：`PARTSUPP`、`LINEITEM`、`ORDERS`。外生固定：`PART`、`SUPPLIER`、`NATION`。

每条witness为：

`{PS_(partkey,suppkey), L_(orderkey,linenumber), O_orderkey}`。

业务依据：

- 产品和供应商主数据被视为已持有的固定目录/维表，不参与本轮收入分配。
- `PARTSUPP`仍是供货关系及成本事实，`LINEITEM`是交易明细，`ORDERS`提供时间归属，三者均独立存储并可独立缺失。

P2用于检查Q9的非星形性是否依赖把主数据表纳入玩家，而不是为了让图更简单而事后缩减。

## 共同物理语义

每个玩家对应数据库中的一个真实底层tuple；JOIN输出行不是玩家。一个玩家加入联盟只带入对应物理tuple，不自动带入通过外键关联的其他tuple。P1/P2均不使用owner打包，也不把同一 `(part,supplier)` 的多条交易合并成玩家。
