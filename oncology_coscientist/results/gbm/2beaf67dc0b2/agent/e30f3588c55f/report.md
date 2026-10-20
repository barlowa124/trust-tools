<!-- agent_run_sha256: c6e3714fa6bb64512b136227fa5f4cd3626b7665dece209be851574c58e3d183 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The cohort consists of 580 patients, with 152 having expression data available. The missingness analysis reveals that age, sex, and genetic mutations (TP53, PTEN, EGFR, IDH1, NF1, ATRX) have a missingness rate of 48.97%, while the missingness for OS (overall survival) data is 4.00%. Additionally, 194 patients have no primary sample, and 4 patients have missing OS data. The cohort is split into training and testing sets with 406 patients in the training set and 174 in the testing set. The covariates check indicates a failure, and the proportional hazards and convergence checks also failed.

## Models and metrics
- cox/clinical: abstained (covariates failed; proportional_hazards failed; convergence failed)
- rsf/clinical: abstained (covariates failed)
- cox/clinical_expression: abstained (covariates failed; convergence failed)
- rsf/clinical_expression: abstained (covariates failed)

## Checks and abstentions
- split_integrity: PASS
- min_events: PASS
- covariates: FAIL — no covariates survived the missingness filter (affected models abstained)
- proportional_hazards: FAIL — clinical Cox model did not fit (affected models abstained)
- convergence: FAIL — {"converged": false} (affected models abstained)

## Limitations
- High missingness rates for age, sex, and genetic mutations (48.97% each).
- Missing OS data for 4 patients.
- No primary sample for 194 patients.
- Failure in covariates, proportional hazards, and convergence checks.
- The cohort is split into training and testing sets with 406 patients in the training set and 174 in the testing set, which may affect model performance and generalizability.
- The models abstained due to the failure in covariates, proportional hazards, and convergence checks, indicating that the models could not be properly trained or validated.
