<!-- agent_run_sha256: 0f02d7fe546e427468dfade02e270a89f80f4cf4dca8d1651f353b35205ef862 -->
> **UNAPPROVED DRAFT — pending human review**

## Cohort

This analysis focuses on cohort “luad,” comprising 501 patients. Of these, 497 patients have expression data available. The cohort includes 350 patients designated for training and 151 for testing. A notable amount of missingness was observed, with 10 patients missing age data (representing 2% of the cohort), and 2 patients missing stage data (representing 0.4% of the cohort). No other variables were missing.  Additionally, 61 patients were dropped due to missing overall survival (OS) data, and 4 patients had nonpositive OS months.

## Models and metrics

The analysis utilizes two models: “cox/clinical” and “cox/clinical_expression.”  The following metrics were calculated and passed integrity checks:

*   **harrell_c:**  This metric, representing calibration, consistently achieved values around 0.639 - 0.643 across both models.
*   **uno_c:** This metric, representing discrimination, consistently achieved values around 0.615 - 0.632 across both models.
*   **auc_12m, auc_24m, auc_36m:** These Area Under the Curve metrics for 12, 24, and 36 months, respectively, demonstrated performance ranging from 0.604 to 0.711.
*   **integrated_brier_6_36m:** This metric, representing the integrated squared calibration error, consistently achieved values around 0.153.

The models have passed checks for split integrity, minimum events, leakage, proportional hazards, and convergence.

## Checks and abstentions

All integrity checks for the “cox/clinical” and “cox/clinical_expression” models passed.  Specifically, the analysis confirmed no leakage, maintained proportional hazards assumptions, and achieved sufficient minimum events for reliable model estimation. The models were split into training (350 patients) and testing (151 patients) sets, and the split integrity was confirmed.

## Limitations

The analysis is limited by the missingness of data. 10 patients (2% of the cohort) were missing age data, and 2 patients (0.4% of the cohort) were missing stage data. While the models passed checks for proportionality of hazards, the missingness of these key variables could introduce bias if the missingness is related to the outcome.  Furthermore, the overall survival data was incomplete, with 61 patients missing OS data and 4 patients with nonpositive OS months, which may affect the accuracy of the survival predictions.  The calibration metrics, while generally good, are susceptible to bias if the missingness is not random.
