<!-- agent_run_sha256: 6ab4561254b4de694697fc5764dd516bf3f7fbc3e9254769747c2904f209b902 -->
> **UNAPPROVED DRAFT — pending human review**

## Cohort

This cohort, designated “brca,” comprises 1071 patients. Of these, 1069 patients have expression data available, while 18 remain unsequenced. The dataset was split into 749 patients for training and 322 patients for testing. Notably, 13 patients have nonpositive outcomes in months, and 19 patients are missing stage information, representing 1.77% of the cohort. Furthermore, 18 patients are missing information regarding mutations in TP53, PIK3CA, CDH1, GATA3, MAP3K1, and KMT2C, each representing 1.68% of the cohort.

## Models and metrics

The analysis utilizes two models: `cox/clinical` and `cox/clinical_expression`. The following metrics were calculated:

*   **harrell_c:** Measures the correlation between predicted and observed survival times.
*   **uno_c:**  Unadjusted concordance index.
*   **auc_12m, auc_24m, auc_36m:** Area under the receiver operating characteristic (ROC) curve at 12, 24, and 36 months, respectively.
*   **integrated_brier_6_36m:** Measures the integrated squared difference between predicted and observed probabilities.
*   **auc_mean:** The average of the AUC values across the specified time points.

The models have passed all integrity checks, including split integrity, minimum events, leakage, proportional hazards, and convergence.

## Checks and abstentions

The following checks were successfully completed:

*   **Split Integrity:** The models perform correctly on both the training and testing datasets.
*   **Minimum Events:** Sufficient events were observed to allow for reliable model training and evaluation.
*   **Leakage:** No data leakage between the training and testing sets was detected.
*   **Proportional Hazards:** The models satisfy the proportional hazards assumption.
*   **Convergence:** The models have converged to a stable solution.

The following data was abstained from analysis due to missing information:

*   1.77% of patients are missing stage information.
*   1.68% of patients are missing mutation data for each of the specified genes (TP53, PIK3CA, CDH1, GATA3, MAP3K1, KMT2C).
*   13 patients have nonpositive outcomes in months.

## Limitations

The analysis is limited by the missing data present in the cohort. Specifically, the absence of stage information and mutation data for key genes (TP53, PIK3CA, CDH1, GATA3, MAP3K1, KMT2C) introduces uncertainty into the model’s interpretation and predictive power. The 13 patients with nonpositive outcomes in months also represent a potential bias.  The relatively small size of the testing dataset (322 patients) may limit the generalizability of the findings.
