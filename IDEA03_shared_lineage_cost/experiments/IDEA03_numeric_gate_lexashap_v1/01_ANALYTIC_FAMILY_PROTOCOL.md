# 解析族协议

冻结测试族为

\[
F_{m,5}=\bigvee_{j=1}^{m}\bigwedge_{\ell=1}^{5}x_{j,\ell},\qquad m=1,\ldots,20.
\]

不同子句不共享变量，直接以 `list[set[Value]]` 送入官方 `lift_recursively`、`DNFCircuitNode.recursively_expand` 与 `Value.backward`，不经过 SQL、DuckDB、Q9、CSV、player map 或收入归一化。

由子句间同构、子句内对称及 Shapley 效率性，全部 `N=5m` 个玩家的解析 oracle 为 `1/N`。该 oracle 不依赖联盟枚举。

预注册门槛见 `config/protocol.json`；扫描后不修改门槛或网格。
