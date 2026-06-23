# Statistical Analysis Plan v1.0

## 1. 文件信息

**项目名称：** Mental Delirium Long-term Outcomes Study  
**SAP版本：** v1.0  
**版本日期：** 2026年6月20日  
**对应Protocol：** `protocol/protocol_v1.md`  
**对应DAG：** `dag/dag_v1.md`  
**对应正式变量字典：** `data_dictionary/data_dictionary_v1.md`  
**冻结配置：** `config/frozen_study_definitions_v1.yaml`  
**冻结配置SHA256：** `16D40CC98A02FA7824C639ED6D299DC4741CEFA237D1A00406F96CB138804E73`  
**精神科映射：** `psychiatric_code_mapping_validated_v1.1.csv`  
**精神科映射SHA256：** `30297cf7415fe84e2a352adbf65e6310801034f64320310802f35db56baef954`

**研究状态：** Protocol、DAG、正式变量字典和SAP均已形成；SAP批准并封存后，方可构建正式分析数据集及运行预设模型。

---

## 2. 分析原则

1. 本研究为预后关联和临床风险分层研究，不解释为严格因果效应研究。
2. 主要暴露、主要结局、研究人群和时间零点均采用冻结定义，不根据正式分析结果修改。
3. 四分类联合表型为主要临床呈现方式。
4. 精神科共病、早期谵妄及其乘积项模型用于正式交互检验。
5. 协变量由DAG预先规定，不使用单因素P值、逐步回归、LASSO或其他结果导向方法筛选。
6. 所有效应估计同时报告95%置信区间。
7. 不以“统计学显著/不显著”作为唯一解释依据，重点报告效应大小、绝对风险、精确度及临床一致性。
8. 正式模型运行前必须冻结患者级分析数据集和全部分析代码。
9. 所有主分析使用双侧检验，名义显著性水平为0.05。
10. 次要、交互、亚组和敏感性分析主要用于估计和稳健性评价，不进行机械的多重比较显著性判定。

---

## 3. 分析软件与可复现性

### 3.1 数据构建

- 本地数据库：DuckDB；
- 原始数据：MIMIC-IV v3.1；
- 官方衍生概念：MIT-LCP mimic-code；
- 固定官方commit：
  `57069783095e7770e66ea97da264c0200078ddbf`。

### 3.2 统计分析

优先使用R完成正式统计分析。

推荐R版本：4.3.3或项目实际冻结版本。

计划使用的包包括但不限于：

- `survival`
- `survminer`
- `riskRegression`
- `cmprsk`
- `rms`
- `splines`
- `mice`
- `sandwich`
- `lmtest`
- `boot`
- `ggplot2`
- `tableone`或等价描述性统计包

正式运行时必须记录：

- R版本；
- 所有包版本；
- 操作系统；
- DuckDB版本；
- 随机种子；
- 分析脚本SHA256；
- 分析数据集SHA256；
- 输出文件SHA256。

---

## 4. 分析人群

### 4.1 基础人群

满足以下条件：

1. 年龄≥18岁；
2. 每位患者第一次符合条件的ICU住院；
3. ICU住院时间≥24小时；
4. 存活至index hospitalization出院。

冻结基础人群数量：46,316人。

### 4.2 主要分析人群

基础人群中，早期72小时谵妄状态按冻结规则可明确分类者。

冻结主要分析人群数量：29,458人。

### 4.3 谵妄不可分类人群

冻结数量：16,858人。

该人群不进入主要结局模型，但用于：

- 可分类与不可分类描述比较；
- 选择模型；
- IPSW敏感性分析。

### 4.4 死亡分析有效人群

主要分析人群中，排除以下仅影响死亡结局分析的记录：

- `DOD < index_admission_date`
- `index_admission_date ≤ DOD < index_discharge_date`

这些患者不从再住院和ICU再入分析中自动排除。

死亡分析应报告：

- 原始主要分析人群数量；
- 因死亡日期逻辑异常被排除的人数；
- 最终死亡分析人数。

### 4.5 保守再住院分析人群

90天同系统再住院和一年同系统ICU再入的主要分析人群限定为：

> approximate actual discharge-year upper bound ≤ 2021

该限制用于降低数据库末端截断风险。

技术审计时，72小时可分类人群中约24,033人符合该条件。

该样本量必须在正式分析数据集构建后重新确认。

### 4.6 全样本再住院敏感性人群

全部29,458名72小时谵妄可分类患者。

该分析解释为：

> 在MIMIC所属系统记录中观察到的再住院或ICU再入。

不能解释为完整的全医疗系统再住院发生率。

---

## 5. 暴露定义

### 5.1 主要精神科共病

`psych_primary_documented_by_index`

定义为index hospitalization之前或本次index hospitalization中，记录以下任一主要精神科类别：

- depressive disorders；
- anxiety disorders；
- trauma and stressor-related disorders；
- bipolar disorders；
- schizophrenia spectrum and other primary psychotic disorders。

无相应诊断代码解释为“未记录主要精神科共病”，而非确认无精神疾病。

### 5.2 早期ICU谵妄

`delirium_status_72h`

- 阳性：ICU入科后72小时内至少一次直接谵妄评估为Positive；
- 阴性：无Positive，且至少两个不同自然日有有效Negative；
- UTA不计为Negative；
- 与Observed RASS≤−4在前后1小时内匹配的Negative无效；
- 其他情况为不可分类。

### 5.3 四分类联合表型

`joint_exposure_4level`

1. 无精神科共病、无谵妄；
2. 有精神科共病、无谵妄；
3. 无精神科共病、有谵妄；
4. 有精神科共病、有谵妄。

Group 1为参考组。

### 5.4 交互变量

正式交互模型包括：

- `psych_primary_documented_by_index`
- `delirium_binary_for_interaction`
- `psych_primary_documented_by_index × delirium_binary_for_interaction`

---

## 6. 结局定义

## 6.1 主要结局：一年全因死亡

时间零点：

> index hospitalization出院日期。

主定义：

`index_discharge_date < DOD ≤ index_discharge_date + 365 days`

同日DOD不计入主定义。

随访时间为：

- 从出院至死亡；
- 无一年内死亡者截尾于365天。

### 主要死亡结局输出

- 一年累积死亡风险；
- 组间绝对风险差；
- Cox模型HR；
- 365天标准化风险；
- 365天标准化风险差和风险比。

---

## 6.2 关键次要结局：90天同系统再住院

定义为：

- index hospitalization出院后；
- 新的`hadm_id`；
- `admittime > index_dischtime`；
- 90天内首次同系统住院。

死亡在再住院发生前视为竞争事件。

主分析使用保守再住院分析人群。

---

## 6.3 探索性结局：一年同系统ICU再入

定义为：

- index hospitalization出院后新的医院住院；
- 该新住院中首次ICU入住；
- 发生于出院后365天内。

死亡在ICU再入前视为竞争事件。

主分析使用保守再住院分析人群。

---

## 7. 描述性分析

### 7.1 总体与四组描述

按四分类联合表型报告：

- 样本量；
- 年龄；
- 性别；
- race/ethnicity；
- anchor_year_group；
- admission type；
- admission location；
- ICU类型；
- 既往住院次数；
- 既往ICU次数；
- Charlson；
- 痴呆；
- 物质使用障碍；
- 慢性神经系统疾病；
- 保险；
- 语言；
- 婚姻状态；
- 急性严重度；
- 早期有创机械通气；
- 早期血管活性药；
- 早期RRT；
- Sepsis-3；
- 主要和次要结局事件。

### 7.2 汇总方式

- 近似正态连续变量：均值±标准差；
- 偏态连续变量：中位数和四分位数；
- 分类变量：人数和百分比。

### 7.3 组间差异

主要使用标准化差异：

- 连续变量：standardized mean difference；
- 分类变量：总体标准化差异或各水平标准化差异。

不使用表1的P值决定协变量纳入。

### 7.4 缺失情况

对每个变量报告：

- 非缺失人数；
- 缺失人数；
- 缺失比例；
- 四组缺失比例；
- 缺失模式。

---

## 8. 协变量定义与模型层级

## 8.1 Model 0：未调整模型

仅包含四分类联合表型。

---

## 8.2 Model 1：核心调整模型

固定纳入：

1. `age_at_index_admission`
2. `sex_recorded`
3. `race_group`
4. `data_era_group`，使用`anchor_year_group`
5. `admission_type_group`
6. `admission_location_group`
7. `first_careunit_group`
8. `prior_mimic_hospitalizations`
9. `prior_mimic_icu_stays`
10. `charlson_documented_by_index`
11. `dementia_documented_by_index`
12. `substance_use_documented_by_index`
13. `chronic_neurologic_disease`
14. `pre_admission_care_proxy`

### 函数形式

- 年龄：限制性立方样条，默认4个结点；
- Charlson：先作为连续变量，使用限制性立方样条或线性形式，根据预设分布诊断决定；
- 既往住院次数和既往ICU次数：优先使用`log1p(count)`；
- 多分类变量使用预先冻结的分类映射和哑变量编码。

函数形式的选择依据：

- 分布；
- 临床合理性；
- 非线性诊断；

不得依据暴露效应是否显著作出选择。

---

## 8.3 Model 2：急性严重度扩展模型

Model 1基础上增加：

1. `nonneurologic_sofa_zero_imputed_0_24h`
2. `nonneurologic_sofa_observed_components_n_0_24h`

### non-neurologic SOFA主处理

包含：

- respiratory；
- coagulation；
- liver；
- cardiovascular；
- renal。

明确排除：

- CNS；
- GCS。

主定义：

- 未观测器官分项暂按0分；
- 同时调整已观测器官分项数量0～5。

理由：

- 完整五分项病例比例过低；
- 仅使用完整病例会造成严重样本损失；
- observed component count用于部分控制“未测量不等于正常”的测量过程差异。

该做法属于预设的实用性严重度调整，不代表未测量器官功能一定正常。

---

## 8.4 Model 2B：器官支持替代模型

Model 1基础上加入：

- `invasive_ventilation_0_24h`
- `vasopressor_any_0_24h`
- `rrt_any_0_24h`

Model 2和Model 2B不在同一模型中同时纳入所有高度重叠变量。

Model 2为主要扩展模型。

Model 2B为敏感性分析。

---

## 8.5 Model 3：社会背景扩展模型

Model 2基础上加入：

- `insurance_group`
- `language_group`
- `marital_status_group`

Model 3为进一步敏感性或解释性模型，不作为主要结论依据。

---

## 8.6 不进入主要调整模型的变量

- ICU住院总时长；
- 医院住院总时长；
- 谵妄后镇静或镇痛；
- 72小时后机械通气；
- 抗精神病药；
- 身体约束；
- 谵妄持续时间；
- hospice；
- 出院去向；
- 出院后照护；
- 结局后变量。

---

## 9. 主要结局统计模型

## 9.1 未调整分析

按四组绘制：

- Kaplan–Meier生存曲线；
- 365天风险表；
- log-rank检验仅作总体描述。

同时报告每组：

- 365天死亡数；
- 365天死亡比例；
- 每100人年死亡率。

---

## 9.2 Cox比例风险模型

依次拟合：

- Model 0；
- Model 1；
- Model 2；
- Model 3作为补充。

主要报告：

- Group 2 vs Group 1 HR；
- Group 3 vs Group 1 HR；
- Group 4 vs Group 1 HR；
- 95%CI。

---

## 9.3 比例风险假设

使用：

- Schoenfeld残差；
- 暴露与`log(time)`交互；
- 图形检查。

### 处理规则

若四分类暴露总体比例风险检验P<0.05，或图形显示明显系统性偏离：

1. 仍报告整体365天Cox HR，标明其为平均相对效应；
2. 预设分段模型：
   - 0～30天；
   - 31～90天；
   - 91～365天；
3. 或加入暴露×时间交互；
4. 主要解释优先采用365天标准化绝对风险，而非单一HR。

不因个别协变量轻度违反比例风险而删除协变量；必要时对该协变量分层或允许时间变化效应。

---

## 9.4 标准化绝对风险

基于调整后生存模型，通过g-computation/模型标准化估计：

- 每位患者分别设为四种联合暴露状态；
- 其他协变量保持观测值；
- 计算365天预测生存概率；
- 对全体患者平均。

报告：

- 每组365天标准化死亡风险；
- 与Group 1的风险差；
- 与Group 1的风险比；
- bootstrap 95%CI。

默认bootstrap重复次数：1,000次。

如计算资源不足，可使用500次作为技术最低要求，但最终投稿版优先1,000次。

---

## 10. 90天再住院分析

## 10.1 主要人群

approximate actual discharge-year upper bound ≤2021的保守队列。

---

## 10.2 描述性竞争风险分析

绘制并报告：

- 再住院累积发生函数；
- 死亡累积发生函数；
- 90天累积发生率。

---

## 10.3 主要相对效应模型

cause-specific Cox模型：

- 再住院为事件；
- 再住院前死亡按竞争事件时点删失；
- 报告cause-specific HR；
- 依次拟合Model 0、Model 1、Model 2。

该模型解释为：

> 在仍存活且尚未再住院患者中，再住院瞬时发生率的相对差异。

---

## 10.4 补充模型

Fine–Gray模型：

- 死亡为竞争事件；
- 报告subdistribution HR；
- 使用与主要模型相同的预设协变量集合；
- 用于补充解释人群层面的累积发生差异。

Fine–Gray模型不替代cause-specific Cox作为主要相对效应模型。

---

## 10.5 标准化90天风险

使用适合竞争风险的模型标准化方法估计：

- 四组90天再住院累积发生风险；
- 风险差；
- 风险比；
- 95%CI。

---

## 11. 一年ICU再入分析

采用与90天再住院相同的框架：

1. 保守年份队列；
2. 死亡作为竞争事件；
3. cause-specific Cox为主要相对效应；
4. Fine–Gray为补充；
5. 报告365天累积发生风险；
6. 报告标准化绝对风险。

该结局定位为探索性结局，解释应弱于主要和关键次要结局。

---

## 12. 交互作用分析

## 12.1 乘法交互

拟合二元暴露模型：

- psychiatric comorbidity；
- early ICU delirium；
- psychiatric comorbidity × early ICU delirium。

在Model 1和Model 2中分别估计。

报告：

- 交互项系数；
- 比值尺度上的交互效应；
- Wald检验P值；
- 95%CI。

不预设交互方向。

---

## 12.2 加法交互

加法交互不直接用Cox HR代入RERI公式。

### 死亡结局

基于调整后365天标准化风险计算：

- `R00`：无精神科/无谵妄；
- `R10`：有精神科/无谵妄；
- `R01`：无精神科/有谵妄；
- `R11`：有精神科/有谵妄。

风险差尺度交互：

`IC = R11 - R10 - R01 + R00`

同时报告：

- 相对于Group 1的标准化风险比；
- RERI；
- AP；
- synergy index。

RERI、AP和S仅在分母和风险值允许时计算。

### 再住院和ICU再入

基于固定时间点竞争风险标准化累积发生风险计算相同指标。

### 置信区间

采用患者层级bootstrap，默认1,000次。

---

## 13. 缺失数据处理

## 13.1 暴露

- 精神科“无诊断记录”编码为未记录；
- 谵妄不可分类不插补为阴性；
- 主要分析不对谵妄状态做多重插补。

---

## 13.2 主要协变量

首先报告缺失率。

### 低缺失变量

缺失<1%：

- 可采用完整协变量记录；
- 分类变量可保留Unknown类别。

### 中等缺失变量

缺失1%～20%：

- 连续或有序变量优先使用多重插补；
- 分类结构性变量可在主要分析中保留Unknown类别，并在敏感性分析中多重插补。

### 高缺失变量

缺失>20%：

- 不自动进入Model 1；
- 如为Model 2关键变量，使用预设的领域特异处理；
- non-neurologic SOFA采用zero-imputed score加observed component count，不依赖完整病例。

---

## 13.3 多重插补

如Model 1或Model 3协变量需要插补：

- 使用MICE；
- 插补次数至少20次；
- 若最高缺失率明显高于20%，插补次数至少等于最高缺失百分比的整数值；
- 连续变量使用predictive mean matching；
- 二分类变量使用logistic regression；
- 多分类变量使用polytomous regression；
- 有序变量使用proportional odds模型。

插补模型应包含：

- 暴露；
- 所有模型协变量；
- 结局事件指示；
- 生存结局的Nelson–Aalen累计风险或适当时间信息；
- 不包含患者标识符。

各插补数据集分别拟合模型，使用Rubin法则合并。

---

## 13.4 完整病例敏感性分析

对Model 1运行完整病例敏感性分析。

完整病例结果不作为主结果，除非所有关键协变量缺失均极低。

---

## 14. 谵妄可分类选择偏倚分析

## 14.1 选择模型人群

基础人群46,316人。

结局：

- 可分类=1；
- 不可分类=0。

---

## 14.2 选择模型变量

固定候选：

- 年龄；
- 性别；
- race；
- anchor_year_group；
- admission type；
- admission location；
- ICU类型；
- insurance；
- language；
- marital status；
- 既往住院次数；
- 既往ICU次数；
- strict-prior精神科共病；
- strict-prior痴呆；
- strict-prior物质使用障碍；
- 早期急性严重度；
- 0～24小时有创机械通气；
- 0～24小时血管活性药；
- 0～24小时RRT。

不纳入：

- documented-by-index精神科暴露；
- 最终谵妄状态；
- ICU和医院总住院时长；
- hospice；
- 出院去向；
- 长期结局。

---

## 14.3 概率生成

采用交叉验证或out-of-fold预测：

- 默认5折交叉验证；
- 每名患者的可分类概率来自未包含该患者的训练折；
- 主模型使用预设logistic regression；
- 可使用非线性年龄和计数变量；
- 不以AUC最大化作为唯一目标。

---

## 14.4 权重

稳定化选择权重：

`P(S=1) / P(S=1|X)`

主截尾：

- 1st percentile；
- 99th percentile。

进一步敏感性：

- 5th percentile；
- 95th percentile。

报告：

- 截尾前后最小值、最大值、均值和分位数；
- ESS；
- 加权前后SMD；
- 极端权重人数。

---

## 14.5 加权结局模型

在主要可分类队列中使用IPSW重新拟合：

- 一年死亡Model 1；
- 一年死亡Model 2；
- 90天再住院主要模型；
- 一年ICU再入探索模型。

使用稳健标准误。

IPSW作为敏感性分析，不替代未加权主分析。

---

## 15. 预设敏感性分析

## 15.1 精神科暴露敏感性

1. strict-prior psychiatric comorbidity；
2. none / strict-prior / index-only三分类；
3. common mental disorders；
4. serious mental illness；
5. 排除痴呆患者；
6. 物质使用障碍加入扩展暴露；
7. 各主要精神科类别分别描述，不进行无限多重建模。

---

## 15.2 谵妄定义敏感性

1. 48小时谵妄定义；
2. 整个ICU期间谵妄定义；
3. 直接评估与CAM-ICU组件一致病例；
4. 排除存在RASS冲突记录患者；
5. 仅使用评估密度较高的患者。

冻结72小时主定义不修改。

---

## 15.3 死亡结局敏感性

1. 将同日DOD计入一年死亡；
2. 排除hospice出院患者；
3. 同时排除hospice和同日DOD；
4. 0～30天、31～90天、91～365天分段效应；
5. 完整SOFA替代non-neurologic SOFA；
6. OASIS替代non-neurologic SOFA；
7. 器官支持替代模型；
8. Model 1完整病例分析；
9. IPSW分析。

---

## 15.4 再住院和ICU再入敏感性

1. 全29,458人数据库记录事件分析；
2. 更宽松的90天近似年份限制；
3. 更严格保守年份限制；
4. Fine–Gray替代/补充cause-specific Cox；
5. 排除hospice患者；
6. IPSW分析。

---

## 15.5 急性严重度敏感性

1. Model 2主版本：
   zero-imputed non-neurologic SOFA + observed component count；
2. 五个器官分项各自缺失指示变量；
3. non-neurologic SOFA完整病例；
4. 完整SOFA；
5. OASIS；
6. 早期器官支持替代模型；
7. 0～6小时严重度版本，若样本量和测量覆盖允许。

---

## 15.6 RRT敏感性

器官支持替代模型中：

1. 使用全部早期RRT；
2. 排除strict-prior维持性透析/ESKD患者；
3. 单独使用CRRT；
4. 不将RRT作为主模型必要变量。

---

## 16. 亚组分析

预设且数量有限：

1. 年龄：
   - <65岁；
   - 65～79岁；
   - ≥80岁。
2. 性别；
3. ICU类型；
4. 痴呆；
5. 早期有创机械通气；
6. common mental disorder vs serious mental illness；
7. strict-prior vs index-only；
8. anchor_year_group。

### 亚组规则

- 使用交互项检验异质性；
- 不根据各亚组内部P值判断效应差异；
- 报告效应值、95%CI和交互P值；
- 亚组结果为探索性；
- 不进一步无限细分。

---

## 17. 多重比较

### 17.1 主要结局

主要结局为一年死亡，四分类暴露的总体检验和预设组间比较不进行形式化校正，但明确其层级。

### 17.2 次要、探索和亚组

- 重点报告效应大小和置信区间；
- P值作为辅助；
- 可补充Benjamini–Hochberg FDR结果；
- 不因FDR结果改变主结论；
- 不对敏感性分析进行“显著性计数”。

---

## 18. 模型诊断

### 18.1 共线性

检查：

- Charlson与其相关慢性病变量；
- non-neurologic SOFA与器官支持；
- admission type、ICU类型和急性疾病类型。

使用：

- 相关矩阵；
- 方差膨胀因子；
- 条件指数；
- 临床解释。

不使用纯数据驱动逐步删除。

### 18.2 连续变量

检查：

- 分布；
- 极端值；
- 非线性；
- 样条图。

### 18.3 影响点

检查：

- deviance residuals；
- dfbeta；
- 极端预测值。

### 18.4 竞争风险模型

检查：

- 事件编码；
- 死亡与再住院时间顺序；
- 同日事件处理；
- Fine–Gray收敛；
- 预测累积发生函数范围。

### 18.5 加权模型

检查：

- 权重分布；
- ESS；
- 加权平衡；
- 稳健标准误；
- 极端权重敏感性。

---

## 19. 统计报告格式

### 19.1 主要结果

每个结局报告：

- 分析人数；
- 事件数；
- 未调整风险；
- 调整后相对效应；
- 标准化绝对风险；
- 95%CI；
- 关键敏感性结果。

### 19.2 小数位

- 百分比：1位或2位小数；
- HR/SHR/RR：2位小数；
- 风险差：每100人或百分点，1～2位小数；
- P值：3位小数，小于0.001写`<0.001`；
- SMD：2位小数。

### 19.3 语言

使用：

- “associated with”
- “higher/lower observed risk”
- “prognostic association”
- “effect modification”

避免：

- “caused”
- “prevented”
- “synergistically caused”
- “independent causal effect”

---

## 20. 预设表格

### Table 1

四组基线特征。

### Table 2

一年死亡：

- 事件数；
- 未调整HR；
- Model 1 HR；
- Model 2 HR；
- 365天标准化风险；
- 风险差。

### Table 3

90天同系统再住院：

- 事件数；
- cause-specific HR；
- Fine–Gray SHR；
- 标准化90天累积发生风险。

### Table 4

一年同系统ICU再入。

### Table 5

乘法和加法交互。

### Supplementary Tables

- 可分类与不可分类比较；
- 精神科类别重叠；
- strict-prior敏感性；
- 48小时谵妄敏感性；
- 完整SOFA/OASIS/器官支持敏感性；
- IPSW诊断；
- hospice和同日DOD敏感性；
- 再住院年份限制敏感性；
- 缺失数据与插补诊断。

---

## 21. 预设图形

### Figure 1

研究人群流程图。

### Figure 2

四组一年死亡Kaplan–Meier曲线。

### Figure 3

四组365天标准化死亡风险及95%CI。

### Figure 4

90天同系统再住院累积发生函数。

### Figure 5

一年同系统ICU再入累积发生函数。

### Figure 6

主要及敏感性分析森林图。

### Supplementary Figures

- 加权前后SMD love plot；
- 权重分布；
- Schoenfeld残差；
- 年龄和Charlson非线性效应；
- 交互绝对风险图；
- 缺失模式图。

---

## 22. 正式分析数据冻结

正式建模前必须完成：

1. 构建一人一行分析表；
2. 验证主键唯一；
3. 核对队列人数；
4. 核对四组人数；
5. 核对主要结局事件数；
6. 核对时间逻辑；
7. 生成缺失率报告；
8. 生成范围和异常值报告；
9. 保存所有衍生变量版本和SHA256；
10. 生成`analysis_data_freeze_log.md`；
11. 计算分析表内部SHA256；
12. 保存session information；
13. 禁止手工修改患者级分析表。

若正式构建人数与冻结可行性人数不一致，必须先生成差异报告，不得直接继续建模。

---

## 23. 偏离SAP的处理

任何偏离必须记录：

- 日期；
- 偏离内容；
- 原因；
- 是否在查看正式结果前决定；
- 是否影响主要结论；
- 是否需要Protocol/SAP修订；
- 修订前后SHA256。

探索性分析必须明确标记为post hoc。

不得把post hoc分析重新描述为预设分析。

---

## 24. SAP批准后的执行顺序

1. 构建并持久化官方衍生概念；
2. 构建项目特异non-neurologic SOFA；
3. 构建正式患者级分析表；
4. 完成QC和差异核对；
5. 冻结分析数据；
6. 运行Table 1；
7. 运行主要死亡模型；
8. 运行比例风险与模型诊断；
9. 运行标准化风险；
10. 运行再住院和ICU再入模型；
11. 运行交互分析；
12. 运行多重插补；
13. 运行IPSW；
14. 运行预设敏感性分析；
15. 自动生成表格和图形；
16. 撰写Results；
17. 撰写Discussion。

---

## 25. 当前禁止事项

SAP封存前后均禁止：

- 修改冻结精神科暴露；
- 修改冻结72小时谵妄主定义；
- 根据正式结果增加或删除主要协变量；
- 根据P值选择模型；
- 寻找“最显著”时间窗；
- 选择性报告交互；
- 删除不符合预期的敏感性分析；
- 将同系统再住院解释为全部再住院；
- 将观察性关联解释为因果效应。

---

## 26. SAP最终决定摘要

1. 一年全因死亡为主要结局；
2. 全29,458人进入主要死亡分析，死亡日期逻辑异常者仅从死亡模型排除；
3. 90天再住院和一年ICU再入主要使用保守年份队列；
4. 全29,458人再住院分析为敏感性分析；
5. Model 1为预设核心调整集合；
6. Model 2采用zero-imputed non-neurologic SOFA加observed component count；
7. 完整SOFA、OASIS和器官支持模型为敏感性分析；
8. cause-specific Cox为再住院主要相对效应模型；
9. Fine–Gray为补充；
10. 四分类表型用于主要展示；
11. 二元暴露加乘积项用于正式交互检验；
12. 加性交互基于固定时间点标准化风险；
13. 谵妄不可分类不做暴露插补；
14. 协变量适度缺失采用多重插补；
15. IPSW使用out-of-fold概率，主截尾1%/99%；
16. hospice保留在主分析，不作为主要模型协变量；
17. 同日DOD仅进入敏感性分析；
18. 不再增加前置技术审计，后续进入正式数据构建和冻结阶段。
