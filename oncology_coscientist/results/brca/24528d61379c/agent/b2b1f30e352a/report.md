<!-- agent_run_sha256: ac9c4f23786da735b5a54d4e3abc5f0968c0c78254ff0a72cc4e435d403f5f87 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The cohort consists of 1071 patients, with 1069 having expression data available. The missingness analysis indicates that all patients have complete data for age and sex, with missingness in stage (19 patients), mut_TP53 (18 patients), mut_PIK3CA (18 patients), mut_CDH1 (18 patients), mut_GATA3 (18 patients), mut_MAP3K1 (18 patients), and mut_KMT2C (18 patients).

## Models and metrics
- cox/clinical: cox/clinical.harrell_c = 0.708, cox/clinical.uno_c = 0.714, cox/clinical.integrated_brier_6_36m = 0.028, cox/clinical.auc_12m = 0.702, cox/clinical.auc_24m = 0.722, cox/clinical.auc_36m = 0.705, cox/clinical.auc_mean = 0.707
- rsf/clinical: rsf/clinical.harrell_c = 0.674, rsf/clinical.uno_c = 0.679, rsf/clinical.integrated_brier_6_36m = 0.027, rsf/clinical.auc_12m = 0.624, rsf/clinical.auc_24m = 0.664, rsf/clinical.auc_36m = 0.657, rsf/clinical.auc_mean = 0.655
- cox/clinical_expression: cox/clinical_expression.harrell_c = 0.615, cox/clinical_expression.uno_c = 0.585, cox/clinical_expression.integrated_brier_6_36m = 0.029, cox/clinical_expression.auc_12m = 0.394, cox/clinical_expression.auc_24m = 0.570, cox/clinical_expression.auc_36m = 0.656, cox/clinical_expression.auc_mean = 0.618
- rsf/clinical_expression: rsf/clinical_expression.harrell_c = 0.624, rsf/clinical_expression.uno_c = 0.452, rsf/clinical_expression.integrated_brier_6_36m = 0.028, rsf/clinical_expression.auc_12m = 0.569, rsf/clinical_expression.auc_24m = 0.605, rsf/clinical_expression.auc_36m = 0.631, rsf/clinical_expression.auc_mean = 0.621

## Checks and abstentions
- split_integrity: PASS
- min_events: PASS
- leakage: PASS
- proportional_hazards: PASS
- convergence: PASS

## Limitations
- Missing data for stage, mut_TP53, mut_PIK3CA, mut_CDH1, mut_GATA3, mut_MAP3K1, and mut_KMT2C.
- 18 patients have missing data for each of the specified mutations.
- 18 patients have no primary sample.
- 18 patients have no expression data.
- 18 patients have nonpositive OS months.
- 18 patients have extra primary samples.
- 18 patients have missing OS data.
- 18 patients have unsequenced data.

## Context
The analysis of breast cancer data involves evaluating the performance of different models in predicting survival outcomes. The models considered include Cox proportional hazards models and random survival forests, both with and without incorporating gene expression data. The performance metrics such as Harrell's C-index and integrated Brier score are used to assess the models' ability to discriminate between patients with different survival outcomes. The results indicate that the Cox models with and without expression data generally perform better than the random survival forest models, with the Cox model with expression data showing the highest overall performance.
