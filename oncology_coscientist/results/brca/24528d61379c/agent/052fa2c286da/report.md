<!-- agent_run_sha256: 3991f0bc584d1118e799f7b4778580ba010e81585cb550e35c64e6961713bf41 -->
> **UNAPPROVED DRAFT — pending human review**

## Cohort

This analysis focuses on a cohort of 1071 patients with breast cancer. A training set of 749 patients was used for model development, and a testing set of 322 patients was used for evaluation. The cohort includes 1069 patients with expression data and 18 unsequenced patients. Several data quality checks were performed to ensure the reliability of the analysis. Missing data is a concern, with 19 patients having missing stage data and 18 patients each missing data for mut_TP53, mut_PIK3CA, mut_CDH1, mut_GATA3, mut_MAP3K1, and mut_KMT2C. Thirteen patients have nonpositive overall survival (OS) months, and zero patients have missing overall survival (OS).

## Models and metrics

Four models were evaluated: Cox proportional hazards models using clinical data ("cox/clinical"), random survival forests (RSF) using clinical data ("rsf/clinical"), Cox proportional hazards models using clinical expression data ("cox/clinical_expression"), and random survival forests (RSF) using clinical expression data ("rsf/clinical_expression"). The analysis plan focuses on comparing the performance of Cox and RSF models on both clinical and clinical expression data, and assessing the impact of expression data on model performance. Key metrics to be disclosed include harrell_c, AUC (at 12, 36, and 24 months), and integrated brier score at 6-36 months.

## Checks and abstentions

Several data quality checks were performed, including assessments of split integrity, minimum events, leakage, proportional hazards, and convergence, all of which returned true. The presence of nonpositive overall survival (OS) months in 13 patients represents a potential limitation that may influence the accuracy of survival predictions.

## Limitations

The analysis is subject to several limitations stemming from missing data. The missingness of stage data and genetic mutations (TP53, PIK3CA, CDH1, GATA3, MAP3K1, and KMT2C) in a number of patients (18-19) could introduce bias and reduce the generalizability of the findings. The presence of nonpositive overall survival (OS) months in 13 patients also poses a challenge to accurate survival prediction. Hormone therapy helps lower the risk of recurrence of certain types of breast cancer [PDQ:pdq_breast_treatment#9]. Inflammatory breast cancer treatments may include surgery, radiation therapy, chemotherapy, and more [PDQ:pdq_breast_treatment#15].



## Context

Treatment of oligodendrogliomas may include surgery with or without radiation therapy [PDQ:pdq_adult_brain_treatment#174]. Surgery followed by radiation therapy and chemotherapy [PDQ:pdq_adult_brain_treatment#161]. For pineoblastomas, surgery, radiation therapy, and chemotherapy [PDQ:pdq_adult_brain_treatment#190].
