# Tier 1 county surveillance-review priority contract v1 (ML #23)

**Status:** GO, product decision approved 2026-10-05

**Owner:** Atlas ML product and engineering leads

**Unit:** county

## Product job and approach

Help a public-health epidemiologist identify counties whose current
surveillance/evidence profile is unusual enough to warrant further review.
Tier 1 uses unsupervised surveillance-review prioritization. Isolation Forest
is the primary candidate; one simple standardized-distance/statistical anomaly
method is the reference. The existing deterministic County Review Priority is
a transparent comparator, never a model input or supervised training label.

There is no training target and no supervised ground-truth label requirement
for Tier 1. Supervised label qualification and reported-burden forecasting are
separate future work and do not gate this vertical slice. This GO decision
approves the product/model objective, not a trained model or public release.

## V1 output and interpretation

For each scientifically scorable county, the eventual output supports a raw
anomaly/model score, within-batch percentile, HIGH/MEDIUM/LOW review-priority
tier, evidence-sufficiency state, and lightweight contributing evidence
groups/reasons where supportable. It carries model version, inference batch/run
version, and tier-policy version. The selected batch also needs governed
data/feature lineage, as-of time, and limitations so consumers can interpret
and reproduce it. Missing, unknown, insufficient, and not-estimable evidence
must not silently become zero or LOW. ML owns the tiering policy; API and Web
consume it without recomputation.

The output means **surveillance review priority**, **unusual evidence
profile**, and **candidate for epidemiologist review**. It does not mean Lyme
disease risk, predicted or true incidence, individual risk, diagnosis, causal
effect, an underreporting estimate, or a calibrated disease probability.
Reasons describe observed feature groups; they are not causal explanations.

## Data, inference, and evaluation posture

Use governed data available now and preserve source, retrieval/release,
geography, methodology, quality state, and limitations. NLCD, climate, MODIS,
drought, terrain, Census PEP, and any other optional source family are
non-blocking incremental feature candidates. Do not invent unavailable values
or pool incompatible source eras. Manual/on-demand batch inference is
sufficient for V1; scheduled inference and retraining are not required.

ML #30 evaluates reproducibility, score/tier distribution, stability,
evidence-state and geographic artifacts, inspectable reasons, and comparison
with the heuristic as a reference. Supervised accuracy is not a Tier 1 ship
gate. Thresholds and a SELECT/REJECT/DEFER model decision belong to #30; this
contract sets no numeric tier boundaries and does not select a trained model.

## Downstream execution

This contract unblocks ML #24 (county feature matrix), #27 (Isolation Forest
and statistical reference), #30 (ship/no-ship evaluation), and #32 (persisted
outputs). After the selected batch is approved and persisted, API #10 exposes
it and WEB #457 presents model-assisted review priority. Each downstream
ticket retains its own acceptance and release gates. No model training,
feature construction, or broad EDA occurs in ML #23.

The existing declarative lineage v1 schema requires label-specific fields,
including `label_as_of`. Downstream implementation must resolve that schema
compatibility through an explicit versioned contract change before using it
for unlabeled Tier 1 runs; it must not invent label values or dates. This is
an implementation compatibility task, not a supervised-label prerequisite.
