<!-- agent_run_sha256: c7acb8343db7b66f28c481024dbd42c493052b02f6b44d39f832b1657f473bd0 -->
> **UNAPPROVED DRAFT - pending human review**

## Cohort
The LUAD (Lung Adenocarcinoma) cohort consists of 501 patients, with 497 of them having expression data available. The cohort is split into a training set of 350 patients and a test set of 151 patients. The missing data in the cohort is minimal, with only 10 patients missing age data (2%) and 2 patients missing stage data (0.4%). A total of 61 patients were dropped due to missing OS (Overall Survival) data, and 4 patients were dropped due to non-positive OS months.

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
- 10 patients (2%) missing age data
- 2 patients (0.4%) missing stage data
- 61 patients dropped due to missing OS data
- 4 patients dropped due to non-positive OS months
