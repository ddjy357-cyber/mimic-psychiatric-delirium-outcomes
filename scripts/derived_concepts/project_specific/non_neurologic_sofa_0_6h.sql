-- Project-specific non-neurologic SOFA candidate, 0-6h.
-- Depends on MIT-LCP mimic-code DuckDB concept: mimiciv_derived.sofa.
-- CNS/GCS is intentionally excluded.
-- This script is for technical feasibility/formal build preparation only;
-- SAP must decide the final missing-component handling strategy.

drop table if exists mimiciv_derived.non_neurologic_sofa_0_6h;
create table mimiciv_derived.non_neurologic_sofa_0_6h as
select
    stay_id,
    max(respiration) as respiratory_score,
    max(coagulation) as coagulation_score,
    max(liver) as liver_score,
    max(cardiovascular) as cardiovascular_score,
    max(renal) as renal_score,
    case when max(respiration) is not null then 1 else 0 end as respiratory_observed,
    case when max(coagulation) is not null then 1 else 0 end as coagulation_observed,
    case when max(liver) is not null then 1 else 0 end as liver_observed,
    case when max(cardiovascular) is not null then 1 else 0 end as cardiovascular_observed,
    case when max(renal) is not null then 1 else 0 end as renal_observed,
    (case when max(respiration) is not null then 1 else 0 end)
      + (case when max(coagulation) is not null then 1 else 0 end)
      + (case when max(liver) is not null then 1 else 0 end)
      + (case when max(cardiovascular) is not null then 1 else 0 end)
      + (case when max(renal) is not null then 1 else 0 end) as observed_components_n,
    coalesce(max(respiration), 0)
      + coalesce(max(coagulation), 0)
      + coalesce(max(liver), 0)
      + coalesce(max(cardiovascular), 0)
      + coalesce(max(renal), 0) as nonneurologic_sofa_zero_imputed,
    case
        when max(respiration) is not null
         and max(coagulation) is not null
         and max(liver) is not null
         and max(cardiovascular) is not null
         and max(renal) is not null
        then max(respiration) + max(coagulation) + max(liver) + max(cardiovascular) + max(renal)
        else null
    end as nonneurologic_sofa_complete_case,
    case
        when max(respiration) is not null
         and max(coagulation) is not null
         and max(liver) is not null
         and max(cardiovascular) is not null
         and max(renal) is not null
        then 1 else 0
    end as complete_case_flag
from mimiciv_derived.sofa
where hr between 0 and 6
group by stay_id;
