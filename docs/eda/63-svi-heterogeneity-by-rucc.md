# EDA #63: SVI heterogeneity by RUCC

**Disposition: DISTINCT_CONTEXT**, limited to the observed contextual relationship.
Retain both as candidate families; later spatially held-out ablation is required
to establish incremental predictive value or redundancy. This is not final
feature selection, causal inference, diagnosis or individual-risk evidence.

[Specification](63-analysis-spec.md) commit `c5c5d0c` registered the question,
estimand, exclusions, method, sensitivity and interpretation before joint outcome
inspection. Amendment `5caf499` substituted the available published September 17
DEV release for September 18 before obtaining joint values. No result-driven
groups or methods were selected.

## Finding and decision

Overall SVI differs modestly across official RUCC categories, with broad spread
and overlap within groups. Tie-corrected Kruskal–Wallis **H = 127.765083**, **k=9**,
**N=3,144**; rank epsilon squared `max(0,(H-k+1)/(N-k))` = **0.038203**.
This is a rank effect, not percent of raw SVI variance explained. The relationship
is not monotonic across codes: code 9 median is 0.4190 while codes 4 and 5 medians
are 0.5842 and 0.6352. Categories combine metro-area size, county urban population
and adjacency; codes are not a continuous rurality score. The distinct definitions
and within-group variation justify preserving both candidate families for later
experiments; neither redundancy nor utility for a predictive target is established.

State-block bootstrap sensitivity interval: **[0.023561,0.069503]**, 2,000 valid
replicates, zero skipped, seed 6302026, 51 state/DC blocks. This is **not a
spatially validated confidence interval**. Leave-one-state-out effects range
**0.034079–0.043234**. The release is a finite county census; no IID chi-square
p-value or population-significance claim is reported. State blocks do not remove
interstate metro dependence or neighboring-county dependence across state lines;
ACS estimation uncertainty is not propagated.

**Post-hoc: not performed.** Effect 0.038203 falls below the registered 0.05
exploratory materiality screen, so pair comparisons are not justified. No pairs
were selected and no additional inferential family tested. The screen is an
operational choice, not a scientific definition of predictive redundancy.

## Source-faithful groups and summaries

[USDA ERS official documentation](https://www.ers.usda.gov/data-products/rural-urban-continuum-codes/documentation)
was checked 2026-10-04. Metro codes use total metro-area population; nonmetro
codes use county urban population and adjacency. The 2023 lower urban threshold
is 5,000, not the historical 2,500. All groups meet the registered 20-county
support screen. SVI is the national overall percentile on [0,1], not a percent.

| RUCC | Official category, abbreviated | County N | Mean SVI | Median SVI | Q25–Q75 |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | Metro area population ≥1 million | 443 | 0.4133 | 0.3688 | 0.1688–0.6499 |
| 2 | Metro area population 250,000–<1 million | 385 | 0.5186 | 0.5488 | 0.3086–0.7432 |
| 3 | Metro area population <250,000 | 358 | 0.4994 | 0.4946 | 0.2529–0.7421 |
| 4 | Nonmetro urban population ≥20,000, adjacent | 201 | 0.5819 | 0.5842 | 0.3856–0.8072 |
| 5 | Nonmetro urban population ≥20,000, nonadjacent | 76 | 0.6011 | 0.6352 | 0.3889–0.8196 |
| 6 | Nonmetro urban population 5,000–<20,000, adjacent | 379 | 0.5745 | 0.5832 | 0.3425–0.8298 |
| 7 | Nonmetro urban population 5,000–<20,000, nonadjacent | 247 | 0.5563 | 0.5883 | 0.3411–0.7737 |
| 8 | Nonmetro urban population <5,000, adjacent | 466 | 0.5021 | 0.5176 | 0.2447–0.7549 |
| 9 | Nonmetro urban population <5,000, nonadjacent | 589 | 0.4391 | 0.4190 | 0.1788–0.6732 |

The prespecified metro/nonmetro sensitivity (1–3 / 4–9) has N=1,186 / 1,958,
means 0.473495 / 0.516045, medians 0.46625 / 0.51815 and IQRs
[0.226075,0.716625] / [0.2654,0.7680]. Descriptive only, no second test.
Kruskal–Wallis addresses distributions, not just medians without common shapes.

## Units, missingness and limits

Source units are SVI county features and RUCC county/attribute records. Native
source observation-row counts are **not measured** by the county projection,
never replaced with county N or fictional test counts. Observed projection:
**3,144 rows, 3,144 unique canonical counties**, 50 states plus DC including
county equivalents, exact FIPS-set match, no duplicates or missing joins.
Eligible N **3,144**, exclusions **0**: null/nonfinite/out-of-range SVI **0**,
null/noninteger/non-codebook RUCC **0**, jointly invalid **0**. Missing-by-group
counts are zero. SVI zero and one remain observed valid values.

The numeric presentation view does not expose native value-state literals or
quality flags. Counts describe projected null/invalid values, not proof of no
upstream uncertainty. No imputation or unknown-to-negative conversion occurs.
Equal county weight; separate ACS population is not selected or weighted.
Outcome state is **ESTIMATED_DESCRIPTIVELY**, not BLOCKED_ACCESS, STOP or
scientific NOT_ESTIMABLE. The initial September 18 filter returned no rows,
an availability mismatch rather than N=0 for this analysis.

SVI 2022 aggregates ACS 2018–2022; RUCC 2023 uses June 2023 OMB categories and
older census/commuting inputs. This vintage mismatch prevents same-year,
longitudinal or prediction-cutoff claims. Connecticut planning regions and
independent cities are retained by canonical FIPS. No name crosswalk or territory
extrapolation. County-level association cannot establish conditional predictive
value for any later target.

## Provenance and bounded acquisition

Acquired 2026-10-04 UTC through the existing `snow` CLI DEV read route. Context
passed: user `MATTHEWCARAWAY`, role `OH_LYME_DEV_READ`, database
`ONE_HEALTH_LYME_GAP_ATLAS_DEV`, schema `PRESENTATION`, warehouse
`OH_LYME_DEV_INGEST_XS_WH`. Only objects read: DEV
`PRESENTATION.CURRENT_RELEASE_V`, `PRESENTATION.CURRENT_SOURCE_METADATA_V` and
`PRESENTATION.CURRENT_COUNTY_ATLAS_V`. No internal/raw tables, production writes,
ingestion, grants, training, stronger connection or paid model calls.

[SQL](../../sql/datasets/eda63_svi_rucc.sql) uses a session-only 30-second timeout
per statement and limits three SELECT results to 1 release, 10 metadata rows and
3,145 minimal county rows (overflow sentinel). Preliminary zero-row access and
unavailable-release checks produced no usable cohort. All local statistical
replays use the one retained usable snapshot; no repeated warehouse scans.

- Release `governed-2026-09-17-unknown-coverage`, schema `1.0.0`, methodology
  `semantic-1.0.0`, live generated timestamp `2026-09-17T12:00:00-07:00`.
- Bundle SHA-256 `55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`
  matches data-owned `docs/contracts/alpha-parity/governed-2026-09-17-unknown-coverage-report.json`.
  Historical report approval fields are PENDING; the current published view
  demonstrates publication, not scientific review or a new approval claim.
- Historical source manifest at data commit
  `731cd6f5f8dcf6f26499619eac8a7c5099369906`:
  `docs/contracts/semantic-release/governed-2026-09-15-manifest.json`.
  Current manifest names September 18 and must not be substituted. Historical
  manifest timestamp differs from live timestamp; the live release/digest and
  matching parity report anchor execution identity.
- SVI resource `cdc_atsdr_svi_2022_county`, definition v1,
  dataset `atsdr-svi-2022-county-layer`, source version
  `86bed331-992b-4627-a992-ca4c5da7f392`, run
  `9c13471a-e763-4864-bb69-5264b4800e34`, artifact
  `cdc_atsdr_svi_2022_county:dc042342a2e5abc108af67b439ec04c8`, SHA-256
  `dc042342a2e5abc108af67b439ec04c86da8b61f9bdd1cf1b1e5ee0462dea7b2`.
- RUCC resource `usda_ers_rucc_2023`, definition v1,
  dataset `rural-urban-continuum-codes-2023`, source version
  `84da74ac-e153-4fa1-9809-848c93eb12a7`, run
  `6fad7869-a188-47dd-972b-dee0464321b1`, artifact
  `usda_ers_rucc_2023:ec455ee2a8bc5fc8e070575ea5bee7dc`, SHA-256
  `ec455ee2a8bc5fc8e070575ea5bee7dce46fc6037f8c3449cbf56e8b45331fa7`.
- Source tuples above are historical-manifest evidence, not independently
  reread source-row lineage. Publisher bytes were not reacquired or rehashed.
- Canonical artifact at inspected data HEAD
  `eb984723080c9ff3a3484a6d30f9adb0197bd847`:
  `docs/contracts/county-identity-geometry/canonical-county-fips-2022.txt`.
  Raw bytes SHA-256 `5ece91bea37fb35297f5ea312f23f4a8087a6a8823ab4013d8bd8cce0bc005a5`;
  sorted UTF-8/LF FIPS plus trailing newline SHA-256
  `f2651ec6a9375476e3ff09efb4c2a699cd5690ffd3f0c982aeacad967c21c241`.
- Retained CLI snapshot SHA-256
  `601d3e9ce841b523e84dc1be3de6c1f53c33545aa5ea6aaa32a94a2f7ba3e999`;
  selected projection canonical JSON SHA-256
  `011bab4449c3a0bd2ea2dda10c68aa76033b0ae910a954a54221f30c99ac9b6c`.
  Canonical JSON uses sorted keys and separators `,` and `:`. Replay rejects
  changed release, bundle, canonical identity or projection. CLI formatting may
  vary; the normalized projection digest is stable for the selected values.

## Reproduction and verification

Python 3.12.13, committed `uv.lock`, standard-library [core](../../src/lyme_gap_atlas_ml/eda63.py)
and file-I/O [entry point](../../scripts/eda63_svi_rucc.py). From the ML checkout:

```powershell
uv sync --extra dev
New-Item -ItemType Directory -Force outputs | Out-Null
# Select an existing authorized local DEV read PAT connection privately.
snow sql -c $env:SNOWFLAKE_CONNECTION_NAME --database ONE_HEALTH_LYME_GAP_ATLAS_DEV --schema PRESENTATION -q 'SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE()' --format JSON
# Proceed only if all five context fields match the DEV scope above.
snow sql -c $env:SNOWFLAKE_CONNECTION_NAME --database ONE_HEALTH_LYME_GAP_ATLAS_DEV --schema PRESENTATION -f sql/datasets/eda63_svi_rucc.sql --format JSON > outputs/eda63-source.json
uv run python scripts/eda63_svi_rucc.py --snapshot outputs/eda63-source.json --canonical-fips ../one-health-lyme-gap-atlas-data/docs/contracts/county-identity-geometry/canonical-county-fips-2022.txt > outputs/eda63-result.json
uv run pytest tests/test_eda63.py
uv run python scripts/verify.py
```

For detached worktrees, supply the data artifact path via `--canonical-fips`.
Prefer retained-snapshot replay. If the current pointer moves, checks stop;
access to the old release through a current view is not guaranteed. Independent
review should replay the retained snapshot and verify its digests.

Tests cover known ranks/ties, zero/missing/invalid outcomes, identity/release
rejection, canonical digest, group support and deterministic bounded state
resampling. Fictional tests are not cohort evidence. Required offline checks
and exact review head are in the PR. Snapshot and result JSON, extracts and
caches remain ignored and uncommitted. Independent review, the single issue
comment, merge and closure remain pending; this does not satisfy the merged
evidence gate until reviewed and merged.

## Parent-requested shared consumer capture for ML #61–65

After the ML #63 result, the parent requested one shared capture to prevent
sibling exports. [Shared SQL](../../sql/datasets/eda63_shared_consumer_capture.sql)
and [manifest validator](../../scripts/eda63_shared_manifest.py) capture the
existing authorized DEV consumer boundary, including **before and after**
release rows, full public source/measure metadata and 17 selected atlas fields.
The additional outcomes were selected from existing contracts and captured
without examining their statistics. SVI/RUCC had already been analyzed above;
this is not a claim of blindness to those two fields.

The actual capture has **3,144 rows / unique canonical FIPS, 5 source metadata
rows, 14 measure metadata rows**. Before/after release identity and bundle hash
are identical, all metadata release versions agree, and its five-field SVI/RUCC
subprojection exactly matches the earlier retained snapshot. Context was
reverified and the validator checks the captured five-field context file.

The bounds are 30 seconds per statement, five SELECTs with limits
1 / 10 / 100 / 3,145 / 1, maximum 150 seconds of SQL execution. It reads the same
three views plus `PRESENTATION.CURRENT_MEASURE_METADATA_V`; no private tables,
alternate role, PROD query or production mutation. Existing capture is retained;
this extension is the one additional shared projection, not five sibling exports.

Retained local evidence, ignored and not committed:

- `outputs/eda-shared-20261004-dev-consumer.json`, SHA-256
  `be74f3affff2e7753f14e7b804d672fb83d21eabe8f1dc4abead873ea21e8e45`.
- `outputs/eda-shared-20261004-dev-manifest.json`, sanitized manifest containing
  release/context/row bounds, digests and scope limitations; no connection selector.
  SHA-256 `5a950471806ad3247cb4fa8ef90c888506c56afbcd1f02772dbf25517aa9bd33`.
- `outputs/shared-consumer-context.json`, actual context proof and successful
  zero-row metadata access check. The manifest records its byte digest.
  SHA-256 `e7d83efe86daf7343dbfc213e1e129bb6c6ac23f78be47ea95abffc5502e6f92`.
- Normalized full county projection SHA-256
  `5b59f2557221c570719f51d1b7cedb612ae1dd31981a35459ce5d2f42f208daa`.
- Normalized public source/measure metadata SHA-256 respectively
  `ad3c446bf87d9a39bc069b5684a7cfb71b38984147741559f0a365dbc78e0bb4` /
  `705d8aea205e4abf08540638d73a61a0482d1c9581581447178d38648beeface`.

The county fields are release/FIPS/state, ACS population, SVI and uninsured
percentile/percent, RUCC, human status, **2023** human case/incidence floors,
state-unallocated records, tick/scapularis/pacificus/burgdorferi statuses and
evidence completeness. There is **no 2022 human numerator**; #61 must not use
the 2023 field instead. Newly added status/outcome values are not profiled here;
historical Unknown coverage is not treated as proof of current absence.

```powershell
# Reuse the existing immutable capture, do not repeat acquisition per sibling.
uv run python scripts/eda63_shared_manifest.py --snapshot outputs/eda-shared-20261004-dev-consumer.json --context outputs/shared-consumer-context.json
```

[DATA #199 reconciliation](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-domain/story-199-svi-reconciliation-2026-10-02.md)
confirms this existing consumer route and distinct SVI/population/percent units.
[DATA #200 receipt handoff](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/200#issuecomment-5965980365)
narrows historical source-tuple binding for the **PROD September 18** release;
it is not a receipt for this DEV September 17 capture. The current observation
record/hash authority packet and five authoritative REVIEWED metadata envelopes
remain unavailable through this consumer boundary. Public metadata are descriptive
measure envelopes, not the full #191/#193 acceptance proof. Do not infer private
source acceptance or ML feature admission from visible values, a hash shape,
publication status or historical manifest alone. These are separate governance
gaps, not failure to access the SVI/RUCC distributions estimated above. No denied
private-table query was retried to resolve them.
