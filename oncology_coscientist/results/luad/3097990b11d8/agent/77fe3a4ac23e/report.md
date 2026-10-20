<!-- agent_run_sha256: c768fb639703d6a9b7404b3ff7e20278568c6f3948828c9b3e2017fc65f21087 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The cohort consists of 501 patients, with 497 having their expression data available. The missingness analysis reveals that the 'age' variable has the highest proportion of missing values at 2%, while 'sex', 'stage', 'mut_TP53', 'mut_KRAS', 'mut_EGFR', 'mut_STK11', and 'mut_KEAP1' variables have no missing values. The 'stage' variable has 2 missing values, which constitute 0.004 of the total dataset. No patients had missing 'os' (overall survival) data, but 61 patients had missing 'os' months data, and no extra primary samples or patients without primary samples were dropped.

## Models and metrics
- cox/clinical: harrell_c 0.647 | uno_c 0.640 | integrated_brier_6_36m 0.153 | auc_12m 0.649 | auc_24m 0.691 | auc_36m 0.694 | auc_mean 0.681
- rsf/clinical: harrell_c 0.639 | uno_c 0.639 | integrated_brier_6_36m 0.153 | auc_12m 0.604 | auc_24m 0.675 | auc_36m 0.695 | auc_mean 0.663
- cox/clinical_expression: harrell_c 0.643 | uno_c 0.632 | integrated_brier_6_36m 0.157 | auc_12m 0.711 | auc_24m 0.666 | auc_36m 0.628 | auc_mean 0.664
- rsf/clinical_expression: harrell_c 0.632 | uno_c 0.615 | integrated_brier_6_36m 0.153 | auc_12m 0.671 | auc_24m 0.672 | auc_36m 0.609 | auc_mean 0.649

## Checks and abstentions
- split_integrity: PASS
- min_events: PASS
- leakage: PASS
- proportional_hazards: PASS
- convergence: PASS

## Limitations
- 'age' variable has a high proportion of missing values.
- 'stage' variable has a small number of missing values.
- 61 patients have missing 'os' months data.
- 2 patients have nonpositive 'os' months data.
- No extra primary samples or patients without primary samples were dropped.
