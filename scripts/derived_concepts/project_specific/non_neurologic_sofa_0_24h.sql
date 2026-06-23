-- Project-specific non-neurologic SOFA candidate, 0-24h.
-- Depends on MIT-LCP mimic-code DuckDB concept: mimiciv_derived.first_day_sofa.
-- CNS/GCS is intentionally excluded.
-- This script is for technical feasibility/formal build preparation only;
-- SAP must decide the final missing-component handling strategy.

drop table if exists mimiciv_derived.non_neurologic_sofa_0_24h;
create table mimiciv_derived.non_neurologic_sofa_0_24h as
select
    stay_id,
    respiration as respiratory_score,
    coagulation as coagulation_score,
    liver as liver_score,
    cardiovascular as cardiovascular_score,
    renal as renal_score,
    case when respiration is not null then 1 else 0 end as respiratory_observed,
    case when coagulation is not null then 1 else 0 end as coagulation_observed,
    case when liver is not null then 1 else 0 end as liver_observed,
    case when cardiovascular is not null then 1 else 0 end as cardiovascular_observed,
    case when renal is not null then 1 else 0 end as renal_observed,
    (case when respiration is not null then 1 else 0 end)
      + (case when coagulation is not null then 1 else 0 end)
      + (case when liver is not null then 1 else 0 end)
      + (case when cardiovascular is not null then 1 else 0 end)
      + (case when renal is not null then 1 else 0 end) as observed_components_n,
    coalesce(respiration, 0)
      + coalesce(coagulation, 0)
      + coalesce(liver, 0)
      + coalesce(cardiovascular, 0)
      + coalesce(renal, 0) as nonneurologic_sofa_zero_imputed,
    case
        when respiration is not null
         and coagulation is not null
         and liver is not null
         and cardiovascular is not null
         and renal is not null
        then respiration + coagulation + liver + cardiovascular + renal
        else null
    end as nonneurologic_sofa_complete_case,
    case
        when respiration is not null
         and coagulation is not null
         and liver is not null
         and cardiovascular is not null
         and renal is not null
        then 1 else 0
    end as complete_case_flag
from mimiciv_derived.first_day_sofa;
