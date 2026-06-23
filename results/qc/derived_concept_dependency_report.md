# Derived Concept Dependency Report

Official MIT-LCP mimic-code commit: `57069783095e7770e66ea97da264c0200078ddbf`.

Official DuckDB SQL files were copied without changing their body. They were executed in an in-memory DuckDB session using read-only schema aliases to the local MIMIC-IV database.

                       concept  can_directly_build build_difficulty  recommended_build_order missing_tables_or_concepts
                      Charlson                True              Low                        1              none_detected
             vasoactive agents                True              Low                        2              none_detected
norepinephrine equivalent dose                True              Low                        3              none_detected
                           RRT                True              Low                        4              none_detected
                          CRRT                True              Low                        5              none_detected
                   ventilation                True           Medium                        6              none_detected
                first-day SOFA                True             High                        7              none_detected
                         OASIS                True           Medium                        8              none_detected
                      Sepsis-3                True             High                        9              none_detected

Build status for all executed source files:

                 derived_table build_status  row_count  elapsed_seconds error_or_note
                           age        built     546028             0.03              
                 icustay_times        built      94458             0.16              
                icustay_hourly        built   10485609             0.58              
              weight_durations        built     401850             1.10              
                      charlson        built     546028            11.36              
                     vitalsign        built   13519533             5.04              
                  urine_output        built    4127634             0.30              
             urine_output_rate        built    4126485             3.22              
                           gcs        built    2217787             1.64              
                            bg        built     697418             6.88              
                     chemistry        built    4976408             3.07              
          complete_blood_count        built    4377900             2.77              
            blood_differential        built    4154226             3.69              
                   coagulation        built    1991167             1.18              
                        enzyme        built    2187060             2.40              
                        height        built      43342             0.49              
           first_day_vitalsign        built      94458             3.12              
        first_day_urine_output        built      94458             0.09              
                 first_day_gcs        built      94458             0.26              
                 first_day_lab        built      94458             2.04              
                  first_day_bg        built      94458             0.46              
              first_day_bg_art        built      94458             0.30              
              first_day_height        built      94458             0.04              
              first_day_weight        built      94458             0.05              
                    dobutamine        built      10264             0.44              
                      dopamine        built      18085             0.04              
                   epinephrine        built      31495             0.04              
                norepinephrine        built     459800             0.40              
                 phenylephrine        built     209376             0.28              
                   vasopressin        built      37163             0.18              
                     milrinone        built      10668             0.02              
              vasoactive_agent        built     839543             0.63              
norepinephrine_equivalent_dose        built     783613             0.03              
                           rrt        built    4098630             5.44              
                          crrt        built     475214             1.68              
                 first_day_rrt        built      94458             0.25              
            ventilator_setting        built    1377514             2.73              
               oxygen_delivery        built     794232             4.56              
                   ventilation        built     144812             2.84              
                first_day_sofa        built      94458             0.44              
                         oasis        built      94458             4.81              
                          sofa        built    8219121            32.47              
                    antibiotic        built     949901             7.27              
        suspicion_of_infection        built     949901           619.48              
                       sepsis3        built      41295             5.28              
