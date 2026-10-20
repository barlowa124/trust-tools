<!-- agent_run_sha256: 3a9fab0713a31874c1b7da4c47439de943692139dc6800783fe5c193182755a2 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The BRCA cohort consists of 1071 patients, with 1069 patients having expression data available and 18 patients lacking sequencing data. The cohort is divided into a training set of 749 patients and a test set of 322 patients. The missingness in key variables such as age and sex is zero, indicating complete data for these variables. However, there is a notable amount of missing data for certain mutation types and disease stage, with 19 patients missing stage information and 18 patients missing data for each of the listed mutations (TP53, PIK3CA, CDH1, GATA3, MAP3K1, and KMT2C), representing approximately 1.77% and 1.68% of the total cohort, respectively. Additionally, 13 patients have non-positive overall survival months, which may require further investigation.

- Missing data for stage (19 patients, 1.77%)
- Missing data for mutations (TP53, PIK3CA, CDH1, GATA3, MAP3K1, KMT2C) (18 patients each, 1.68%)
- Non-positive overall survival months (13 patients)

## Models and metrics
- cox/clinical: harrell_c 0.708 | uno_c 0.714 | integrated_brier_6_36m 0.028 | auc_12m 0.702 | auc_24m 0.722 | auc_36m 0.705 | auc_mean 0.707
- rsf/clinical: harrell_c 0.674 | uno_c 0.679 | integrated_brier_6_36m 0.027 | auc_12m 0.624 | auc_24m 0.664 | auc_36m 0.657 | auc_mean 0.655
- cox/clinical_expression: harrell_c 0.615 | uno_c 0.585 | integrated_brier_6_36m 0.029 | auc_12m 0.394 | auc_24m 0.570 | auc_36m 0.656 | auc_mean 0.618
- rsf/clinical_expression: harrell_c 0.624 | uno_c 0.452 | integrated_brier_6_36m 0.028 | auc_12m 0.569 | auc_24m 0.605 | auc_36m 0.631 | auc_mean 0.621

## Checks and abstentions
- split_integrity: PASS
- min_events: PASS
- leakage: PASS
- proportional_hazards: PASS
- convergence: PASS

## Limitations
- Missing data for stage (19 patients, 1.77%)
- Missing data for mutations (TP53, PIK3CA, CDH1, GATA3, MAP3K1, KMT2C) (18 patients each, 1.68%)
- Non-positive overall survival months (13 patients)
