# EDA #62: SVI by positive vector evidence state

**Pooled point category: MATERIAL_DIFFERENCE; magnitude classification is uncertain.**
In the governed published PROD cohort, IXODES_SCAPULARIS Established counties
have lower overall SVI than Reported counties: median 0.4528 versus 0.6258.
Probability of higher SVI in Established versus Reported is 0.3769 (tie-adjusted),
with a nominal 95% state-cluster interval 0.3259–0.4365. The point rank effect
meets the registered material threshold; the interval spans SMALL and MATERIAL,
so **no confidence-supported magnitude category is assigned**. Within-state
contrasts vary in direction. This is exploratory descriptive association, not
causation, biological abundance/absence, surveillance-quality validation or ML
feature admission.

Issue: [ML #62](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/62),
parent #59; [#60 analysis contract](../methodology/analysis-spec-v1.md).
Question: Do counties with stronger source-reported vector establishment evidence
differ in overall national SVI percentile from counties with weaker-but-positive
evidence for one compatible taxon?

## Registered question, scope and selection

The [specification](../methodology/62-svi-vector-evidence-spec.md) was committed
before results at `a05e83ccce4e27f717a16dd24f2fe1105bb59dbd`. Source-positive
states, candidate order, >=30/group eligibility, missingness, county weighting,
Mann–Whitney/effect output, geographic checks and interpretation criteria were
fixed before outcomes. The rank-neutral/unequal-spread interpretation amendment
was committed at `df1fa7914647f35120deaac841128feb0b28c6cd`.

Parent scientific review corrected an overstrict access gate. Descriptive EDA
of the existing governed **published county projection** does not universally
require private source-record hashes or REVIEWED #191/#193 envelopes. The
explicit amendment at `42324b7ff1eb53bf3c660300121b7bf738ac43c6` admits this
consumer EDA while retaining release/bundle, species mapping, source/vintage,
canonical coverage, missingness, digest and interpretation requirements.
Native lineage validation and ML admission remain separate, unclaimed work.

The [selected input/cohort](../methodology/62-prod-selection.md) was committed
at **`114ccc0aa7f73427f9b5ead1808c0b2bd00d772b` before any SVI result statistics**.
The first preregistered taxon, IXODES_SCAPULARIS, has adequate positive N.
IXODES_PACIFICUS has only 15 Reported counties and fails the N floor. Outcomes
were not inspected to select either taxon or method.

| Actual consumer taxon field | Established | Reported | No records | Unknown |
| --- | ---: | ---: | ---: | ---: |
| scapularis_status | 1,307 | 475 | 1,327 | 35 |
| pacificus_status | 97 | 15 | 2,997 | 35 |

Exact source-defined consumer labels `Established` and `Reported` correspond
to canonical ESTABLISHED and REPORTED. They are two positive evidence states,
not pathogen-test DETECTED/NOT_DETECTED or an absence contrast. Primary cohort:
**1,782 unique counties**, 1,307 / 475. Excluded: 1,327 No records and 35 Unknown;
neither is biological negative. Source-native sampling events/source-row N are
not known from this consumer capture. Both taxon fields refer to the same 3,144
counties and were not pooled as independent observations. Invalid/duplicate FIPS
exclusions: zero. SVI missing/invalid/sentinel exclusions in the selected positive
cohort: zero; complete-case N remains 1,307 / 475. Zero SVI would remain valid.

## Governed input and provenance

Existing [semantic-release consumer contract](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-release/README.md)
and V072 expose CURRENT_COUNTY_ATLAS_V and CURRENT_RELEASE_V. The task explicitly
authorized one bounded PROD consumer read under the existing runbook profile.
Context verified before data: user MATTHEWCARAWAY, role OH_LYME_PROD_RUNTIME,
database ONE_HEALTH_LYME_GAP_ATLAS_PROD, schema PRESENTATION,
warehouse OH_LYME_PROD_INGEST_XS_WH; secondary roles NONE. No credential/config
change, private-object retry, stronger-role fallback or national API crawl.

- Release: `governed-2026-09-18-unknown-coverage`, schema `1.0.0`, method `semantic-1.0.0`.
- Served bundle SHA-256: `038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`.
- Private raw capture SHA-256: `a62e522c2da8482a20fd1ad055fe280acd15c60e49f63d6b2d331f9fef50395e`.
- Context capture SHA-256: `88c2c875bc79e6cea13c0fcc6dad5e7c5d722802066aff308762386eb78774af`.
- Canonical sorted FIPS digest: `f2651ec6a9375476e3ff09efb4c2a699cd5690ffd3f0c982aeacad967c21c241`.
- Capture query: `01c77eba-040b-dea2-0064-2d070110a5fa`.
- Capture completed 2026-10-04T02:02:45Z (local file completion time,
  not the original publisher retrieval time).
- [Capture SQL](../../sql/datasets/eda62_prod_consumer_capture.sql), SHA-256 LF UTF-8:
  `9edc9d737d9489d3c7f2f44ac2bc008eea413f962ebabc161ce1ae64f6eae9d2`.

All 3,144 ordered unique counties match the canonical shared county-set digest.
Before/after pointer release/bundle match; every county row is pinned to that
release/bundle. One county projection with <=3,145 rows, 30-second statement
timeout; only the two published PROD views were read. Stored fields: release ID,
bundle, FIPS/state, species states, overall SVI and burgdorferi_status for
parent-coordinated #65 reuse. No rowdata is committed or uploaded.

The matching [September 18 manifest](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-release/governed-2026-09-15-manifest.json)
(blob `ef7e08c2919d38bdf6bdaa8ef79316b1bafd00f5`; filename is historical)
provides the frozen source identities below. Existing
[build](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/actions/runs/35328355391)
and [publication](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/actions/runs/35362701191)
receipts at build head `7b80373187b8aa665891e2f39e6bf7f8c6fb35a1`, as documented in
[DATA200](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/200#issuecomment-5965980365),
bind historical manifest tuples to this served release/bundle. The served digest
was not independently recomputed from native source artifacts. No fresh private
record/hash/metadata-authority replay or source/ML acceptance is claimed.

| Governed source | Definition / time meaning | Source-version ID | Ingestion-run ID | Artifact SHA-256 |
| --- | --- | --- | --- | --- |
| CDC ArboNET cdc-ixodes-county-status-2025 | 1; cumulative through 2025-12-31 | b81c116f-d93d-4c6b-9d11-ac2477e0e242 | ec14cc85-85d6-4064-80f1-1354238b88d6 | e35a5066a7c77b2e79c50f315a18e042405ab7baa8a414a1a907792bb25d2adc |
| CDC/ATSDR atsdr-svi-2022-county-layer | 1; national RPL_THEMES percentile; ACS 2018–2022 | b8b6bf61-c6a3-4538-b0df-1b88c61720b1 | 331f367d-9282-4936-9b49-a480db995016 | dc042342a2e5abc108af67b439ec04c86da8b61f9bdd1cf1b1e5ee0462dea7b2 |

SVI is national county rank on [0,1], not a percentage, population count,
individual risk or raw disease burden. Cumulative 2025 tick evidence and 2022
SVI context are not contemporaneous annual measurements. Existing source,
normalization and native-versus-consumer lineage boundaries remain unchanged.

## Method, effects and uncertainty

Registered two-sided Mann–Whitney U, normal approximation with tie-corrected
variance and continuity correction. The primary effect is P(SVI_Established >
SVI_Reported) + 0.5 P(tie), county-weighted; equal distribution shapes are not
assumed and U is not interpreted solely as a median test. Central/spread/overlap
summaries remain separate descriptive quantities. One selected contrast; no
method/taxon switching or outcome-based selection and no protected holdout use.

| Overall SVI percentile | Established (N=1,307) | Reported (N=475) |
| --- | ---: | ---: |
| Mean | 0.47061 | 0.59164 |
| Median | 0.4528 | 0.6258 |
| Q1 / Q3 | 0.2270 / 0.70745 | 0.3813 / 0.8177 |
| IQR | 0.48045 | 0.4364 |
| Range | 0.0010–0.9984 | 0.0025–1.0000 |

- Superiority: **0.376949**, nominal 95% whole-state bootstrap interval
  **[0.325894, 0.436478]**; neutral value 0.5.
- Rank-biserial effect: **−0.246102** (monotone interval **[−0.348213, −0.127044]**).
- Median difference Established minus Reported: **−0.1730**; mean difference
  **−0.121032**. These central summaries have no separate uncertainty interval.
- U_Established = **234,019.5**; nominal two-sided county-independence
  p = **1.807×10^-15**. It is **ancillary and spatially unadjusted**, not
  state-adjusted inferential evidence or proof of product/ML importance.
- Empirical CDF maximum separation: **0.214954**; common-range fraction
  **0.996897**. Broad shared range is not distribution equivalence or a density
  overlap estimate. Unequal-spread rank-neutral regression case remains tested.

State-cluster bootstrap uses the union of 39 contributing states, resampling
whole states with replacement; 27 have both groups. Fixed seed 62, 2,000 draws,
all 2,000 valid. These exceed registered >=10-state / >=5-mixed-state thresholds.
Its percentile interval is exploratory: exchangeable state clusters are a
working assumption and cross-state spatial correlation is not removed.
It does not validate causal effects, survey selection or independent counties.

## Geographic check and interpretation

No state exceeds the registered 25% dominance trigger. Largest Established
share: state FIPS 18 (Indiana), **6.89%**; largest Reported share: state FIPS 48
(Texas), **9.26%**. No leave-dominant-state-out run was triggered.

Registered within-state descriptors require >=10 counties in each group.
**17 states** qualify: superiority is below 0.5 in **7** and above 0.5 in **10**,
range **0.3023–0.6156**. For example, state FIPS 26 (Michigan) has 56 / 14
counties and superiority 0.3023; FIPS 37 (North Carolina) has 63 / 14 and 0.6156.
This is descriptive heterogeneity, not an adjusted common effect or a new
family of significance tests. The pooled lower-SVI pattern is not uniform
within states; geographic composition must remain visible in later research.

Point |superiority−0.5| = **0.123051** meets the prespecified material cutoff
0.10. The interval implies rank magnitudes **0.063522–0.174106**, spanning the
SMALL and MATERIAL categories. The registered
`category_supported_by_interval_and_sensitivity` flag is **false**. Report the
point category as descriptive only; do not call the magnitude confidently
material or infer equivalent distributions from a near-neutral rank statistic.

## Decision and boundaries

There is a useful pooled descriptive association in this published positive-
evidence cohort, with uncertain magnitude and substantial within-state
heterogeneity. No confident categorical magnitude decision is supported.
SVI merits contextual, geography-aware investigation relative to vector status;
this does not establish confounding causally, feature independence, incremental
predictive value or promotion to ML. Product: retain source states and geography
and avoid implying that lower SVI causes stronger establishment evidence,
surveillance quality, Lyme disease or individual/local exposure risk.
Do not generalize this positive-only cohort to unreported/Unknown counties.

The earlier DEV release September 17 was genuinely NOT_ESTIMABLE (all Unknown).
The earlier PROD summary omitted species/raw SVI; a one-county public detail
probe established field availability only. Neither justified source-level
absence or the private-authority prerequisite for published-projection EDA.
Those scoped checks/digests and correction history remain in Git and the spec;
they are superseded as the primary input by the authorized frozen PROD capture.

No further source acquisition, training, score change, web change or deployment
is proposed. Keep the draft PR and single comment ready for independent current-
head review; no issue posting, merge or closure before that review.

## Reproduction and retained evidence

Reuse the private immutable local capture; do not repeat a warehouse export or
upload rows. Context and capture must match the digests above. To screen and
replay the already committed selection from this repository:

```powershell
uv run python scripts/eda62_prod_projection.py --capture $env:EDA62_PROD_CAPTURE --context $env:EDA62_PROD_CONTEXT --mode screen
uv run python scripts/eda62_prod_projection.py --capture $env:EDA62_PROD_CAPTURE --context $env:EDA62_PROD_CONTEXT --mode analyze --selection-commit 114ccc0aa7f73427f9b5ead1808c0b2bd00d772b
uv run pytest tests/test_eda62_analysis.py tests/test_eda62_availability.py tests/test_eda62_capture_gate.py tests/test_eda62_prod_projection.py -q
uv run python scripts/verify.py
```

[Projection replay](../../scripts/eda62_prod_projection.py) enforces capture
byte digest, context, canonical FIPS, ordered unique counties, row and pointer
release/bundle consistency, recognized species states and a committed selection
record before outcome execution. [Core statistics](../../scripts/eda62_analysis.py)
are pure offline code. The optional capture SQL is for explicitly authorized
replay only, with context first and all stdout redirected to ignored private
outputs. No connection selector/credential is committed. Analysis-result JSON
SHA-256: `9db81fb1f10b9c77bac61a2d927b1517f5c444ca18dd3d693983c809d86bdf6c`.
One local replay produced the identical result-byte digest; no warehouse reread.
The four focused issue suites passed **50 tests** on explicit synthetic
safety/math fixtures, separate from actual source cohort/result evidence.

Verification is recorded in the PR/final exact-head handoff. Tests distinguish
fictional fixtures from actual consumer counts and cover math/ties, geographic
uncertainty, no outcome-driven selection, zero/sentinel handling, duplicates,
input digests, commit/context gates and bounded/private acquisition. Current
native source-validation/ML-admission proof is not claimed. Raw captures,
context/profile/result JSON, caches and virtual environment remain ignored and
uncommitted; only aggregate conclusions and reusable code/SQL are retained.
