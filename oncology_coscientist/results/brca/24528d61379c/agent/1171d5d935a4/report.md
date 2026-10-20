<!-- agent_run_sha256: 628211b5b8240945b62402ef83642d27b1fe8164134e32d359eadb89eb7743c6 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The cohort consists of 1071 patients, with 1069 having expression data available. The missingness analysis indicates that all patients have complete data for age and sex, with missingness in stage (19 patients), mut_TP53 (18 patients), mut_PIK3CA (18 patients), mut_CDH1 (18 patients), mut_GATA3 (18 patients), mut_MAP3K1 (18 patients), and mut_KMT2C (18 patients).

## Models and metrics
- cox/clinical: harrell_c 0.708, uno_c 0.714, auc_12m 0.702, auc_24m 0.722, auc_36m 0.705, auc_mean 0.707, integrated_brier_6_36m 0.028, HR[age] 1.02 [1.01, 1.03] p=0.0002, HR[mut_CDH1] 1.06 [0.69, 1.65] p=0.7800, HR[mut_GATA3] 1.33 [0.86, 2.06] p=0.1934, HR[mut_KMT2C] 1.23 [0.75, 2.01] p=0.4111, HR[mut_MAP3K1] 0.97 [0.55, 1.71] p=0.9106, HR[mut_PIK3CA] 1.06 [0.77, 1.45] p=0.7376, HR[mut_TP53] 1.22 [0.88, 1.68] p=0.2277, HR[sex_Male] 1.05 [0.25, 4.50] p=0.9460, HR[stage_II] 1.03 [0.74, 1.42] p=0.8693, HR[stage_III] 1.51 [1.04, 2.19] p=0.0306, HR[stage_IV] 6.55 [3.19, 13.48] p=0.0000, reference_levels: {"sex": "Female", "stage": "I"}
- rsf/clinical: harrell_c 0.674, uno_c 0.679, auc_12m 0.624, auc_24m 0.664, auc_36m 0.657, auc_mean 0.655, integrated_brier_6_36m 0.027
- cox/clinical_expression: harrell_c 0.615, uno_c 0.585, auc_12m 0.394, auc_24m 0.570, auc_36m 0.656, auc_mean 0.618, integrated_brier_6_36m 0.029
- rsf/clinical_expression: harrell_c 0.624, uno_c 0.452, auc_12m 0.569, auc_24m 0.605, auc_36m 0.631, auc_mean 0.621

## Checks and abstentions
- split_integrity: PASS
- min_events: PASS
- leakage: PASS
- proportional_hazards: PASS
- convergence: PASS

## Limitations
The cohort analysis is based on 1071 patients, with 1069 having expression data available. The missingness analysis indicates that all patients have complete data for age and sex, with missingness in stage (19 patients), mut_TP53 (18 patients), mut_PIK3CA (18 patients), mut_CDH1 (18 patients), mut_GATA3 (18 patients), mut_MAP3K1 (18 patients), and mut_KMT2C (18 patients). The data was checked for integrity, minimum events, leakage, proportional hazards, and convergence, all of which passed the checks. The models passed all checks ensuring integrity, leakage, proportional hazards, and convergence. The clinical models (cox/clinical, rsf/clinical) and clinical
