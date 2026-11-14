# 03 SQL 与来源结构修订

## 三个独立查询版本

|版本|物理玩家|地区语义|去重位置|目的|
|---|---|---|---|---|
|F0 `E/B/H`|E、B、H 每行独立|`B.city` 唯一决定场所地区|基础 JOIN 后自然唯一|历史简单企业中心来源|
|F1 `SITE_LINK`|E、B、H、`R1(rid,sid,city)`|同一场所—地区可有多条合法 R1 证明|先 `SELECT DISTINCT sid,eid,city,industry,workers`|增加替代证明，但证明不跨场所共享|
|F2 `ENTITY_LINK`|E、B、H、`R2(rid,eid,city)`|企业级地区证明可被该企业多个场所复用|同样先形成去重 eligible site|让一个 R2 玩家同时影响多个场所、COUNT DISTINCT、SUM 与比例|

SQL 文件位于 `sql/report_f0.sql`、`report_f1.sql`、`report_f2.sql`。`SUM` 只在去重后的 eligible site 上执行，所以重复地区证明不会重复就业人数。三个 Q 版本分开编号，绝不混入同一速度排名。

## 冻结结构结果

|游戏|N|JOIN 证明|变量出现|最大变量出现|重叠证明对|平均证明重叠|联合状态|
|---|---:|---:|---:|---:|---:|---:|---:|
|F0|10|4|12|2|2|0.333|16|
|F1 balanced|16|6|24|3|6|0.667|16|
|F1 concentrated|16|6|24|4|7|0.867|16|
|F2 balanced|14|8|32|4|12|0.857|16|
|F2 concentrated|14|8|32|6|16|1.143|16|

这说明 F1/F2 确实改变了来源证明复用，不只是改地区标签；但在本最小 fixture 中，最终六维统计值域没有扩大。证明分布由 balanced 改为 concentrated 后，Harsanyi 规模甚至可能下降（如 F2-G2 从 72 降为 56），因此“更多局部重叠必然更慢”被当前结果否定。

## SQL 语义验证

每个 Q 版本使用 65 个唯一的确定性边界/样本联盟进行 SQL—Python 逐坐标相等核验，共 325 个，全部 `VERIFIED`。F0 的历史 V2 已另有更广核验；本轮没有声称 F1/F2 完成全联盟 SQL 穷举。完整记录见 canonical run 的 `raw/sql_validation.csv`。

