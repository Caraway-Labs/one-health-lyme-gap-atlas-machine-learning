# Atlas Agentic ML lifecycle v2

Use one versioned JSON state and the existing offline validator. Stages are
sequential; inspect referenced artifacts before marking a stage complete.
References prove presence, not scientific correctness or approval.

| Stage | Required evidence and existing owner |
| --- | --- |
| `frame` | `decision_contract`: explicit question/target, user decision, intended and prohibited interpretation; #23. |
| `data` | `dataset_contract`, `leakage_review`: governed cohort, timing/availability and revision cutoffs, leakage risks, time/geography limits; #23/#24. |
| `baseline` | `baseline_comparison`, `validation_design`: simplest compatible analysis/model first; split matches intended temporal/geographic generalization; #24/#25/#26/#30. |
| `evaluate` | `frozen_evaluation_plan`, `evaluation_result`: frozen validation, errors/slices, uncertainty, limitations and comparison with baseline; #25/#30. |
| `decide` | `review_decision`, approved human review, and SELECT / REJECT / DEFER / BLOCKED disposition with evidence. No automatic release. |

No target/model work without an explicit question/target. Use only data available
at the prediction cutoff, excluding future/revised information. Fit preprocessing
within training folds. Future prediction needs temporal validation; unseen
geography needs grouped/spatial validation; both need spatiotemporal validation.
Do not default county-time data to random K-fold. Compare against the simple
baseline before accepting complexity. Existing stories above define details;
this checklist adds no target, metric, threshold, or public-health claim.

Final holdout use is restricted to final evaluation or independent audit after
Frame, Data and Baseline evidence and a frozen evaluation plan exist. Never use
it for tuning, feature/model/threshold/calibration selection, repeated exploration,
or prompt iteration. Preserve every access and negative/inconclusive result.
Repeated permitted access requires a reason and reviewer decision reference.
The validator cannot detect omitted access events or judge artifact contents.

Use [the schema](lifecycle-state-v2.schema.json) and
[template](lifecycle-state-v2.template.json). Load with `load_state`, then call
`resume` from `lyme_gap_atlas_ml.lifecycle`: it reports completed evidence,
current stage/status, next stage and allowed action. `holdout_used` is derived
from the append-only `holdout_history`; do not store a conflicting yes/no flag.
The project/model identifier is `project_id`, with optional versioned model
identity in `references`. A blocked stage records dependency and reason.
Completion requires named evidence and relevant versioned references; a justified
`not_applicable` Evaluate stage requires evidence and approved reviewer decision.
Frame, Data and Baseline scientific prerequisites cannot be waived. Decide
cannot be not_applicable: use an explicit reviewed DEFER or BLOCKED disposition
when ending a run without selection.
No exception authorizes target work without Frame evidence or bypasses scientific gates.

The [partial fixture](../../tests/fixtures/partial_lifecycle.json) resumes at
blocked Baseline after Frame and Data. Resolve its named dependency, then work;
never rerun completed stages. Run `uv run python scripts/verify.py` before handoff.
Production monitoring/retraining belongs to a later production-scoped story.

Migration: v1 artifacts remain historical and unchanged. The active validator
rejects v1 instead of silently renaming stages. An owner must inspect old evidence,
map explore/prepare into Data/Baseline, candidates into Baseline, validate into
Evaluate, and communicate into Decide; add missing v2 evidence and decision.
Retain operate/release evidence separately if production work is actually scoped.
Do not infer completion or approval during migration. See ADR 0003.
