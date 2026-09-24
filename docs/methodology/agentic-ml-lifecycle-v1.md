# Atlas Agentic ML lifecycle v1

This is an Atlas adaptation of [Aurélien Géron's ML project checklist](https://github.com/ageron/handson-ml/blob/master/ml-project-checklist.md), not a copy of its text. The order is useful, but Atlas adds public-health use limits, governed Snowflake data, point-in-time availability, geographic dependence, auditable holdout access, and human decisions. This document and `atlas-ml-lifecycle/v1` state are a workflow contract, not approval of any model or target.

## Gates and outputs

Stages are sequential. A completed stage needs its named evidence and applicable versioned references. A stage marked `not_applicable` needs a reason, an evidence reference, and an approved review decision. A blocked stage needs a named dependency and reason. Later stages cannot start until all preceding stages are terminal. Evidence references identify reviewable artifacts; a string alone does not prove their contents. Before a transition, the agent must inspect the artifact and record the reviewer decision where required.

| Stage | Gate output and responsible existing story |
| --- | --- |
| `frame` | Approved decision/target, unit, horizon, intended and prohibited use, evaluation/error costs, and abstention contract (`decision_contract`); #23. |
| `data` | Governed source eligibility, dataset contract, point-in-time availability, label maturity, geography and limitations (`dataset_contract`, versioned dataset reference); #23 and data#110/#113. |
| `explore` | Versioned profile of quality, missingness, time/geography behavior, revisions and limitations (`profile`). No protected holdout labels. |
| `prepare` | Reproducible feature definitions and fold-local preprocessing (`feature_implementation`, feature reference); #24. |
| `candidates` | Documented appropriate baseline and comparable candidate evidence (`baseline_comparison`, split and experiment references); #25/#26/#30. |
| `validate` | Frozen evaluation plan and result, including uncertainty/calibration, slices and negative findings (`frozen_evaluation_plan`, `evaluation_result`, model reference); #25/#30. |
| `communicate` | Model card with provenance, limitations, interpretation and explicit human review (`model_card`, `review_decision`); #35. |
| `operate` | Human release decision and monitoring/rollback plan (`release_decision`, `monitoring_plan`); #34/#35. No automatic retrain/promotion. |

The `operate` gate describes readiness evidence only. Snowflake ML Jobs/Registry, declarative cross-system lineage, Arize integration/policy, independent review automation, and CI harnesses belong to #40–#46. A complete state does not itself execute a release.

## Validation and leakage

The intended generalization problem determines the #25 split contract. IID prediction may justify random or stratified cross-validation. Future prediction needs temporal validation. Unseen geography needs grouped/spatial validation. Future prediction in unseen geography needs spatiotemporal validation. Random K-fold is never the automatic county-time default. Freeze cutoffs, cohort, label maturity, embargo/gap when needed, spatial groups, preprocessing fitting, metrics and selection rules before final holdout access. Check target, future/revision, temporal and spatial leakage. Use point-in-time data available at the prediction cutoff.

The protected final holdout must not drive feature selection, model-family/algorithm selection, hyperparameter tuning, threshold selection, calibration selection, repeated exploration, or prompt-guided iteration. Record every access with actor, time, purpose, split, frozen plan and result. A later access is possible only with a recorded reason and reviewer decision reference; preserve failed and inconclusive results. Access for any prohibited purpose is invalid. The event log is append-only in practice and must be reviewed against underlying access records; this local validator cannot detect omitted events.

## Baselines, transformations and decisions

Every production-intended model needs an appropriate documented simple baseline under the same dataset, split and evaluation contract as candidates. A strong absolute metric alone is insufficient. Preserve negative and inconclusive findings. Prefer the simplest adequate model unless added complexity has material evidence-backed value under the approved #23/#30 criteria; this lifecycle sets no universal algorithm or threshold.

Every transformation required to reproduce training, evaluation or inference must live in version-controlled Python, SQL, Snowpark or approved feature definitions/configuration. A transient notebook, worksheet, shell history or manual step cannot be the only implementation. Record versions, code revision, dependencies, seeds and remaining nondeterminism. Distinguish model uncertainty from data completeness and association from causation. Arize observability is planned, but absent telemetry is not evidence of monitoring readiness.

## State procedure

Use `docs/methodology/lifecycle-state-v1.schema.json` and `docs/methodology/lifecycle-state-v1.template.json`; validate with `lyme_gap_atlas_ml.lifecycle.load_state` or `validate_state`, then call `resume`. Check each referenced artifact before claiming a gate. Record a transition only after the prerequisite and required outputs exist, with human decision references for non-applicability and communication/operation. Never invent or rerun completed evidence. The synthetic partial example in `tests/fixtures/partial_lifecycle.json` demonstrates a blocked resume; it is not Atlas model evidence.
