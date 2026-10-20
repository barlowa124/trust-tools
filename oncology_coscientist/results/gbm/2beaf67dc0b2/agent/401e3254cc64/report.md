<!-- agent_run_sha256: cb627adc17ba914a3bdf90e003825b8e5f4b5b2fee2af31284cd51c2fcf013b5 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The cohort consists of 580 patients with glioblastoma, of which 152 have expression data available and 194 are unsequenced. The cohort is split into a training set of 406 patients and a test set of 174 patients. Missingness in key variables such as age and sex is high, with 284 patients missing data for each, representing a fraction of 0.4897. Similarly, mutations in TP53, PTEN, EGFR, IDH1, NF1, and ATRX are missing for 194 patients, each with a fraction of 0.3345.

## Models and metrics
- cox/clinical: abstained (covariates failed; proportional_hazards failed; convergence failed)
- rsf/clinical: abstained (covariates failed)

## Checks and abstentions
- split_integrity: PASS
- min_events: PASS
- covariates: FAIL — no covariates survived the missingness filter (affected models abstained)
- proportional_hazards: FAIL — clinical Cox model did not fit (affected models abstained)
- convergence: FAIL — {"converged": false} (affected models abstained)

## Limitations
- High missingness in age and sex (284 missing, fraction 0.4897)
- High missingness in mutation data (194 missing for each of TP53, PTEN, EGFR, IDH1, NF1, and ATRX, fraction 0.3345)
- 194 unsequenced patients
- Data integrity issues in the split
- Insufficient events
- Failures in covariates, proportional hazards, and convergence checks
