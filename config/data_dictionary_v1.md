# Formal Data Dictionary v1.0

## 1. 文件信息

**项目：** Mental Delirium Long-term Outcomes Study  
**文件：** Formal Data Dictionary v1.0  
**日期：** 2026年6月19日  
**对应Protocol：** `protocol/protocol_v1.md`  
**对应DAG：** `dag/dag_v1.md`  
**冻结配置：** `config/frozen_study_definitions_v1.yaml`  
**冻结配置SHA256：** `16D40CC98A02FA7824C639ED6D299DC4741CEFA237D1A00406F96CB138804E73`  
**精神科映射：** `psychiatric_code_mapping_validated_v1.1.csv`  
**精神科映射SHA256：** `30297cf7415fe84e2a352adbf65e6310801034f64320310802f35db56baef954`

**状态：** 正式变量定义草案；尚未批准SAP；不得运行正式结局模型。

---

## 2. 目的

本变量字典用于把Protocol和DAG中的概念落实为可复现的数据变量，包括：

1. 规范变量名称；
2. 指定MIMIC来源表和字段；
3. 固定时间零点和测量窗口；
4. 规定数据类型、编码和缺失值处理；
5. 明确变量在主要模型、扩展模型、IPSW或敏感性分析中的角色；
6. 区分冻结变量、待构建变量和禁止调整变量；
7. 为Codex后续构建分析数据集提供唯一规范。

本文件不授权运行回归、交互模型、P值筛选或论文结果分析。

---

## 3. 变量角色代码

| 代码 | 含义 |
|---|---|
| `ID_INTERNAL` | 仅限本地连接和去重的内部标识，不得导出 |
| `COHORT` | 队列纳入、排除或时间零点变量 |
| `EXPOSURE_FROZEN` | 已冻结的主要暴露 |
| `OUTCOME_FROZEN` | 已冻结的结局 |
| `MODEL1_CORE` | DAG核心调整模型候选 |
| `MODEL2_ACUTE` | 急性严重度扩展模型候选 |
| `MODEL3_SOCIAL` | 社会背景扩展模型候选 |
| `IPSW` | 谵妄可分类选择模型候选 |
| `DESCRIPTIVE` | 表1或描述性结果变量 |
| `SENSITIVITY` | 敏感性分析变量 |
| `SUBGROUP` | 预设亚组变量 |
| `MEDIATOR_NO_ADJUST` | 可能中介，不进入主要调整模型 |
| `PROHIBITED` | 禁止用于主要调整模型 |
| `PENDING_AUDIT` | 定义已提出，但构建前仍需非结局导向的可行性审计 |

---

## 4. 通用时间规则

### 4.1 Index ICU时间

- `index_icu_intime`为index ICU入科时间；
- `index_icu_outtime`为index ICU出科时间；
- ICU早期窗口采用左闭右开区间：
  - 0～6小时：`[intime, intime + 6 hours)`；
  - 0～24小时：`[intime, intime + 24 hours)`；
  - 0～48小时：`[intime, intime + 48 hours)`；
  - 0～72小时：`[intime, intime + 72 hours)`。

### 4.2 医院出院时间

- 长期结局时间零点为`index_dischtime`；
- 死亡日期来自`patients.dod`；
- 再住院和ICU再入必须发生于新的医院住院；
- 同一index hospitalization内部再次转入ICU不计为出院后ICU再入。

### 4.3 日期移位与实际时期

- `admittime`、`dischtime`和ICU时间可用于同一患者内部的时间差和事件排序；
- 不得使用去标识化后的`year(admittime)`作为跨患者真实日历年份或医疗实践趋势变量；
- 跨患者时期调整使用`patients.anchor_year_group`；
- 年龄估算可使用：
  `anchor_age + year(admittime) - anchor_year`，
  因为该计算使用同一患者内部一致移位的年份差；
- `anchor_age = 91`保留为MIMIC年龄顶格编码，不尝试恢复真实年龄。

### 4.4 时间变量精度

- 时间戳变量以小时或天计算；
- `DOD`为日期级变量时，不伪造具体死亡时刻；
- 同日DOD按冻结主定义不计入出院后死亡，在敏感性分析中纳入。

---

## 5. 内部标识与队列变量

| canonical name | 角色 | 来源 | 定义/编码 | 缺失处理 | 使用 |
|---|---|---|---|---|---|
| `subject_id_internal` | ID_INTERNAL | `hosp.patients.subject_id` | 患者内部连接键 | 不允许缺失 | 不导出 |
| `hadm_id_internal` | ID_INTERNAL | `hosp.admissions.hadm_id` | index hospitalization连接键 | 不允许缺失 | 不导出 |
| `stay_id_internal` | ID_INTERNAL | `icu.icustays.stay_id` | index ICU stay连接键 | 不允许缺失 | 不导出 |
| `index_icu_intime` | COHORT | `icu.icustays.intime` | index ICU入科时间 | 缺失则排除 | 时间锚点 |
| `index_icu_outtime` | COHORT | `icu.icustays.outtime` | index ICU出科时间 | 缺失则排除 | ICU LOS |
| `index_admittime` | COHORT | `hosp.admissions.admittime` | index住院入院时间 | 缺失则排除 | 时间锚点 |
| `index_dischtime` | COHORT | `hosp.admissions.dischtime` | index住院出院时间 | 缺失则排除 | 长期结局time zero |
| `icu_los_hours` | COHORT | 计算 | `outtime-intime`，小时 | 逻辑异常则排除并记录 | 纳入条件≥24小时 |
| `hospital_survivor` | COHORT | `admissions.hospital_expire_flag`及时间核查 | 院内存活=1 | 不允许缺失 | 纳入条件 |
| `first_icu_per_patient` | COHORT | `icu.icustays` | 按`intime, stay_id`排序第一条 | 不允许缺失 | 纳入条件 |
| `delirium_classifiable_72h` | COHORT/IPSW | 冻结谵妄算法 | positive或negative=1，其他=0 | 不插补 | 主分析限制/选择模型 |
| `analysis_cohort_primary` | COHORT | 计算 | 所有纳入条件且72h可分类 | 不允许缺失 | 主分析人群 |

### 队列质量控制

1. 每位患者只能有一个index ICU stay；
2. `index_admittime ≤ index_icu_intime < index_icu_outtime ≤ index_dischtime`；
3. ICU LOS必须≥24小时；
4. 医院存活者不得有明确院内死亡标志；
5. 72小时可分类人数应与冻结记录一致；
6. 正式分析前重新生成STROBE流程图，但不得根据结果修改纳排标准。

---

## 6. 冻结精神科暴露

| canonical name | 角色 | 来源 | 定义/编码 | 缺失处理 | 使用 |
|---|---|---|---|---|---|
| `psych_primary_documented_by_index` | EXPOSURE_FROZEN | `hosp.diagnoses_icd` + 冻结v1.1映射 | index住院前或index住院中存在任一主要精神科类别：1；否则0 | 无代码记录编码0，解释为“未记录” | 主暴露 |
| `psych_primary_strict_prior` | SENSITIVITY/IPSW | 同上 | index住院开始前既往MIMIC住院存在主要精神科诊断：1 | 无记录=0 | 关键敏感性；IPSW候选 |
| `psych_primary_index_only` | SENSITIVITY/DESCRIPTIVE | 同上 | documented-by-index=1且strict-prior=0 | 不允许缺失 | 时间分层 |
| `psych_timing_group` | SENSITIVITY | 同上 | none / strict_prior / index_only | 不允许缺失 | 三分类敏感性 |
| `psych_depressive` | DESCRIPTIVE/SUBGROUP | 冻结v1.1映射 | documented-by-index抑郁障碍 | 无记录=0 | 类别描述 |
| `psych_anxiety` | DESCRIPTIVE/SUBGROUP | 冻结v1.1映射 | documented-by-index焦虑障碍 | 无记录=0 | 类别描述 |
| `psych_trauma_stressor` | DESCRIPTIVE/SUBGROUP | 冻结v1.1映射 | documented-by-index创伤及应激相关障碍 | 无记录=0 | 类别描述 |
| `psych_bipolar` | DESCRIPTIVE/SUBGROUP | 冻结v1.1映射 | documented-by-index双相障碍 | 无记录=0 | 类别描述 |
| `psych_psychotic` | DESCRIPTIVE/SUBGROUP | 冻结v1.1映射 | documented-by-index精神分裂症谱系/其他原发精神病性障碍 | 无记录=0 | 类别描述 |
| `psych_common_mental_disorder` | SENSITIVITY | 计算 | depressive或anxiety或trauma/stressor | 无记录=0 | CMD敏感性 |
| `psych_serious_mental_illness` | SENSITIVITY | 计算 | bipolar或psychotic | 无记录=0 | SMI敏感性 |
| `psych_category_count` | DESCRIPTIVE | 计算 | 同一患者主要精神科类别数，0～5 | 不允许缺失 | 重叠描述 |

### 精神科暴露限制

- 不得使用旧关键词映射；
- 不得改变v1.1代码表；
- 同一患者在二分类暴露中只计一次；
- 无记录不解释为确认无精神疾病；
- `documented_by_index`不解释为全部在ICU前确诊；
- strict-prior分析是时间顺序最可信的敏感性分析。

---

## 7. 冻结早期谵妄暴露

| canonical name | 角色 | 来源 | 定义/编码 | 缺失处理 | 使用 |
|---|---|---|---|---|---|
| `delirium_positive_72h` | EXPOSURE_FROZEN | `icu.chartevents`, itemid 228332 | 0～72小时内任一`Positive`=1 | 不插补 | 主暴露 |
| `delirium_valid_negative_days_72h` | EXPOSURE_FROZEN | itemid 228332 + RASS 228096 | 无Positive；有效Negative所在不同自然日数 | 不插补 | 阴性判定 |
| `delirium_negative_72h` | EXPOSURE_FROZEN | 冻结算法 | 无Positive且≥2个不同自然日有效Negative=1 | 不插补 | 主暴露 |
| `delirium_status_72h` | EXPOSURE_FROZEN | 冻结算法 | positive / negative / unclassifiable | 不插补 | 主分析 |
| `rass_conflicting_negative_n_72h` | DESCRIPTIVE/QC | itemid 228096 | Negative前后1小时内Observed RASS≤−4的记录数 | 不插补 | 质量控制 |
| `delirium_status_48h` | SENSITIVITY | 同一冻结逻辑，48小时窗口 | positive / negative / unclassifiable | 不插补 | 敏感性 |
| `delirium_status_full_icu` | SENSITIVITY/PENDING_AUDIT | 整个index ICU | 采用预设同类规则，细节在SAP固定 | 不插补 | 敏感性 |
| `delirium_first_positive_hours` | DESCRIPTIVE | 计算 | 首次Positive距ICU入科小时数 | 无Positive则缺失 | 描述/时间顺序审计 |
| `delirium_assessment_count_72h` | DESCRIPTIVE/IPSW | `chartevents` | 72小时内全部直接评估数 | 无记录=0 | 评估过程 |
| `delirium_uta_count_72h` | DESCRIPTIVE/IPSW | `chartevents` | 72小时内UTA数 | 无记录=0 | 评估过程 |

### 有效Negative规则

1. 72小时内不得有Positive；
2. Negative必须来自itemid 228332；
3. UTA不计为Negative；
4. Negative前后1小时内存在Observed RASS≤−4时，该Negative无效；
5. 至少两个不同自然日有有效Negative；
6. 只有一次Negative、只有UTA或无评估均不可分类。

---

## 8. 四组联合暴露

| canonical name | 角色 | 定义 |
|---|---|---|
| `joint_exposure_4level` | EXPOSURE_FROZEN | 1=no psych/no delirium；2=psych/no delirium；3=no psych/delirium；4=psych/delirium |
| `psych_binary_for_interaction` | EXPOSURE_FROZEN | `psych_primary_documented_by_index` |
| `delirium_binary_for_interaction` | EXPOSURE_FROZEN | positive=1，negative=0，仅可分类者 |
| `psych_delirium_product` | SENSITIVITY/ANALYSIS | 二元乘积项，仅在SAP批准后生成 |

Group 1为所有主要模型的参考组。

---

## 9. 冻结结局

### 9.1 一年全因死亡

| canonical name | 角色 | 来源 | 定义 |
|---|---|---|---|
| `death_date` | OUTCOME_FROZEN | `hosp.patients.dod` | 日期级死亡记录 |
| `death_365d_main` | OUTCOME_FROZEN | 计算 | `discharge_date < DOD ≤ discharge_date+365` |
| `time_to_death_or_censor_365d` | OUTCOME_FROZEN | 计算 | 出院至死亡或365天，单位天 |
| `death_same_day_discharge` | SENSITIVITY | 计算 | `DOD = discharge_date` |
| `death_365d_include_same_day` | SENSITIVITY | 计算 | `discharge_date ≤ DOD ≤ discharge_date+365` |
| `death_30d` | SENSITIVITY | 计算 | 主定义下0～30天死亡 |
| `death_90d` | SENSITIVITY | 计算 | 主定义下0～90天死亡 |

### 9.2 90天同系统再住院

| canonical name | 角色 | 来源 | 定义 |
|---|---|---|---|
| `readmission_90d_event` | OUTCOME_FROZEN | `hosp.admissions` | 新的住院`admittime > index_dischtime`且≤90天 |
| `time_to_readmission_90d` | OUTCOME_FROZEN | 计算 | 首次符合条件再住院时间 |
| `death_before_readmission_90d` | OUTCOME_FROZEN | `patients.dod` | 未再住院前死亡，竞争事件 |
| `followup_complete_90d` | PENDING_AUDIT | 数据覆盖审计 | 能否确认完整90天同系统观察期 |
| `readmission_same_day` | DESCRIPTIVE/SENSITIVITY | 计算 | 新hadm但`admittime`与出院同日；主定义不计 |

### 9.3 一年同系统ICU再入

| canonical name | 角色 | 来源 | 定义 |
|---|---|---|---|
| `icu_readmission_365d_event` | OUTCOME_FROZEN | `hosp.admissions` + `icu.icustays` | index出院后的新住院内首次ICU入住≤365天 |
| `time_to_icu_readmission_365d` | OUTCOME_FROZEN | 计算 | 出院至首次新住院ICU入科 |
| `death_before_icu_readmission_365d` | OUTCOME_FROZEN | `patients.dod` | ICU再入前死亡，竞争事件 |
| `followup_complete_365d` | PENDING_AUDIT | 数据覆盖审计 | 能否确认完整365天同系统观察期 |

### 随访完整性要求

在SAP批准前，Codex必须先完成非结局导向的数据覆盖审计，确定：

1. MIMIC v3.1本地数据的真实来源年份范围；
2. 如何利用`anchor_year_group`识别数据末期患者；
3. 是否能够可靠构建90天和365天完整随访标志；
4. 若不能可靠判断，则主要再住院分析采用时间到事件及行政删失框架，并将固定窗口二分类结果限于可确认完整随访者。

---

## 10. Model 1核心调整变量

| canonical name | 来源 | 定义/编码 | 缺失规则 | 模型角色 |
|---|---|---|---|---|
| `age_at_index_admission` | `patients.anchor_age`, `anchor_year`; `admissions.admittime` | `anchor_age + year(admittime)-anchor_year`；连续变量；91保留顶格 | 不应缺失；异常则审计 | MODEL1_CORE/IPSW |
| `sex_recorded` | `patients.gender` | 按数据库记录；保存原值和分析值 | 缺失=Unknown并报告 | MODEL1_CORE/IPSW |
| `race_group` | `admissions.race` | White / Black / Hispanic-Latino / Asian / Other-Multiple / Unknown-Unable | Unknown独立类别，不插补 | MODEL1_CORE/IPSW |
| `data_era_group` | `patients.anchor_year_group` | 保留官方实际年份区间类别 | 缺失则报告并设Unknown | MODEL1_CORE/IPSW |
| `admission_type_group` | `admissions.admission_type` | elective / urgent-emergency / observation / other，先审计原始水平 | 缺失=Unknown | MODEL1_CORE/IPSW |
| `admission_location_group` | `admissions.admission_location` | ED / transfer-hospital / transfer-facility / clinic-physician / procedure / other-unknown | 缺失=Unknown | MODEL1_CORE/IPSW |
| `first_careunit_group` | `icustays.first_careunit` | MICU / SICU / CCU-CVICU / Neuro / Trauma / Mixed-other | 缺失=Unknown | MODEL1_CORE/IPSW |
| `prior_mimic_hospitalizations` | `admissions` | index admittime前独立hadm数 | 无既往记录=0 | MODEL1_CORE/IPSW |
| `prior_mimic_icu_stays` | `icustays` | index ICU intime前独立stay数 | 无既往记录=0 | MODEL1_CORE/IPSW |
| `charlson_index_documented_by_index` | 官方Charlson SQL适配 | index住院前及index住院记录的CCI；保留总分与分项 | 无代码记录按官方逻辑；报告局限 | MODEL1_CORE |
| `charlson_index_strict_prior` | 官方Charlson SQL适配 | 仅index住院前诊断 | 无既往住院=0但标记无历史 | SENSITIVITY |
| `dementia_documented_by_index` | v1.1独立非主类别 | index前或index住院记录 | 无记录=0 | MODEL1_CORE |
| `dementia_strict_prior` | 同上 | 仅index前记录 | 无记录=0 | IPSW/SENSITIVITY |
| `substance_use_documented_by_index` | v1.1独立类别 | 酒精或其他物质使用障碍 | 无记录=0 | MODEL1_CORE |
| `substance_use_strict_prior` | 同上 | 仅index前记录 | 无记录=0 | IPSW/SENSITIVITY |
| `chronic_neurologic_disease` | Charlson/预设ICD映射 | 不含急性谵妄的慢性神经疾病 | 无记录=0 | MODEL1_CORE/PENDING_AUDIT |
| `pre_admission_care_proxy` | admission location等 | skilled nursing facility/long-term care等代理 | 缺失=Unknown | MODEL1_CORE/DESCRIPTIVE |

### Model 1规则

- 不按P值筛选；
- 年龄的函数形式由SAP决定，优先考虑限制性立方样条；
- 既往利用次数同时保留原始值和`log1p`版本，由SAP选择；
- Charlson、痴呆、神经疾病之间可能存在重叠，正式建模前检查共线性；
- 不因共线性自动删除临床关键变量，需按SAP预设处理；
- Model 1不得加入ICU LOS、hospital LOS、hospice或出院去向。

---

## 11. Model 2急性严重度候选变量

### 11.1 主要急性严重度构造

| canonical name | 来源 | 时间窗 | 定义 | 角色 |
|---|---|---|---|---|
| `non_neurologic_sofa_0_24h` | 官方SOFA/first-day SOFA SQL适配 | ICU入科0～24h | respiratory + coagulation + liver + cardiovascular + renal；排除CNS/GCS | MODEL2_ACUTE |
| `non_neurologic_sofa_0_6h` | 同上适配 | 0～6h | 相同五器官，作为更严格时间顺序敏感性 | SENSITIVITY |
| `full_sofa_0_24h` | 官方SOFA SQL适配 | 0～24h | 完整SOFA，仅扩展/敏感性 | SENSITIVITY |
| `oasis_0_24h` | 官方OASIS SQL适配 | 官方首日窗口 | 不进入最小模型；仅敏感性 | SENSITIVITY |

### 11.2 早期器官支持

| canonical name | 来源 | 时间窗 | 定义 | 角色 |
|---|---|---|---|---|
| `invasive_ventilation_0_24h` | 官方ventilation衍生概念 | 与0～24h窗口有重叠 | 正式有创通气状态，不使用procedure proxy | MODEL2_ACUTE/ALTERNATIVE |
| `invasive_ventilation_0_6h` | 同上 | 0～6h | 更严格时间顺序 | SENSITIVITY |
| `vasopressor_any_0_24h` | 官方vasoactive agent概念 | 与0～24h重叠 | norepinephrine/epinephrine/vasopressin/dopamine/phenylephrine等官方定义 | MODEL2_ACUTE/ALTERNATIVE |
| `norepinephrine_equivalent_max_0_24h` | 官方NE-equivalent概念 | 0～24h | 最大或时间加权剂量；具体汇总由SAP固定 | SENSITIVITY |
| `rrt_any_0_24h` | 官方RRT概念 | 与0～24h重叠 | 任一RRT | MODEL2_ACUTE/ALTERNATIVE |
| `crrt_any_0_24h` | 官方CRRT概念 | 与0～24h重叠 | 连续性RRT | DESCRIPTIVE/SENSITIVITY |

### 11.3 急性疾病类型

| canonical name | 来源 | 定义 | 角色 |
|---|---|---|---|
| `surgical_admission_status` | `hosp.services`, admission type, procedures | medical / elective surgical / emergency surgical / other；需盲于结局构建规则 | MODEL2_ACUTE/PENDING_AUDIT |
| `acute_neurologic_admission` | principal diagnosis + ICU类型 | 急性卒中、颅内出血、癫痫持续状态、TBI等预设映射 | MODEL2_ACUTE/SUBGROUP/PENDING_AUDIT |
| `sepsis3_index` | 官方sepsis3概念 | index ICU是否满足Sepsis-3 | MODEL2_ACUTE/SUBGROUP |
| `principal_diagnosis_group` | `diagnoses_icd.seq_num=1` + AHRQ映射 | 预设临床大类，不以结局筛选 | DESCRIPTIVE/PENDING_AUDIT |

### Model 2实施原则

1. 主要Model 2优先采用`non_neurologic_sofa_0_24h`；
2. 不默认同时加入non-neurologic SOFA与其高度重叠的通气、血管活性药、RRT变量；
3. 另建“器官支持替代模型”，以早期IMV、血管活性药和RRT替代综合评分；
4. 完整SOFA和OASIS不进入最小调整模型；
5. 0～6小时变量用于评价时间顺序敏感性；
6. 所有官方衍生SQL必须固定源commit、记录本地改动和SHA256。

---

## 12. Model 3社会背景变量

| canonical name | 来源 | 定义/编码 | 缺失规则 | 角色 |
|---|---|---|---|---|
| `insurance_group` | `admissions.insurance` | Medicare / Medicaid / private / self-pay / other | Missing独立类别 | MODEL3_SOCIAL/IPSW |
| `language_group` | `admissions.language` | English / non-English / unknown | Missing独立类别 | MODEL3_SOCIAL/IPSW |
| `marital_status_group` | `admissions.marital_status` | married-partnered / single / divorced-separated / widowed / unknown | Missing独立类别 | MODEL3_SOCIAL/IPSW |

这些变量作为结构性和社会背景代理，不解释为纯生物学因素。

---

## 13. IPSW选择模型变量

### 13.1 选择结局

`delirium_classifiable_72h`：

- 可分类=1；
- 不可分类=0；
- 分析基础人群为46,316名医院存活、ICU LOS≥24小时患者。

### 13.2 允许纳入

- age_at_index_admission；
- sex_recorded；
- race_group；
- data_era_group；
- admission_type_group；
- admission_location_group；
- first_careunit_group；
- insurance_group；
- language_group；
- marital_status_group；
- prior_mimic_hospitalizations；
- prior_mimic_icu_stays；
- psych_primary_strict_prior；
- dementia_strict_prior；
- substance_use_strict_prior；
- 可在最早24小时获得的正式急性严重度和器官支持变量。

### 13.3 禁止纳入

- documented-by-index精神科暴露；
- 最终谵妄状态；
- 72小时后变量；
- ICU LOS和hospital LOS；
- hospice；
- 出院去向；
- 死亡、再住院和ICU再入。

### 13.4 生成要求

- 使用交叉验证或out-of-fold预测概率；
- 输出未稳定和稳定化权重；
- 主敏感性使用1%/99%截尾；
- 5%/95%截尾作为进一步敏感性；
- 报告权重分布、协变量平衡和ESS；
- 不以AUC最大化为唯一模型选择标准。

---

## 14. 描述性与亚组变量

| canonical name | 定义 | 角色 |
|---|---|---|
| `hospice_discharge` | `discharge_location`中hospice相关状态 | DESCRIPTIVE/SENSITIVITY/MEDIATOR_NO_ADJUST |
| `discharge_destination_group` | home / home health / rehab / SNF-LTC / hospice / other | DESCRIPTIVE/MEDIATOR_NO_ADJUST |
| `icu_los_days` | ICU总时长 | DESCRIPTIVE/PROHIBITED |
| `hospital_los_days` | 医院总时长 | DESCRIPTIVE/PROHIBITED |
| `age_group_prespecified` | <65 / 65～79 / ≥80，仅亚组展示 | SUBGROUP |
| `early_imv_subgroup` | 正式0～24h有创通气 | SUBGROUP |
| `dementia_subgroup` | documented-by-index dementia | SUBGROUP |
| `icu_type_subgroup` | first_careunit_group | SUBGROUP |
| `psych_timing_subgroup` | strict-prior vs index-only | SUBGROUP |
| `data_era_subgroup` | anchor_year_group | SUBGROUP |

亚组模型不根据亚组内部P值判断差异；必须报告交互项和置信区间。

---

## 15. 禁止进入主要调整模型的变量

| 变量 | 原因 |
|---|---|
| ICU总住院时长 | 暴露后病程/潜在中介 |
| 医院总住院时长 | 暴露后病程及诊断机会 |
| 72小时后的机械通气 | 可能由谵妄或病程导致 |
| 72小时累计镇静药总量 | 时间顺序不清、指征混杂、潜在中介 |
| 谵妄发生后的苯二氮䓬/阿片/丙泊酚 | 暴露后治疗 |
| 抗精神病药使用 | 谵妄和行为异常后的治疗 |
| 身体约束 | 谵妄后的干预 |
| 谵妄持续时间 | 主要暴露后的病程 |
| hospice出院 | 暴露后治疗目标/中介 |
| 出院去向 | 暴露后转衔结果 |
| 90天再住院用于死亡模型 | 出院后中间事件 |
| 出院后门诊、康复或精神科随访 | 暴露后照护过程 |
| 任何结局后记录变量 | 时间顺序错误 |

上述变量可用于描述或专门的中介研究，但不得进入本研究主要总关联模型。

---

## 16. 缺失数据编码

### 16.1 暴露

- 精神科无代码记录编码为0，但表述为“未记录”；
- 谵妄不可分类不进行单值插补；
- 不将UTA、无评估或单次Negative插补为无谵妄。

### 16.2 分类协变量

- race、insurance、language、marital status和来源变量保留Unknown/Missing类别用于描述和IPSW；
- 正式结局模型中的缺失处理由SAP决定；
- 不因为缺失而合并具有不同临床含义的类别。

### 16.3 连续协变量

- 构建后报告缺失率、分布和极值；
- 不在数据构建阶段自动中位数填补；
- 多重插补仅在SAP批准后执行；
- 生理值必须先执行单位、范围和重复测量QC。

---

## 17. 官方衍生概念及构建顺序

采用MIT-LCP官方mimic-code作为基础，项目已审计的源commit为：

`57069783095e7770e66ea97da264c0200078ddbf`

推荐顺序：

1. Charlson：
   `mimic-iv/concepts/comorbidity/charlson.sql`
2. vasoactive agents及NE-equivalent：
   `mimic-iv/concepts/medication/`
3. RRT/CRRT：
   `mimic-iv/concepts/treatment/rrt.sql`
   及相关first-day概念
4. ventilation：
   `mimic-iv/concepts/treatment/ventilation.sql`
5. SOFA及first-day SOFA：
   `mimic-iv/concepts/score/sofa.sql`
   `mimic-iv/concepts/firstday/first_day_sofa.sql`
6. OASIS：
   `mimic-iv/concepts/score/oasis.sql`
7. Sepsis-3：
   `mimic-iv/concepts/sepsis/sepsis3.sql`

每个适配脚本必须记录：

- 官方路径；
- 官方commit；
- 原始文件SHA256；
- DuckDB适配说明；
- 本地脚本SHA256；
- 输入依赖；
- 输出行数；
- 主键重复检查；
- 与官方示例或合理范围的验证。

---

## 18. 构建前必须完成的非模型审计

### 18.1 原始分类水平

输出但不按结局比较：

- race全部原始值；
- admission_type全部原始值；
- admission_location全部原始值；
- first_careunit全部原始值；
- insurance、language、marital status全部原始值；
- anchor_year_group全部原始值。

据此冻结映射表。

### 18.2 数据时期

确认：

- 不再使用shifted admission year作为跨患者年代变量；
- `anchor_year_group`完整率；
- 不同时期的谵妄评估覆盖率；
- 本地MIMIC v3.1实际数据覆盖末期；
- 90天和365天随访完整性规则。

### 18.3 Charlson和慢性病

输出：

- documented-by-index与strict-prior Charlson分布；
- 两者差异；
- 无既往住院患者比例；
- Charlson分项与精神科、痴呆映射是否冲突。

### 18.4 急性严重度

输出：

- non-neurologic SOFA可构建率；
- 各器官分项缺失；
- 0～6h与0～24h分布；
- IMV、vasopressor、RRT覆盖率；
- 不同ICU类型的可用性；
- 不得进行结局关联或P值筛选。

### 18.5 结局随访

输出：

- 同日DOD人数；
- 数据末期出院人数；
- 可确认完整90天/365天观察者人数；
- 新hadm同日再入情况；
- 死亡与再住院的时间关系；
- 不运行正式竞争风险模型。

---

## 19. 正式分析数据集结构

最终患者级分析表仅在本地受控环境中生成，一行一名患者。

必须包含：

- 内部连接ID；
- 队列变量；
- 冻结暴露；
- 冻结结局；
- Model 1变量；
- Model 2变量；
- Model 3变量；
- IPSW变量；
- 敏感性和亚组变量；
- 变量来源版本；
- 数据构建版本。

不得导出或上传患者级分析表。

对外可提供：

- 非患者级代码；
- 数据字典；
- 汇总统计；
- 变量QC报告；
- 文件校验值。

---

## 20. 正式分析前数据冻结要求

在SAP批准且衍生变量验证通过后：

1. 生成唯一分析表；
2. 检查一人一行；
3. 生成变量缺失率报告；
4. 生成逻辑检查报告；
5. 生成四组人数和结局事件数；
6. 与冻结可行性结果比较并解释任何差异；
7. 计算分析表的内部SHA256；
8. 保存软件和包版本；
9. 创建analysis data freeze log；
10. 冻结后不得无记录修改。

---

## 21. 当前未决事项

下列事项由SAP最终决定，不得由Codex自行选择：

1. 年龄和连续变量的函数形式；
2. race等分类变量的最终合并映射；
3. Model 1中Charlson总分与分项的具体组合；
4. Model 2使用non-neurologic SOFA还是器官支持替代模型作为主要扩展；
5. non-neurologic SOFA缺失成分处理；
6. NE-equivalent汇总方式；
7. 0～6h严重度敏感性模型；
8. 数据末期行政删失；
9. 多重插补；
10. 再住院cause-specific与Fine–Gray模型报告顺序；
11. 交互标准化风险的计算方法；
12. 亚组分析的最终数量。

---

## 22. 当前授权范围

本变量字典v1.0批准后，Codex仅被授权：

- 审计原始分类水平；
- 审计随访覆盖；
- 适配和验证官方衍生变量；
- 生成非患者级QC汇总；
- 更新正式变量字典的技术来源字段。

Codex仍不被授权：

- 运行正式结局回归；
- 运行调整后交互模型；
- 根据P值选择变量；
- 修改冻结暴露；
- 修改主要结局；
- 撰写论文Results或Discussion。
