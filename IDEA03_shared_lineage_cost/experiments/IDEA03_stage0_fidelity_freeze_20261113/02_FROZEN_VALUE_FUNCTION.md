# 冻结价值函数规范

机器可读配置：`config/frozen_value_function.json`  
配置 SHA-256：`e05c7a9fc5a53a9b9f1493a556a48f21b3bebae0a78bf4bd792f6bf76708f591`

## 1. 数学对象

令玩家集合为冻结的 E/B/H 物理事实集合 (N)，固定维表和报表骨架不属于玩家。对任意联盟 (S\subseteq N)，

\[
Y(S)=Q(D_S),\qquad Y^*=Q(D_N).
\]

主价值函数为

\[
v_{\mathrm{fid}}(S)=L(Y(\varnothing),Y^*)-L(Y(S),Y^*).
\]

它衡量联盟对已售完整统计产品信息内容的重建程度。它不是现实总体准确率、买方支付意愿或直接货币效用。保真度定义联盟价值，Shapley 对这个同一个价值函数归因；二者不是两套贡献算法。

## 2. 坐标与损失

35个坐标分三类：

- counts：`enterprise_count`、`site_count`；
- sums：`workers`、`mfg_workers`；
- ratio：`mfg_share=mfg_workers/workers`。

每个数值坐标 (c) 的损失为

\[
\ell_c(y,y_c^*)=\frac{|y-y_c^*|}{a_c}.
\]

固定尺度：

- COUNT、COUNT DISTINCT、SUM：(a_c=\max(1,|y_c^*|))；
- 当前比例：(a_c=1)，因为有效域冻结为 ([0,1])；
- 后续 AVG：必须在贡献计算前用业务有效域或外部参考范围冻结，不能看过 Shapley 或耗时后调整。

不做事后 clipping。若合法查询产生超出冻结有效域的误差，直接作为 SQL/尺度审计异常报告。

## 3. NULL 与0

对任一坐标：

| 候选 | 目标 | 损失 |
|---|---|---|
| NULL | NULL | 0 |
| NULL | 数值 | 1（缺失定义） |
| 数值 | NULL | 1（多出的定义） |
| 数值 | 数值 | 固定尺度绝对误差 |

数值0不是 NULL。分母为0时 SQL 保留 `NULL`；评分层不得把它悄悄改成0。对满联盟目标恰为0、空联盟也为0的坐标，重建损失从一开始就是0；它不会凭空制造价值。

## 4. 主权重

\[
L(Y,Y^*)=\sum_c w_c\ell_c(Y_c,Y_c^*),\qquad \sum_c w_c=1.
\]

主基准：

- 全国、省、市三个层次各 (1/3)；
- 层内节点等权；
- counts、sums、ratio 三个统计族各 (1/3)；
- 族内指标等权。

因此全国 count/sum 单坐标权重 (1/18)、全国 ratio (1/9)；省级分别为 (1/36,1/18)；城市分别为 (1/72,1/36)。

## 5. 两套预注册敏感性权重

仅允许以下两套；它们不是事后调参：

1. `v_fid_level_emphasis`：全国/省/市权重 (1/2,1/3,1/6)，统计族仍等权。
2. `v_fid_content_emphasis`：层次等权，counts/sums/ratio 权重 (1/4,1/2,1/4)。

后续若要改变权重，必须建立新版本，不得覆盖本配置。

## 6. 跨地区联合补充任务

令

\[
d(S)=r_{PA}(S)-r_{PB}(S),\quad r_p=\mathrm{mfg\_share}_p.
\]

满联盟两个省的比例必须均有定义，目标 (d^*=d(N))。联合损失为

\[
L_{\mathrm{gap}}(S)=
\begin{cases}
1,&r_{PA}(S)\text{ 或 }r_{PB}(S)\text{ 为 NULL},\\
|d(S)-d^*|/2,&\text{否则}.
\end{cases}
\]

并定义

\[
v_{\mathrm{gap}}(S)=L_{\mathrm{gap}}(\varnothing)-L_{\mathrm{gap}}(S).
\]

它表示两省制造业就业占比差异这一比较统计的重建保真度，确实需要两个地区的统计结果共同决定评分。它仍不是经买方行为验证的货币效用，只是有明确统计含义的补充算法基准。

## 7. 收入映射

外生收入池 (R=1000)。先计算标准 Shapley (phi_i(v))，再按

\[
p_i=R\frac{\phi_i(v)}{v(N)}
\]

映射为金额。若 (v(N)\le0)，该产品定义无效并停止。由 Shapley 效率性，

\[
\sum_i p_i=R.
\]

这一步只做单位归一化，不改变玩家相对 Shapley；不能反向用支付结果修改 G。

## 8. 冻结结果

在 `FID_F0_N12` 上：

- 主保真度 (v(\varnothing)=0)，(v(N)=35/36)。不是1的原因是 A2、B2 的满联盟 `mfg_workers=0`，空联盟也为0，这两个坐标无需重建；
- 两套敏感性 (v(N)) 分别为 (71/72) 与 (23/24)；
- 联合 gap 任务 (v(\varnothing)=0,v(N)=1,d^*=-7/20)。

阶段0审计未发现必须修改的数学错误，因此该 G 版本正式冻结。历史 G0/G1/GC 保留为结构压力测试，不被覆盖。
