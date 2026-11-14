# 第二实现核验

本地未发现 AdaBan/ExaShap 作者实现；当前 Abramovich 仓库 README 只提供外部仓库链接，没有对应源码。未联网下载。

ProvSQL 现有档案只有环境检查记录，本轮没有可直接执行的同目标 ExaShap/ProvSQL 路径，也未安装环境。因此记录：

- ExaShap：`ENV_UNAVAILABLE_NOT_DOWNLOADED`
- ProvSQL：`PROVSQL_ENV_UNAVAILABLE`
- 独立解析 oracle：`VERIFIED`（对称性与效率给出 `1/N`）
- 同递推 Decimal 50/100 位：`VERIFIED_DIAGNOSTIC`

由于根因已由解析族、作者 raw 路径和精度依赖边界三重证据确认，按用户批准的提前停止规则，不再以下载第二实现为前提继续扩大实验。
