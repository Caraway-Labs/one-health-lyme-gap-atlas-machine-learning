# Cross-signal disagreement decision contract v1

Owner: ML [Story #52](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/52),
under [#50](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/50).
Status: draft for a transparent statistical baseline; **no operational signal
pair, threshold or user-facing anomaly output is approved by this document**.
No supervised training, new infrastructure or future supervised design is needed.

## Decision, unit and permitted evidence

Support an analyst deciding which comparable cross-signal observations merit
manual evidence review. The unit is `(county_fips, period_start, period_end,
signal_pair_id)` within one explicit governed release/version. Different units
require a separately reviewed spec. Disagreement means an unusually large
signed difference relative to a reviewed comparable reference cohort; it is
evidence discordance, not evidence of disease or an adverse event.

Only a pair approved in an owning analysis spec is eligible. The spec must name
both governed measure definitions and sources, release/query/version, geography,
period, reporting/availability cutoffs, value states, units/denominators,
revision policy, permitted use, and an interpretable common comparison scale.
Counts and rates cannot be subtracted directly. Unrelated constructs cannot be
made comparable merely by normalization. Derived versions of the same source
are not independent corroboration; source linkage must be disclosed and the
pair's scientific interpretation explicitly justified.

Minimum evidence for each comparison:

- Both finite, observed values for the exact eligible county-period, unique
  join keys, valid denominators where relevant, and complete provenance.
- Compatible construct, coverage, geographic boundaries, period/grain, source
  availability and revision policy; no silent joins across reporting eras.
- Reviewed comparison transforms, reference cohort/time window, minimum eligible
  reference count, nondegenerate reference spread, threshold and rationale.
- Missingness/coverage and source-quality limitations recorded; spatial/temporal
  dependence considered for reference selection and any uncertainty claims.

Missing, suppressed, unknown, stale, duplicate, incomparable or insufficient
reference evidence yields **“Insufficient evidence to compare”**, with reason
and source references. Residual/score/flag must be absent, never zero or true.
Missingness itself may be summarized separately; it is not disagreement evidence.
Missing approved configuration stops execution with NEEDS_DECISION; it must not
be silently replaced by library defaults or fitted from inspected candidate flags.

## One implementable baseline

Given approved transforms `T_A`, `T_B`, compute `d = T_A(A) - T_B(B)` on the
eligible comparison scale. On the separately specified eligible reference cohort,
compute `center = median(d_ref)` and `spread = median(abs(d_ref - center))`.
For positive finite spread, report `residual = d - center` and
`score = abs(residual) / spread`. This unscaled median-absolute-deviation score
is a descriptive relative discrepancy, **not a z-score, probability or p-value**.
If spread is zero/nonfinite or reference eligibility fails, do not add an epsilon
or fall back silently: return insufficient evidence.

With an explicitly reviewed positive finite threshold `tau`, `score > tau` means
**DISAGREEMENT_FOR_REVIEW**; otherwise **NO_FLAG_AT_REVIEWED_THRESHOLD**.
Equality is not flagged. No-flag is not proof of agreement, health, completeness
or low risk. Preserve signed residual to explain direction, both source values,
coverage/limitations, reference/config versions and evidence references.

This is ordinary filtering, subtraction and medians, implementable with existing
Python/numerical tools. It does not train a predictor. Freeze the spec/config
before evaluation; exclude evaluated candidate observations from reference
calibration and use time-appropriate evidence. Protected predictive holdouts
are not exploratory reference data. Any change to transforms/cohort/threshold
is an explicit versioned amendment, not a hidden optimization for more flags.

## Evaluation and testable behavior

Use at most these two initial measures, with denominators and limits:

1. **Comparison coverage:** eligible scored units / all in-scope units; report
   excluded counts by insufficiency reason. High coverage does not prove validity.
2. **Review yield:** independently adjudicated meaningful evidence-discordance
   flags / reviewed flags, using a prespecified review rubric and sample. Report
   count and justified uncertainty; without review evidence mark NOT_ESTIMABLE.
   This is not outbreak detection accuracy or disease sensitivity.

Contract cases for a later implementation (fictional arithmetic, not analysis):

| Inputs/config | Required behavior |
| --- | --- |
| Missing A or B, incompatible period/unit, duplicate key, unknown state | Insufficient evidence; no score/flag |
| Reference below approved minimum, spread zero/nonfinite | Insufficient evidence; no score/flag |
| Pair/transform/reference/threshold approval absent | Stop NEEDS_DECISION; no defaults |
| Approved fixture reference differences `[-1, 0, 1]`, candidate `d=4`, test-only `tau=3` | Center 0, spread 1, residual 4, score 4; review flag |
| Same fictional fixture, candidate `d=3` | Score equals threshold; no flag |

The numbers above are test-only expectations, **not operational defaults**.
Actual minimum count, transform, reference and threshold require a bounded
scientific/product decision in the owning analysis spec. This draft can be
reviewed without data reads; it does not assert that any current Atlas pair is ready.
The #40 sample path proves access to a single-period human projection, not
cross-signal eligibility or historical calibration readiness.

## Interpretation, evidence and next decision

Prohibit outbreak, hidden disease, underreporting, individual risk, clinical or
causal claims. A flag initiates evidence review only; it cannot change governed
observations, promote a model, trigger retraining or authorize publication.
Source revision and telemetry failure remain separate from disagreement.

Before implementation/execution, the owner supplies the pair/scale/reference/
minimum/threshold decisions above using the
[analysis spec](../methodology/analysis-spec-v1.md). Reuse existing lineage and
scientific review where applicable. Persist any material execution findings
under [docs/eda](../eda/README.md), with exact source/config/code/reproduction
references and limits; keep exports transient. Story #52 itself performs no
analysis or training, so EDA artifact N/A. Verification is the existing
`uv run python scripts/verify.py`; no new service or gate is introduced.
