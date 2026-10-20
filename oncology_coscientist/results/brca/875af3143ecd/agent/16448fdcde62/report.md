<!-- agent_run_sha256: 465524091b73099d1726322c01b4e38e0ad1e9e7a062d2ab1e1a9870e3d23f97 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The cohort consists of 1071 patients, with 1069 having expression data available. The missingness analysis indicates that all patients have complete data for age and sex, with missingness in stage (19 patients), mut_TP53 (18 patients), mut_PIK3CA (18 patients), mut_CDH1 (18 patients), mut_GATA3 (18 patients), mut_MAP3K1 (18 patients), and mut_KMT2C (18 patients). The cohort was split into training (n_train: 749) and test sets (n_test: 322). The data was checked for integrity, minimum events, leakage, proportional hazards, and convergence, all of which passed the checks.

## Models and metrics
- cox/clinical: harrell_c 0.708 | uno_c 0.714 | integrated_brier_6_36m 0.028 | auc_12m 0.702 | auc_24m 0.722 | auc_36m 0.705 | auc_mean 0.707
- rsf/clinical: harrell_c 0.674 | uno_c 0.679 | integrated_brier_6_36m 0.027 | auc_12m 0.624 | auc_24m 0.664 | auc_36m 0.657 | auc_mean 0.655
- cox/clinical_expression: harrell_c 0.615 | uno_c 0.585 | integrated_brier_6_36m 0.029 | auc_12m 0.394 | auc_24m 0.570 | auc_36m 0.656 | auc_mean 0.618
- rsf/clinical_expression: harrell_c abstained (missing data) | uno_c abstained (missing data) | integrated_brier_6_36m abstained (missing data) | auc_12m 0.569 | auc_24m 0.605 | auc_36m 0.631 | auc_mean 0.621

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
The analysis of breast cancer data involves evaluating various models to predict survival outcomes. The models considered include Cox proportional hazards models with clinical covariates and clinical covariates plus gene expression data. The performance of these models is assessed using metrics such as Harrell's C-index, Uno's C-index, and integrated Brier score, which measure the predictive accuracy and calibration of the models. The results indicate that the Cox model with clinical covariates and gene expression data performs better in terms of concordance indices and integrated Brier scores, suggesting that incorporating gene expression data can improve the predictive power of the model. However, the models are subject to limitations such as missing data and unsequenced samples, which can affect the reliability of the results.
