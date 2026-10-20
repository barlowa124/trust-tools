<!-- agent_run_sha256: 885c87dd239c20ff64cf3f084320134ac7e4c3bba3bb61859679cf35f682d9b2 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The cohort consists of 580 patients, with 152 having expression data available. The missingness analysis reveals that age, sex, and genetic mutations (TP53, PTEN, EGFR, IDH1, NF1, ATRX) have a missingness rate of 48.97%, while the missingness for OS (overall survival) data is 4.00%. Additionally, 194 patients have no primary sample, and 4 patients have missing OS data. The cohort is split into training and testing sets with 406 patients in the training set and 174 in the testing set. The covariates check indicates a failure, and the proportional hazards and convergence checks also failed.

## Models and metrics
- cox/clinical: harrell_c abstained (reason: convergence failed), auc_12m abstained (reason: convergence failed), auc_24m abstained (reason: convergence failed), auc_36m abstained (reason: convergence failed), integrated_brier_6_36m abstained (reason: convergence failed)
- rsf/clinical: harrell_c abstained (reason: convergence failed), auc_12m abstained (reason: convergence failed), auc_24m abstained (reason: convergence failed), auc_36m abstained (reason: convergence failed), integrated_brier_6_36m abstained (reason: convergence failed)
- cox/clinical_expression: harrell_c abstained (reason: convergence failed), auc_12m abstained (reason: convergence failed), auc_24m abstained (reason: convergence failed), auc_36m abstained (reason: convergence failed), integrated_brier_6_36m abstained (reason: convergence failed)
- rsf/clinical_expression: harrell_c abstained (reason: convergence failed), auc_12m abstained (reason: convergence failed), auc_24m abstained (reason: convergence failed), auc_36m abstained (reason: convergence failed), integrated_brier_6_36m abstained (reason: convergence failed)

## Checks and abstentions
- cox/clinical: cox/clinical.abstained = true (covariates failed; proportional_hazards failed; convergence failed)
- cox/clinical_expression: cox/clinical_expression.abstained = true (covariates failed; convergence failed)
- rsf/clinical: rsf/clinical.abstained = true (covariates failed)
- rsf/clinical_expression: rsf/clinical_expression.abstained = true (covariates failed)

## Limitations
Data Concerns:
- High missingness rates for age, sex, and genetic mutations (48.97% each).
- Missing OS data for 4 patients.
- No primary sample for 194 patients.
- Failure in covariates, proportional hazards, and convergence checks.

The analysis plan focuses on evaluating the Cox proportional hazards model and random survival forest models with and without clinical covariates. However, the covariates check, proportional hazards, and convergence checks all failed, leading to the abstention of all model-specific metrics. This failure indicates that the models could not be reliably estimated due to the high missingness rates and other underlying issues in the data.
