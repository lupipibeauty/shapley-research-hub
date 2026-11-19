# 待调查的真实业务/公共决策任务清单

## 使用原则

本清单是后续证据采集入口，不把“存在公开指标”自动写成“存在数据交易”或“存在合理收入池”。每个任务分别记录官方规则、统计输入、可观测行动和公开结果数据。2026-11-18 仅完成官方入口级核验，因规则会更新，正式实验前必须重新冻结版本与下载日期。

## TASK-BIZ-01：商业开店/扩张选址

- **现实任务**：企业比较地区，决定开店、扩张或关闭。
- **官方决策规则**：`MISSING`。美国 Census Business Builder 明确为小企业开店/扩张研究提供统计，但不存在统一官方“最优选址评分公式”。因此不能从工具内指标反推出买方效用。
- **候选统计指标**：人口与收入、行业结构、企业/场所数、就业、工资、消费者支出、竞争密度、通勤和地理信息。
- **官方数据入口**：Census Business Builder 与 Business/Owner Data Tools；County Business Patterns (CBP)；ACS/LEHD；Business Dynamics Statistics (BDS)。
- **可观测行动**：开业、关停、就业扩张/收缩。BDS 公开年度、行业和地区聚合结果；个体企业选址与决策理由通常不公开。
- **公开结果数据**：`PARTIAL`。BDS 有聚合开业/关停与就业变化；不能把它直接配对到某份报表的购买和使用。
- **对 IDEA-03 的用途**：作为“真实规则缺失”的对照任务；先访谈或获取采购/咨询流程，再冻结 `G`。
- **官方入口**：
  - https://www.census.gov/topics/business-economy/characteristics/data/tools.html
  - https://www.census.gov/programs-surveys/cbp/data.html
  - https://www.census.gov/programs-surveys/bds/about.html
- **状态**：`TASK_EXISTS / RULE_MISSING / OUTCOME_AGGREGATED / TRANSACTION_EVIDENCE_MISSING`。

## TASK-BIZ-02：机会区/政策性投资区位筛选

- **现实任务**：政府按法定规则指定可享税收激励的 census tracts，投资者随后选择项目地区。
- **官方决策规则**：低收入社区等法定资格条件，州级提名、财政部认证；具体批次必须冻结当期法规和提名程序。该规则决定“资格/指定”，不等于私人投资者选址效用。
- **统计指标与来源**：贫困率、家庭收入、census tract、城乡类别；IRS/Treasury 发布资格与指定清单。
- **可观测行动**：区域被提名/指定、Qualified Opportunity Fund 投资申报；投资项目微观结果可能受披露限制。
- **公开结果数据**：指定清单公开，真实资本流与长期社区结果只部分公开。
- **对 IDEA-03 的用途**：具有官方门槛和多层统计输入，适合作为“规则驱动统计产品”；不能冒充一般商业选址。
- **官方入口**：https://www.irs.gov/credits-deductions/businesses/opportunity-zones
- **状态**：`OFFICIAL_RULE / PUBLIC_DESIGNATION / OUTCOME_PARTIAL / PRICE_MISSING`。

## TASK-HEALTH-01：Primary Care HPSA 短缺评分与指定

- **现实任务**：识别初级保健专业人员短缺地区并形成 0–25 分 HPSA score。
- **官方规则（2026 页面/手册）**：人口—服务提供者比率最高10分；100% FPL 以下人口比例最高5分；婴儿健康指数（婴儿死亡率或低出生体重率）最高5分；到最近非短缺可及服务源的旅行时间最高5分。人口—提供者比率双重加权。
- **统计数据来源**：HRSA 的 Shortage Designation Management System 使用国家标准数据集，州 Primary Care Offices/设施可提交补充数据。
- **可观测行动**：HPSA 指定与分数；NHSC 等项目站点/资源优先顺序受到指定和分数影响。
- **公开结果数据**：公开指定、分数、地理与设施数据较强；最终服务改善、人员迁入和患者结果需另接 HRSA 项目/卫生结果数据。
- **对 IDEA-03 的用途**：35坐标式多源层次报表可以重建一个明确评分；可研究底层记录对指定/评分保真的贡献、NULL/边界和门槛效应。收入 `R` 若无项目预算/合同依据，不得臆造。
- **官方入口**：
  - https://bhw.hrsa.gov/workforce-shortage-areas/shortage-designation/scoring
  - https://programportal.hrsa.gov/docs/pco/Manual-for-Policies-and-Procedures.pdf
- **状态**：`OFFICIAL_RULE / PUBLIC_SCORE / INPUT_DATA_MIXED / OUTCOME_LINKAGE_NEEDED`。

## TASK-DISASTER-01：Community Disaster Resilience Zones 指定

- **现实任务**：在 census tract 层面识别风险高且需求大的社区，定向提供技术援助和减灾融资/投资关注。
- **官方规则**：CDRZ Act 要求基于自然灾害风险评级、社会脆弱性和社区韧性指定。FEMA 2024 方法使用 National Risk Index（含18类自然灾害）及定制 Social Vulnerability 指标，并对 tribal tracts 使用基于 Expected Annual Loss 的附加方法；正式研究必须冻结具体方法版本。
- **统计数据来源**：FEMA NRI、CDC SVI派生主题、人口普查地理与多类灾害/损失数据。
- **可观测行动**：tract 被指定为 CDRZ；BRIC/FMA 等技术和财务支持、公共/私人韧性投资。
- **公开结果数据**：指定区域清单公开；项目申请、拨款与后续损失/韧性结果需跨 FEMA 数据集连接，且因果时滞长。
- **对 IDEA-03 的用途**：天然多指标、多层地理、非线性排序/门槛，可检验公共决策任务下多源记录贡献和多 G 复用；不能把风险评分直接解释为商业价格。
- **官方入口**：
  - https://www.fema.gov/sites/default/files/documents/fema_cdrz_designation-methodology.pdf
  - https://preptoolkit.fema.gov/web/hazard-explorer
- **状态**：`OFFICIAL_METHOD / PUBLIC_DESIGNATION / MULTISOURCE / LONG_TERM_OUTCOME_NEEDED`。

## TASK-DISASTER-02：地方减灾项目排序（后续候选）

- **现实任务**：地方在多个减灾项目间配置预算。
- **官方规则**：需按具体 BRIC/FMA funding notice 冻结，当前未完成版本核验。
- **指标/数据**：成本收益、Expected Annual Loss、社会脆弱性、项目可行性、匹配资金。
- **行动/结果**：申请、获批金额、项目实施、事后损失。
- **状态**：`RULE_VERSION_PENDING / PUBLIC_AWARD_PARTIAL / CAUSAL_OUTCOME_DIFFICULT`。

## 优先调查次序

1. HPSA：规则最明确，可先验证“完整统计产品→公开行动规则→可观测指定”的全链条。
2. CDRZ：多源与非线性更丰富，但版本和因果结果连接更复杂。
3. 商业选址：经济相关性强，但统一规则与微观行动数据缺失，需先做访谈/采购档案调查。
4. Opportunity Zones：可作为政策性区位指定对照，不能替代私人选址。

## 每个任务下一轮统一采集字段

`rule_version, legal_authority, output_action, input_indicator, source_table, geography, update_frequency, missing_rule, threshold, public_decision, public_outcome, transaction_price, buyer_identity, reproducibility_license`。

