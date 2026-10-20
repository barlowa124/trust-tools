<!-- agent_run_sha256: fb687d82c23ac9c5a56319feb566e156b061943a9ed22794fcccf7e8baf1c2a4 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The cohort consists of 1071 patients, with 1069 having expression data available. The missingness analysis indicates that all patients have complete data for age and sex, with missingness in stage (19 patients), mut_TP53 (18 patients), mut_PIK3CA (18 patients), mut_CDH1 (18 patients), mut_GATA3 (18 patients), mut_MAP3K1 (18 patients), and mut_KMT2C (18 patients).

## Models and metrics
The models and metrics of interest include the clinical Cox model, the clinical random survival forest (RSF) model, the clinical expression Cox model, and the clinical expression RSF model. The key metrics are the Harrell C-index, Uno C-index, AUC at 12 months, AUC at 24 months, AUC at 36 months, and the Integrated Brier Score over 6 to 36 months.

## Checks and abstentions
All checks passed, ensuring integrity, leakage, proportional hazards, and convergence. The clinical models (cox/clinical, rsf/clinical) and clinical expression models (cox/clinical_expression, rsf/clinical_expression) are the focus of our discussion. The metrics of interest are the Harrell C-index, Uno C-index, AUC at 12 months, AUC at 24 months, AUC at 36 months, and the Integrated Brier Score over 6 to 36 months.

## Limitations
The cohort analysis is based on 1071 patients, with 18 patients having missing data for each of the specified mutations (mut_TP53, mut_PIK3CA, mut_CDH1, mut_GATA3, mut_MAP3K1, and mut_KMT2C). Additionally, 18 patients have no primary sample, 18 have no expression data, 18 have nonpositive OS months, and 18 have unsequenced data. These limitations may affect the robustness of the results.
