---
name: ml-model-evaluation
description: Review model evaluation evidence, leakage safeguards, and interpretation for an approved ML target.
---

# ML model evaluation

Use for evaluation design or result review. Read repository `AGENTS.md` and
approved target, split, and methodology decisions. Identify baselines,
held-out evaluation, relevant slices, uncertainty/calibration, and missing
evidence. Preserve negative and inconclusive findings. Stop if labels,
target horizon, holdout integrity, or public-health meaning is unresolved.
Stories #30 and #41 own evaluation and lineage contracts. This entry does not
approve a model or new target. Bind the frozen plan and protected holdout to
the [canonical evaluation contract](../../../docs/architecture/declarative-ml-contracts-v1.md);
stop on missing or incompatible identity.

For delayed-label monitoring, use the [Story #43 policy](../../../docs/contracts/monitoring-policy-v1.md)
to establish label eligibility and evidence sufficiency before interpreting
metrics. Retain the frozen #30 evaluation plan and baseline; append revised
label results as new evidence rather than replacing prior findings.
