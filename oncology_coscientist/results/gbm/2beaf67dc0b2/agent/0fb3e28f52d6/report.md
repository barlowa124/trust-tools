<!-- agent_run_sha256: c4c2bec18c7a7fb7e5e509a4b46a813d8ef30770553e9fbf2a397d3e4aefa832 -->
> **UNAPPROVED DRAFT — pending human review**

## Cohort
The gbm cohort comprises 580 patients. A subset of 152 patients have expression data, while 194 patients are unsequenced. The cohort was split into a training set of 406 patients and a testing set of 174 patients. Four patients were dropped due to missing overall survival (OS) data, and one patient was dropped due to a nonpositive OS months value. Glioblastoma (grade IV): A glioblastoma grows and spreads very quickly [PDQ:pdq_adult_brain_treatment#36].

## Models and metrics
Due to failures in covariate handling, proportional hazards assumption, and convergence, all focus models were abstained. Therefore, no metrics are available for cox/clinical, cox/clinical_expression, rsf/clinical, or rsf/clinical_expression. The prognosis and treatment options for primary brain and spinal cord tumors depend on the following [PDQ:pdq_adult_brain_treatment#93].

## Checks and abstentions
Split integrity passed, confirming data split consistency. The minimum events check passed, ensuring sufficient event counts for model training. The covariates check failed, indicating potential issues with covariate handling across all models. The proportional hazards assumption check failed, suggesting a violation of a key assumption for Cox models. The convergence check failed, raising concerns about the stability and reliability of the model training process. Due to these failures, all focus models (cox/clinical, cox/clinical_expression, rsf/clinical, rsf/clinical_expression) were abstained.

## Limitations
Due to the failures in covariate handling, proportional hazards assumption, and convergence, the analysis is limited. The prognosis and treatment options for metastatic brain and spinal cord tumors depend on the following [PDQ:pdq_adult_brain_treatment#99]. The failure of the covariates, proportional hazards, and convergence checks warrants further investigation and potential remediation.



## Context
Glioblastoma (grade IV): A glioblastoma grows and spreads very quickly [PDQ:pdq_adult_brain_treatment#36]. The prognosis and treatment options for primary brain and spinal cord tumors depend on the following [PDQ:pdq_adult_brain_treatment#93]. The prognosis and treatment options for metastatic brain and spinal cord tumors depend on the following [PDQ:pdq_adult_brain_treatment#99].
