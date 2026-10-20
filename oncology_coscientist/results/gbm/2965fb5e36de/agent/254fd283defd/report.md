<!-- agent_run_sha256: 4d311e14fcb2a83b5382178f9c5b0737659c579bfa624f4152f2e6055f1eac7b -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The cohort consists of 580 patients, with 152 having expression data available. The missingness analysis reveals that age, sex, and genetic mutations (TP53, PTEN, EGFR, IDH1, NF1, ATRX) have a missingness rate of 48.97%, while the missingness for OS data is 4.00%. Additionally, 194 patients have no primary sample, and 4 patients have missing OS data. The cohort is split into training and testing sets with 406 patients in the training set and 174 in the testing set. The covariates check indicates a failure, and the proportional hazards and convergence checks also failed.

## Models and metrics
- cox/clinical: harrell_c = abstained (reason: no covariates survived the missingness filter), auc_12m = abstained (reason: no covariates survived the missingness filter), auc_24m = abstained (reason: no covariates survived the missingness filter), auc_36m = abstained (reason: no covariates survived the missingness filter), integrated_brier_6_36m = abstained (reason: no covariates survived the missingness filter)
- rsf/clinical: harrell_c = abstained (reason: no covariates survived the missingness filter), auc_12m = abstained (reason: no covariates survived the missingness filter), auc_24m = abstained (reason: no covariates survived the missingness filter), auc_36m = abstained (reason: no covariates survived the missingness filter), integrated_brier_6_36m = abstained (reason: no covariates survived the missingness filter)
- cox/clinical_expression: harrell_c = abstained (reason: no covariates survived the missingness filter), auc_12m = abstained (reason: no covariates survived the missingness filter), auc_24m = abstained (reason: no covariates survived the missingness filter), auc_36m = abstained (reason: no covariates survived the missingness filter), integrated_brier_6_36m = abstained (reason: no covariates survived the missingness filter)
- rsf/clinical_expression: harrell_c = abstained (reason: no covariates survived the missingness filter), auc_12m = abstained (reason: no covariates survived the missingness filter), auc_24m = abstained (reason: no covariates survived the missingness filter), auc_36m = abstained (reason: no covariates survived the missingness filter), integrated_brier_6_36m = abstained (reason: no covariates survived the missingness filter)

## Checks and abstentions
- cox/clinical: cox/clinical.abstained = true (covariates failed; proportional_hazards failed; convergence failed)
- cox/clinical_expression: cox/clinical_expression.abstained = true (covariates failed; convergence failed)
- rsf/clinical: rsf/clinical.abstained = true (covariates failed)
- rsf/clinical_expression: rsf/clinical_expression.abstained = true (covariates failed)

## Limitations
- High missingness rates for age, sex, and genetic mutations (48.97% each).
- Missing OS data for 4 patients.
- No primary sample for 194 patients.
- Failure in covariates, proportional hazards, and convergence checks.

[PDQ:pdq_adult_brain_treatment#36] Glioblastoma (grade IV) grows and spreads very quickly, and the tumor cells look very different from normal cells. It is also called glioblastoma multiforme. The prognosis and treatment options for glioblastoma depend on various factors including the presence of genetic mutations and the overall health of the patient.
