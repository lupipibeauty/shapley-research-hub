# 02 真正跨省共同来源配对

## Material Passport

- 阶段：IDEA-03 阶段1，实验2。
- 状态：严格配对 `VERIFIED`；放宽配对 `LOCAL_OBSERVATION`。
- 玩家：4 E + 6 B + 6 H，N=16；D 外生。
- SQL：冻结 F0 全 JOIN；6个最小 JOIN 见证。
- G：阶段0冻结 `v_fid/v_gap`，未修改。

## 1. 配对约束审计

两省统计满足

\[
C_A+C_B-C_{NAT}=C_{cross}.
\]

因此若同时固定省 A、省 B、全国的 `COUNT DISTINCT eid`，跨省共同企业数量也被固定，不能再任意从0变1。阶段1采用两层设计：

1. 严格配对固定全部35个满联盟坐标和 `C_cross=1`，只改变同一 E 玩家在见证中的集中方式；
2. 唯一一次放宽配对允许 PB 企业数2→3，从而让 `C_cross` 从0→1，并完整记录参照变化。

没有通过随机种子搜索或观察 Harsanyi 后修改生成器。

## 2. 固定物理事实

| sid | city | province | industry | workers |
|---|---|---|---|---:|
| S1 | A1 | PA | manufacturing | 8 |
| S2 | A1 | PA | service | 12 |
| S3 | A2 | PA | manufacturing | 7 |
| S4 | B1 | PB | manufacturing | 15 |
| S5 | B1 | PB | service | 5 |
| S6 | B2 | PB | service | 11 |

B、H 玩家及其属性在所有实例中相同；只有 B.eid 合法重连。每条场所仍有唯一 H，场所地理位置没有跨省复制。

## 3. 严格配对

| sid | STRICT_CONCENTRATED | STRICT_BALANCED |
|---|---|---|
| S1 | E1 | E1 |
| S2 | E2 | E2 |
| S3 | E1 | E2 |
| S4 | E1 | E1 |
| S5 | E3 | E3 |
| S6 | E4 | E4 |

两侧都存在真正跨省的同一物理玩家 E1：它同时进入 PA 和 PB 的最小 JOIN 证明。全部35个满联盟坐标完全相同，PA/PB/NAT 企业数为2/3/4，故 `C_cross=1`。

非同构证据在看结果前已冻结：企业见证度数多重集分别为 `[3,1,1,1]` 和 `[2,2,1,1]`。度数多重集在任意变量重命名下保持不变，所以两来源超图不是简单重命名。

全部严格控制均通过：相同玩家 ID、4/6/6 事实数、6个见证、相同完整报表、相同跨省 E 数。状态为 `VERIFIED`。

## 4. 放宽配对

| sid | RELAXED_NO_CROSS | RELAXED_ONE_CROSS |
|---|---|---|
| S1 | E1 | E1 |
| S2 | E2 | E2 |
| S3 | E2 | E2 |
| S4 | E3 | E1 |
| S5 | E4 | E3 |
| S6 | E3 | E4 |

两侧玩家、事实数、站点属性、6个见证、全国企业数4和所有城市坐标相同。跨省 E 数从0变1；根据集合恒等式，PB `enterprise_count` 必须从2变3。这是35个满联盟坐标中唯一变化的坐标，其固定尺度也从2变3。

两边企业度数多重集均为 `[2,2,1,1]`，但跨省支持 E 数0/1是地区标签保持同构下的不变量。因此它们不是保留地区语义的同构游戏；不过由于满联盟参照变化，该对照只能标记为 `LOCAL_OBSERVATION`，不能把所有差异归因于共享数量。

## 5. SQL/Python独立核验

每个新实例执行65个预注册掩码：空/满联盟、全部 singleton、全部 leave-one-out、关系类型边界、每个完整见证、每个见证分别缺 E/B/H、PA/PB 全见证以及移除跨省 E。4个实例共260次 SQL/Python 逐坐标核验，全部为 `VERIFIED`。

这不是对旧 F0 或旧 E1 SQL 的重复全量测试，只针对新物理关联及关键边界。

## 6. 自核二

1. 同一物理 E 是否进入两省证明：严格两侧均为 E1；放宽对照为0与1。
2. 来源关联是否实际不同：是，保存于 `new_fixture_records.csv`。
3. 严格配对完整报表是否固定：35/35坐标相同。
4. 是否只是玩家重命名：严格配对由度数多重集排除；放宽配对由跨省地区支持数排除。
5. 最小来源证明是否不同：是，S3 或 PB 三个场所见证中的 E 变量发生变化。
6. G 是否读取这些变化：严格配对15个坐标的来源分量变化；放宽配对19个。
7. 是否影响联盟价值与 Shapley：是，详见第三份报告。

原始证据：`config/stage1_protocol.json`、`results/new_fixture_records.csv`、`new_player_mapping.csv`、`pair_control_checks.csv`、`sql_python_validation.csv`。
