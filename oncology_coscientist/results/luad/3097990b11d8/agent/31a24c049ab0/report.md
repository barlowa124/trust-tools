<!-- agent_run_sha256: cdb62b47fb4f3433482cca4a3fd14a526fbf05b762d66d315f4a7ac80ff3f321 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The cohort consists of 501 patients, with 497 having their expression data available. The missingness analysis reveals that the 'age' variable has the highest proportion of missing values at 2%, while 'sex', 'stage', 'mut_TP53', 'mut_KRAS', 'mut_EGFR', 'mut_STK11', and 'mut_KEAP1' variables have no missing values. The 'stage' variable has 2 missing values, which constitute 0.004 of the total dataset. No patients had missing 'os' (overall survival) data, but 61 patients had missing 'os' months data, which could introduce bias if not handled appropriately.

## Models and metrics
- cox/clinical: cox/clinical.harrell_c = 0.647, cox/clinical.uno_c = 0.640, cox/clinical.integrated_brier_6_36m = 0.153, cox/clinical.auc_12m = 0.649, cox/clinical.auc_24m = 0.691, cox/clinical.auc_36m = 0.694, cox/clinical.auc_mean = 0.681
- rsf/clinical: rsf/clinical.harrell_c = 0.639, rsf/clinical.uno_c = 0.639, rsf/clinical.integrated_brier_6_36m = 0.153, rsf/clinical.auc_12m = 0.604, rsf/clinical.auc_24m = 0.675, rsf/clinical.auc_36m = 0.695, rsf/clinical.auc_mean = 0.663
- cox/clinical_expression: cox/clinical_expression.harrell_c = 0.643, cox/clinical_expression.uno_c = 0.632, cox/clinical_expression.integrated_brier_6_36m = 0.157, cox/clinical_expression.auc_12m = 0.711, cox/clinical_expression.auc_24m = 0.666, cox/clinical_expression.auc_36m = 0.628, cox/clinical_expression.auc_mean = 0.664
- rsf/clinical_expression: rsf/clinical_expression.harrell_c = 0.632, rsf/clinical_expression.uno_c = 0.615, rsf/clinical_expression.integrated_brier_6_36m = 0.153, rsf/clinical_expression.auc_12m = 0.671, rsf/clinical_expression.auc_24m = 0.672, rsf/clinical_expression.auc_36m = 0.609, rsf/clinical_expression.auc_mean = 0.649

## Checks and abstentions
- split_integrity: PASS
- min_events: PASS
- leakage: PASS
- proportional_hazards: PASS
- convergence: PASS

## Limitations
The cohort summary indicates that the 'age' variable has a high proportion of missing values at 2%, which could introduce bias if not handled appropriately. Additionally, the 'stage' variable has a small number of missing values, which might require further investigation to understand the reasons for these missing values and how they could affect the study's outcomes. The presence of missing 'os' months data in 61 patients is a concern that should be addressed to ensure the integrity of the survival analysis.
