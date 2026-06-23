# Analysis Data Freeze Log

- Analysis table: `mental_delirium_analysis.analysis_dataset_v1_1`
- Freeze status: frozen for prespecified statistical modeling; no formal outcome model has been run.
- Build date: 2026-06-21T08:16:31
- Row count: 46,316
- Column count: 105
- Primary analysis cohort: 29,458
- Conservative readmission cohort: 24,033
- Table fingerprint method: MD5 of per-row hashes ordered by subject_id.
- Table fingerprint MD5: `cd6b47ec23c8a0fdea39f1f4de794674`
- DuckDB version: `v1.5.4`
- Python version: `3.12.13`
- Build script: `${PROJECT_DIR}\scripts\build_analysis_dataset_v1_1.py`
- Build script SHA256: `D0F803D887B538FF65DCE5BC899B31B9496DFC5B8CA3CE069904557294831E9B`

## Pre-Model Hotfix v1.1

- Competing-risk readmission and ICU-readmission status/time variables now stop follow-up at valid competing death before the target event.
- Model 1 Charlson implementation now uses the comorbidity-only documented-by-index score; age remains an independent model variable.
- prior_mimic_icu_stays is retained for description but flagged as constant_nonestimable and excluded from all formal model variable lists.
- pre_admission_care_proxy is retained for description but excluded from Model 1 and IPSW because it is derived from admission_location.
- Trauma/TSICU is mapped before SICU so Trauma SICU is no longer absorbed into ordinary SICU.
- MIT-LCP first-day SOFA and OASIS are named full_sofa_official_first_day and oasis_official_first_day; old names are retained as deprecated columns.

## Four Groups

| joint_exposure_4level | n | death_365d_main_n | death_365d_main_percent | readmission_90d_n | readmission_90d_percent | icu_readmission_365d_n | icu_readmission_365d_percent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1_no_primary_psych_no_delirium | 13909 | 1854.0 | 13.329 | 3216.0 | 23.122 | 1633.0 | 11.741 |
| 2_primary_psych_no_delirium | 5987 | 972.0 | 16.235 | 1723.0 | 28.779 | 807.0 | 13.479 |
| 3_no_primary_psych_delirium | 6067 | 1452.0 | 23.933 | 1548.0 | 25.515 | 829.0 | 13.664 |
| 4_primary_psych_delirium | 3495 | 827.0 | 23.662 | 1032.0 | 29.528 | 478.0 | 13.677 |

## Outcome Event Counts

- Primary-analysis one-year death events: 5,105
- Conservative-cohort 90-day same-system readmission events: 6,321
- Conservative-cohort one-year same-system ICU readmission events: 3,228

## Known Limitations

- Same-system readmission outcomes do not capture care outside the MIMIC hospital system.
- Exact patient-level administrative follow-up completeness at 90 or 365 days is not identifiable from shifted dates; conservative approximate-year cohort is used for primary readmission/ICU-readmission analyses.
- Same-day DOD is excluded from the main death definition and retained for sensitivity analysis.
- Hospice discharge is retained in the main analysis and reserved for sensitivity analyses.
- Non-neurologic SOFA uses zero-imputed components plus observed component count, per SAP v1.0.
- Chronic neurologic disease uses prespecified ICD families and should be described as a documented-code flag.
- A nonblocking time-stamp warning remains: some ICU intime values precede hospital admittime within 24 hours; these were retained because the base cohort definition is frozen.
- analysis_dataset_v1 and its original freeze log were not overwritten or deleted.

## Build Scripts And SHA256

| Script | SHA256 |
|---|---|
| `${PROJECT_DIR}\scripts\build_analysis_dataset_v1_1.py` | `D0F803D887B538FF65DCE5BC899B31B9496DFC5B8CA3CE069904557294831E9B` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__demographics__age.sql` | `6446475E5F82B29CBB9216C3B96C2E6BF96B1B95A18ACD18B9F5A8C39BFD045A` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__demographics__icustay_times.sql` | `27E5DE03899317ABC20FDA31D80CD150EA420196B85FCBCBB2C46F57BEFFAC0C` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__demographics__icustay_hourly.sql` | `32FBE831B27B8890EAA59C02A012A7726246DCDF3CA4079D52B39DD0DA5BB470` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__demographics__weight_durations.sql` | `A79A897E42A8B7685B1BCA53EBBC3C2AE4D40D3E4DE698E800CB3D6ACCB27E02` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__comorbidity__charlson.sql` | `3BFC8B070BC7347EE952E0AB97A3FE1D99B01C31DAA625BF0AB26685368EBA25` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__vitalsign.sql` | `A6CD57FA28E6F25C70286C08CC3C5F4807140B18D3F4BE40521806F0B46E6052` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__urine_output.sql` | `BD9FBD3B124B555AA77E79F786EC6A430CEEBEA62961DC164F21064A6B82ABDA` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__urine_output_rate.sql` | `044788AB5461A1B367EE77059DBB909311A6D992F250888D5E232EB86FF4F073` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__gcs.sql` | `9574C022CB02034DD2FCEE4E854F0DA436AF66F42BE4D3FBD2361F0A38A6DB7B` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__bg.sql` | `AF3594E2B8527D611CFD1EF51250E612D892C1F8CDCB78169803560F54879A39` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__chemistry.sql` | `1E1CFFEBA8F1DE191A15005D40E431784609812934EF1618857C0D586A68B5F1` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__complete_blood_count.sql` | `52A05D8202723B0C8FAB2E2B342E0E2871D0BDE6AB1D2C8D055A8DA9C8E064AB` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__blood_differential.sql` | `499B0CF70DDEB5ACD559C6D5A12914FFCDB8CEFF22638CAF1CFE4E050A23106D` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__coagulation.sql` | `243C050C36A0678E9153820AF6769CF8BC761430F65C702FBCDECB5BD809E9F8` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__enzyme.sql` | `D273DF8C0A0ACB683A7E1506D08189AA51ADDD53837BC67EF662119BF0E8A870` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__height.sql` | `C2BB70515C5F5DE2C89A22835F7F4482A6346D01189EF22D5BD82189086227D9` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__firstday__first_day_vitalsign.sql` | `9736E25B5232F3D91998B8044E17AA6E7210357F0088F17762DF7FEACBA64C98` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__firstday__first_day_urine_output.sql` | `DCBD817FF7A4517FA37D1B736D657C4D0A1007F0423575A0EE7CD8F58994DD1C` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__firstday__first_day_gcs.sql` | `FEA88A29CEDB688C6F45019F386203BF16FD7D0F49700F04CC80F15CA4CFC696` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__firstday__first_day_lab.sql` | `7B3BA012EBCF027CC689F30454C6CA828375C1F935788FA2336AAA251B37D7D2` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__firstday__first_day_bg.sql` | `5C55DB4F50D7A5E1EBDAD710F99438C009C9D90AD068EAFD48558C0793781C88` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__firstday__first_day_bg_art.sql` | `E4CD4C6792C674F1FAB8CB01491AFD0A1292E97A0EC6CA59318B9B36A5657AF1` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__firstday__first_day_height.sql` | `33DCD6CC4D3B04CFAC92CC68C14BE0947F75B70AAFFD0BBF8BF1C98DF71FA463` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__firstday__first_day_weight.sql` | `0EBADBE8091E893B01BB6E9315770D6DA6E08030BC443CDFC7BB9753BFC4B795` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__medication__dobutamine.sql` | `008E3474D6B8416682D96E12DB52661A7075AB246E83BA59FAB91ACB22D5EB02` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__medication__dopamine.sql` | `BD04CB75007D3D67CDA752E208684BCEAAD9350F8E0BE5AE59F15554C36AC761` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__medication__epinephrine.sql` | `528C98B71CB5508C486F51240BD44A2E84C3C80D25F05D860A3CD6AE6351D1A0` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__medication__norepinephrine.sql` | `683995554C66195335E3CE5E18CDAC99FC57875B4A2D187C1999CF75E168FB0A` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__medication__phenylephrine.sql` | `0B26C797575C61936A3E3117CC477771CCC5AD6A51E3DFA575E6EB90124A123B` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__medication__vasopressin.sql` | `6DA8BC8AEEF261B511966CEA829F5C93A280AAA5380B5850B08C034A148134AA` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__medication__milrinone.sql` | `D8BFD0FA15689EF64BEAB55CDC8EE6D97D55B7BDFF69E89BF0125D40D790A3C0` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__medication__vasoactive_agent.sql` | `B4B9FF3A6185C20EAF3FEDFE85410BC27E2BBB4D602018CD0FC02F07B4351E66` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__medication__norepinephrine_equivalent_dose.sql` | `1027B07C71A670E61891CB2C62D1D50DCD84A7AF86FCC2E1D135EE655EB5BF3F` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__treatment__rrt.sql` | `C6B336FC12CF510B7A40E58530D59CDEA9570093E923734E6B178D828C329E0A` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__treatment__crrt.sql` | `4CCFA6038F4D8EC532C496C403DE17E0765D1DDBA4CFB377B9FE2614CDB3FCB8` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__firstday__first_day_rrt.sql` | `6CAC72E23E504E7B8468443FE4156836729A49360D71E8E22E7B4369EB6059E6` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__ventilator_setting.sql` | `2B60F634A308F93E39BE25705D5AC330A17539C5AC8B1D48CEEB81FA8F180E13` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__measurement__oxygen_delivery.sql` | `1BD08C636A71331132C580AA3C61A9F1877661AB2B82145C03675306ECE84957` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__treatment__ventilation.sql` | `F92C414880A237D89AB723AE1B4481DB7136D4555D7F074E76AF8ED32ADBEA83` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__firstday__first_day_sofa.sql` | `F0B776FBED7D0CE68576F1E80C4C26E3F7D3F63DD2A82EFB95C7B3E875AB4CB3` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__score__oasis.sql` | `B338195B0B40426C92D8E422D9ED4CC05794F485265AC8B6483EF486EB05A343` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__score__sofa.sql` | `27494138AF036B1E989267B06D9B69CE3FDF3C2994ACA1B4284FB7294D254272` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__medication__antibiotic.sql` | `2234E3B7267D4327026091AFCEC410AE12E3ACCF45A7844F46B1CCAC71009617` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__sepsis__suspicion_of_infection.sql` | `17233D2C0F6178F746543014613EB624AFA594467EAF06E535103F2B7F274921` |
| `${PROJECT_DIR}\scripts\derived_concepts\duckdb_adapted\mimic-iv__concepts_duckdb__sepsis__sepsis3.sql` | `92149192B8F8D76894150E6DFDDD6FF5291E02C33033AFD861129AB35BD33A63` |
| `${PROJECT_DIR}\scripts\derived_concepts\project_specific\non_neurologic_sofa_0_24h.sql` | `685B17798A4C01F3EB36FB65DF7D80E7B6A72455955CFB0AC61E2477AB80215D` |
| `${PROJECT_DIR}\scripts\derived_concepts\project_specific\non_neurologic_sofa_0_6h.sql` | `47973DECEBD162456D33AB65C9D025832296453B926D47558ADF261A91D25125` |

## QC Output Files

| File | SHA256 |
|---|---|
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_row_count_qc.csv` | `1EA7EE4ABBAFF373AB165457F73C0CEA9081967121098BCE379E431FF86D4AE7` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_key_qc.csv` | `823068B2D32628C8961FE9B0FFA35D92BE67C3D803ABD983B7E9CA57436E6CD6` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_missingness.csv` | `1CFA3F99700D203A7315CE025C75A37031139998AE1F22F8BC90792DB8596F03` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_range_qc.csv` | `17E03F3A439000A27A1570B37350B6532C847BB2F8E550A6D566CED4DEE49B2A` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_time_logic_qc.csv` | `85A1E11C2983A6BCE77BF8E15634E88DAF461EFF7E059635E60F41937C286103` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_time_logic_warning_summary.csv` | `3183887991B402433791595B50D8D10F65283912B623DB40F298E4BAD0314003` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_category_levels.csv` | `E636148D33F62B56092196E25CBA29650E7B11872F4B68D1CC96B22B414F73E7` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_cohort_counts.csv` | `322264B41F280E66E9887007774537A2814B02E9D2E097BC3E0E9672D83C7111` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_four_group_counts.csv` | `F1305CE50DF3109C63CD1DD8F8C9FEA5450186CAC5D893680A24AA40E161B290` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_outcome_counts.csv` | `9A9521CE53AE4A27EF155959F8A8795BCA9D29A6E7E1E135FFD083D3DDA44638` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_competing_risk_status_counts.csv` | `341801304AA9B10A8EB77701EF715AF9E7F869B0DCC9643ADC103C168801E7E1` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_competing_risk_time_qc.csv` | `31AAC1C479159DB8360AD9F955A19C08BDCA04AE117CE3C420AA8FF917CF74C2` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_icu_type_mapping_v1_to_v1_1.csv` | `5C61397C7F5B5C9B3BCCE76C6DB287C8432854F70EADC7C596FB274FCB498C9C` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_charlson_hotfix_qc.csv` | `B460B8AE461B435D12DF24230470C143C4D0664422D5EF01B56C57707632DA22` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_model_variable_hotfix_qc.csv` | `27015B6CCA5F1E58FC708D48C73022257B4E2E6CE1325B5B2381B8CD46653455` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_derived_concept_qc.csv` | `86E942C993E32B6503226DD8235B3D8361BE365B6C0AAE65D3C6C14E45832A27` |
| `${PROJECT_DIR}\analysis\qc_v1_1\analysis_dataset_discrepancy_report.md` | `39F97C747BFF2A5A48E03CC13AB04FEB7B4C7CBB14C0DA1D74D957C7F97A63E7` |
