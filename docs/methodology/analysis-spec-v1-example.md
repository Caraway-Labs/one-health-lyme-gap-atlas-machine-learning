# Representative analysis spec — unexecuted synthetic example

This demonstrates filling the v1 template, not an Atlas data finding or approved
product question. No data is queried, generated or analyzed in Story #60.

- **Spec/version and issue:** `example-coverage-change/v1`; #60 template demonstration.
- **Question / decision / interpretation:** Can the supplied synthetic county
  evidence support a before/after coverage comparison? Decide whether a change
  analysis is estimable; no disease, causal or individual-risk interpretation.
- **Estimand:** Paired mean difference in observed-evidence coverage proportion
  between two specified periods for the same eligible counties.
- **Unit / cohort / geography / time:** County pair in a fictional cohort;
  scenario supplies only period A, no period B. No actual geography or cutoff.
- **Variables / source / version:** Fictional observed-evidence indicator and
  county/period keys, scenario `single-period-example/v1`; no governed release
  exists for this illustration. Real execution requires an exact approved source.
- **Missingness rule:** Preserve unknown evidence as unknown; report eligibility
  and observed denominators separately. Missing period B is not zero coverage.
- **Exploratory or confirmatory:** Exploratory planning example, unexecuted;
  no tested hypothesis family, p-values or multiplicity adjustment.
- **Method / assumption rationale:** Proposed paired descriptive difference only
  if comparable repeated observations exist, because the estimand compares the
  same counties; no test is selected while the paired contrast is unidentified.
- **Spatial / temporal dependence:** Counties may be spatially dependent and
  repeated observations temporally dependent. No independent-sample inference
  is allowed without a justified dependence-aware uncertainty design.
- **Effect-size / uncertainty output:** No estimate or interval: period B is
  absent. Future execution must report paired coverage and uncertainty limits.
- **Key caveat / stop conditions:** Single-period evidence cannot identify change;
  actual source authority and comparability are also unresolved in this example.
- **Result disposition:** **NOT_ESTIMABLE for this scenario**; STOP actual execution
  until approved source and question exist. This is a planning disposition, not
  a conclusion about the current Atlas dataset. Smallest next step: establish
  comparable period evidence or explicitly choose a different approved estimand.
- **Reproduction / evidence:** Read this scenario and
  [analysis-spec-v1.md](analysis-spec-v1.md); verification:
  `uv run python scripts/verify.py`. No execution entry point, measured results,
  lifecycle completion or scientific PASS is claimed. EDA artifact N/A, no
  transient outputs produced or committed.
