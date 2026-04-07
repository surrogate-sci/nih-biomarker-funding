# NIH Biomarker Funding Classification Rubric

> **SOURCE OF TRUTH**: This rubric is the authoritative classification guide.
> The prompt in `scripts/grader_prompt.py` should be generated from this document.

---

## Dimension 1: Intended Biomarker Use

Based on FDA-NIH BEST framework with extensions for NIH research contexts.

**`susceptibility_risk`** — Assign when the biomarker identifies risk of developing a disease in individuals who do NOT currently have clinically apparent disease. Includes genetic predisposition scores (APOE, BRCA, polygenic risk scores) and acquired risk factor models (e.g., Framingham) when applied to disease-free populations. Distinguish from `prognostic_risk` by the absence of established disease: if the study population already has the disease, use a prognostic code.

**`diagnostic`** — Assign when the biomarker is used to screen for, detect, or confirm the presence of a disease or condition. The biomarker's role is to classify individuals as having or not having a specific disease state at a given time point. Distinguish from `stratification_diagnostic` by the aim: if the primary goal is subtyping a heterogeneous disease into molecularly or clinically distinct subtypes rather than binary disease detection, use `stratification_diagnostic`.

**`monitoring`** — Assign when the biomarker is used to assess disease status serially over time in patients with established disease. The biomarker tracks progression, remission, recurrence, or stability. Distinguish from `prognostic_risk` by the temporal structure: monitoring implies repeated measurement to track change, whereas prognostic_risk implies a single-timepoint prediction of future outcome.

**`prognostic_risk`** — Assign when the biomarker predicts a clinical outcome (recurrence, progression, mortality, disease severity) in patients who have established disease, and the abstract makes no claims about treatment response or therapeutic benefit. The prediction is framed as reflecting the natural history or disease trajectory. Distinguish from `susceptibility_risk` by the presence of established disease; distinguish from `prognostic_efficacy` by the absence of any treatment-outcome claim.

**`prognostic_efficacy`** — Assign when the abstract claims a biomarker predicts clinical benefit from treatment in patients with established disease, but (a) does not name a specific drug or regimen, or (b) does not provide evidence of differential response between treatments. The biomarker is framed as identifying patients more likely to benefit from treatment generally, not as selecting among specific therapeutic alternatives. Distinguish from `prognostic_risk` by the presence of any treatment-outcome claim; distinguish from `predictive_enrichment` by the absence of a named treatment; distinguish from `prognostic_enrichment` by the absence of explicit trial design, enrichment strategy, or regulatory language.

**`prognostic_enrichment`** — Assign when a prognostic_efficacy biomarker is explicitly intended for clinical trial enrichment. The abstract must reference enrichment strategy, trial design optimization, or regulatory context. The goal is to select patients with higher expected event rates or greater expected treatment response because they have more severe disease. Enrichment biomarkers may also operate via safety signals — recruiting patients less likely to experience adverse effects and thus more likely to show net benefit. Distinguish from `prognostic_efficacy` by the explicit mention of enrichment, trial design, or regulatory context.

**`predictive_optimal`** — Assign when the biomarker is used to differentiate treatment effects across patient subgroups or individuals, with explicit reference to the biostatistical framework for doing so. This includes biomarker × treatment interaction testing, biomarker-stratified or biomarker-adaptive trial designs, predictive biomarker signature development (as defined by FDA), and at the individual level, CATE estimation, dynamic treatment regimes, or n-of-1 designs. The abstract must name specific treatments and either test or propose to test differential response. Distinguish from `predictive_enrichment` by the presence of treatment comparison (not just single-treatment responder identification); distinguish from `stratification_treatment` by explicit engagement with treatment-effect differentiation methodology.

**`predictive_enrichment`** — Assign when the biomarker predicts response to a named treatment or drug class, but without evidence of specificity to that treatment versus other treatments. The biomarker identifies likely responders to increase the proportion of patients who benefit in a trial or clinical setting. The abstract names a treatment but provides no comparative data against alternative treatments. Distinguish from `predictive_optimal` by the absence of treatment comparison; distinguish from `predictive_ambiguous` by the presence of a named treatment or drug class.

**`predictive_ambiguous`** — Assign when the abstract claims a biomarker predicts treatment response or therapeutic benefit, but does not name a specific treatment, drug class, or regimen, and does not provide evidence of a biomarker × treatment interaction. This is the default code when treatment-related prediction language is present but insufficiently specified to determine whether the biomarker is prognostic (outcome regardless of treatment) or genuinely predictive (differential response to a specific treatment). Distinguish from `prognostic_efficacy` by the presence of explicit "prediction" or "predictive" language directed at treatment response, rather than general outcome claims in a treatment context.

**`pharmacodynamic`** — Assign when the biomarker measures a biological response to a specific intervention (drug, therapeutic agent, or experimental compound). The biomarker's role is to confirm target engagement or quantify the magnitude of biological effect at a given dose or schedule. A pharmacodynamic biomarker does not itself predict clinical outcome; if the abstract claims the biomarker also predicts efficacy or patient benefit, assign the predictive or prognostic code that best fits the efficacy claim, and use `pharmacodynamic` as the secondary code.

**`safety`** — Assign when the biomarker measures toxicity, adverse events, or safety signals associated with a treatment or exposure. The biomarker identifies patients at elevated risk for treatment-related harm, or monitors for the emergence of adverse effects during treatment. Distinguish from `pharmacodynamic` by the focus: safety biomarkers measure harm or risk of harm, whereas pharmacodynamic biomarkers measure intended biological effect.

**`surrogate_endpoint`** — Assign when the biomarker is proposed or used as a substitute for a clinical endpoint, with the intent to support regulatory decision-making or drug approval. The abstract must frame the biomarker as standing in for a clinical outcome (e.g., overall survival, disease-free survival), not merely as correlated with it. Distinguish from `pharmacodynamic` by the endpoint substitution claim: pharmacodynamic biomarkers demonstrate drug effect but do not claim to replace a clinical endpoint. Distinguish from `prognostic_efficacy` by the regulatory or endpoint-substitution framing.

**`stratification_treatment`** — Assign when the abstract describes subtyping or classifying patients with the stated goal of guiding treatment decisions, but without reference to differentiating treatment effects across subtypes. The research may identify molecular or clinical subtypes and assert they should receive different treatments, but does not test or estimate biomarker × treatment interactions, does not reference predictive biomarker methodology, and does not engage with the biostatistical literature on treatment-effect heterogeneity. Typical examples: neuroimaging studies identifying "biotypes" from observational or perturbation data and proposing they imply different treatment needs; retrospective subtyping across biobank data with post-hoc treatment recommendations. Distinguish from `predictive_optimal` by the absence of treatment-effect differentiation methodology; distinguish from `stratification_diagnostic` by the explicit treatment-assignment intent.

**`stratification_diagnostic`** — Assign when the primary aim is to classify a heterogeneous disease into molecularly or clinically distinct subtypes for the purpose of understanding disease biology, natural history, or prognosis. The subtyping goal is disease understanding, not treatment assignment. Distinguish from `diagnostic` by the aim: diagnostic detects disease presence, whereas stratification_diagnostic resolves disease heterogeneity into subtypes.

**`stratification_ambiguous`** — Assign when the abstract describes stratification, subtyping, or patient classification goals but does not specify whether the purpose is treatment assignment or disease understanding. Default when stratification language is present but the downstream intent is unclear.

**`methods_causal`** — Assign when the primary aim is developing statistical, computational, or experimental methods for biomarker validation or evaluation with explicitly identification of causal questions, assumptions in the biomarker use case. Includes methods for causal inference that use Pearl, Hernan-Robins potential outcomes or structural causal models, treatment effect estimation, biomarker × treatment interaction testing, and quasi-experimental or RCT design for biomarker studies. Assign even if the methods are applied to a specific biomarker domain (e.g., surrogate validation in oncology), as long as the methodological contribution is the primary aim, and the methods explicitly aim to expand some school of causal inference methodology.

**`methods_correlational`** — Assign when the primary aim is developing statistical or computational methods for biomarker discovery, evaluation, or application that rely on associational evidence. Includes methods for prediction, classification, regression, feature selection, supervised machine learning, and risk scoring. Distinguish from `methods_causal` by the inferential framework: methods_correlational develops tools for association and prediction often using standard machine learning language or what Judea Pearl would call "rung 0" on his ladder of causation, whereas methods_causal more explicitly identifies when the biomarker context of use implies causal concepts on "rung 1" or "rung 2". Methods develop tools while recognizing causal identification conditions, good estimation of causal estimands and may consider what experimental designs can verify how good such methods are.

**`not_applicable`** — Assign when the grant matched keyword screening but is not substantively about biomarker research. Examples: satellite or administrative cores, infrastructure supplements, cost-effectiveness or health policy analyses, cohort recruitment infrastructure without biomarker measurement or validation as a primary aim. When assigned, Dimension 2 and Dimension 3 are null — do not assign codes for research design or evidence strength.

---

## Decision Hierarchy for Dimension 1

When classifying, apply these rules in order:

### Step 0: Is this grant substantively about biomarker research?

If the grant's primary purpose is infrastructure, administration, cohort recruitment, health economics, or methodology with no direct biomarker measurement or validation component — assign `not_applicable`. Stop here; leave Dim2 and Dim3 null.

### Step 1: Is this a methods grant?

If the primary aim is developing statistical/computational methods:

- Use `methods_causal` or `methods_correlational`
- Even if methods are FOR surrogate endpoints, prediction, etc.

### Step 2: Does the patient have disease?

- NO disease → `susceptibility_risk`
- YES disease → continue to Step 3

### Step 3: Is treatment mentioned?

- NO treatment context → `prognostic_risk`
- YES treatment context → continue to Step 4

### Step 4: How specific is the treatment?

- Named treatment with comparative data (Drug A vs Drug B) → `predictive_optimal`
- Named treatment, no comparison → `predictive_enrichment`
- "Response to therapy" without named treatment → check Step 5

### Step 5: Is enrichment/regulatory context mentioned?

- YES, enrichment/trial design/regulatory → `prognostic_enrichment` or `predictive_enrichment`
- NO enrichment context → `prognostic_efficacy` or `predictive_ambiguous`

### Step 6: Stratification vs other codes

- If subtyping/classification is primary goal:
  - For treatment selection → `stratification_treatment`
  - For disease understanding → `stratification_diagnostic`
  - Unclear purpose → `stratification_ambiguous`

### Uncertainty Tiebreaker

When uncertain between categories, use the more conservative code:

- correlational > causal (for evidence strength)
- prognostic_risk > prognostic_efficacy (less treatment assumption)
- predictive_ambiguous > predictive_enrichment > predictive_optimal (less specificity assumption)

Document uncertainty in notes or explanation, what features or ambiguity makes it confusing.

---

## Dimension 2: Research Design

**`observational_retrospective`** — Assign when the study uses existing data collected for other purposes: chart review, biobank analysis, registry data, claims databases.

**`observational_crosssectional`** — Assign when the study measures biomarker and outcome at a single time point. No temporal sequence between exposure and outcome.

**`observational_cohort`** — Assign when the study prospectively follows groups defined by exposure or biomarker status over time. Temporal sequence between biomarker measurement and outcome is established.

**`observational_longitudinal`** — Assign when the study collects repeated measures over time but is primarily descriptive, without an explicit exposed-vs-unexposed comparison. Distinguish from `observational_cohort` by the absence of an exposure contrast.

**`observational_case_cohort`** — Assign when the study uses nested case-control, case-cohort, or other efficient sampling designs within a larger cohort.

**`observational_quasi`** — Assign when the study exploits natural variation to approximate causal inference: policy changes, instrumental variables, regression discontinuity, difference-in-differences, Mendelian randomization.

**`experimental_singlearm`** — Assign when the study administers an intervention and measures pre/post change without a concurrent control group.

**`experimental_rct`** — Assign when the study is a randomized controlled trial with concurrent control (placebo or active comparator).

**`experimental_perturbation`** — Assign when the study uses experimental manipulations: gene knockdown/knockout, drug exposure in cell lines or animal models, dose-response experiments, non-pharmacological perturbation like brain stimulation. These may lack the design features of a full causal study.

**`methods_secondary_analysis`** — Assign when the primary aim is developing or evaluating analytic methods rather than collecting primary data. Includes secondary analyses, meta-analyses, simulation studies, method comparison studies, and software tool development.

---

## Dimension 3: Evidence Strength for Biomarker Validity

**CRITICAL**: This rates evidence that for the BIOMARKER claim is commensurate with causal content of biomarker context of use. This dimension does not evaluate whether the evidence for the treatment is causal e.g drug was evaluated in an RCT. It is possible for the study to be an RCT and for the strength of evidence for the biomarker validity to be poor.

**`correlational`** — Assign when the biomarker is associated with an outcome but no evidence is presented for the biomarker's causal role in mediating or predicting the outcome beyond statistical association. Default for observational studies without causal design elements.

**`experimental_weak`** — Assign when an intervention exists in the study but the biomarker's own causal validity is not tested or established. Example: a biomarker is measured within a single RCT but is not validated as a surrogate endpoint or shown to mediate the treatment effect.

**`causal_preclinical`** — Assign when the biomarker's causal role in a disease or treatment pathway is validated using in vitro experiments or animal models. The causal evidence is being evaluated in non-human or pre-RCTs.

**`causal_clinical`** — Assign when the biomarker is validated in human studies via appropriate biomarker guided RCT designs: Prentice surrogacy criteria (antiquated and not typical anymore), causal meta-analysis across multiple RCTs, biomarker-guided or adaptive trial designs where the biomarker drives treatment decisions, causal mediation analysis within an RCT or quasi-experiment, or (for risk biomarkers) counterfactual risk prediction or causal transportability analysis. Tag as `causal_clinical` if using causal machine learning or causal inference with well defended assumptions and identifiability requirements. If Baron-Kenny style SEMs or causal mediation is invoked, please tag this as `correlational`, not `causal_clinical`.

**`methods_for_causal`** — Assign when the study develops statistical or computational methods that enable biomarker causal validation. The contribution is methodological, not direct validation of a specific biomarker.

### Key Distinction: RCT ≠ Biomarker Validation

- "Single RCT measuring brain atrophy as pharmacodynamic marker" → **experimental_weak** (biomarker measured but not validated)
- "Biomarker-guided adaptive trial design" → **causal_clinical** (biomarker drives treatment decisions)
- "Meta-analysis across multiple RCTs validating surrogate" → **causal_clinical**
- "Longitudinal study finding biomarker predicts outcome" → **correlational** (association only)

---

## Mapping Common Terms to Codes

| Term in Abstract         | Likely Code                                                |
| ------------------------ | ---------------------------------------------------------- |
| "intermediate biomarker" | surrogate_endpoint or pharmacodynamic (depends on context) |
| "intermediate endpoint"  | surrogate_endpoint                                         |
| "efficacy biomarker"     | pharmacodynamic or predictive_ambiguous                    |
| "response biomarker"     | pharmacodynamic or predictive_ambiguous                    |
| "companion diagnostic"   | predictive_optimal or predictive_enrichment                |
| "theranostic"            | stratification_treatment or predictive_optimal             |

---

## References

1. FDA-NIH BEST (Biomarkers, EndpointS, and other Tools) Resource. [https://www.ncbi.nlm.nih.gov/books/NBK338448/](https://www.ncbi.nlm.nih.gov/books/NBK338448/)
2. Fleming TR, Powers JH. Biomarkers and surrogate endpoints in clinical trials. *Stat Med.* 2012
3. IOM/NASEM. Evaluation of Biomarkers and Surrogate Endpoints in Chronic Disease. 2010
4. Altar et al. A prototypical process for creating evidentiary standards for biomarkers. *Clin Pharmacol Ther.* 2008
