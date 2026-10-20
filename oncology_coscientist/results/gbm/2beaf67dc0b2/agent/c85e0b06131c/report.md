<!-- agent_run_sha256: 3f63ce1eddfcc4f3c75fd1a2749a0234ca23058cdbf7d68f24319050dd5ab788 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The cohort consists of 580 patients, with 152 having expression data available. The missingness analysis reveals that age, sex, and genetic mutations (TP53, PTEN, EGFR, IDH1, NF1, ATRX) have a missingness rate of 48.97%, while the missingness for OS data is 4.00%. Additionally, 194 patients have no primary sample, and 4 patients have missing OS data. The cohort is split into training and testing sets with 406 patients in the training set and 174 in the testing set.

## Models and metrics
- cox/clinical: abstained (covariates failed; proportional_hazards failed; convergence failed)
- cox/clinical_expression: abstained (covariates failed; convergence failed)
- rsf/clinical: abstained (covariates failed)
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
