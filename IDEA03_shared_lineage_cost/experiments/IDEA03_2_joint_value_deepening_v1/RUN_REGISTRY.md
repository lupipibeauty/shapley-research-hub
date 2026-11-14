# 运行登记

|run|状态|说明|
|---|---|---|
|`DEEP_20261113_153836`|`FAILED_CORRECTNESS`|SQL 服务业单独出现时 `mfg_workers=NULL` 未按评分层规则映射；保留空目录证据|
|`DEEP_20261113_153911`|`FAILED_SQL_BINDER`|F1/F2 中 `B.city` 与 `R.city` 歧义；已改为显式 `d.city=r.city`|
|`DEEP_20261113_153952`|`USER_STOPPED_DIAGNOSTIC`|SQL 逐联盟验证策略过慢，主动停止；未产生正式结果|
|`DEEP_20261113_155021`|`VERIFIED_SUPERSEDED`|初次完整 run；ROADD 资格标签随后收紧|
|`DEEP_20261113_155744`|`VERIFIED_CANONICAL`|5 games，15 `(Q,G)`，60 方法记录，325 SQL/Python 检查；ROADD 明确为表示诊断而非求解基线|

修改求解器资格标签后应以最新 `LATEST_RUN.json` 指向的复跑为准；历史目录不删除。
