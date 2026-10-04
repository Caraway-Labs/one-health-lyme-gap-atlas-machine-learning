# EDA #62: SVI by positive vector evidence state

**DEV disposition: NOT_ESTIMABLE — no positive vector contrast in this release.**
The existing `CURRENT_COUNTY_ATLAS_V` is accessible and retains SVI and tick
fields. Its current DEV release has 3,144 `Unknown` counties for each taxon,
with **ESTABLISHED / REPORTED = 0 / 0** for both. Unknown is not negative.
The initial observation-view-only availability conclusion was too broad;
the county-atlas screen below corrects it. The shared PROD bulk capture lacks
species-specific states and raw SVI; the single public detail probe below
confirms field availability, not cohort N or source-authority admission. This DEV result is
not generalized to PROD or all source evidence. No taxon was selected and no
real SVI distribution/test/effect/interval was computed.

Issue: [ML #62](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/62).
Question: Do counties with stronger source-reported vector establishment evidence
differ in overall SVI from counties with weaker-but-positive evidence?
The [registered specification](../methodology/62-svi-vector-evidence-spec.md)
was committed at `a05e83ccce4e27f717a16dd24f2fe1105bb59dbd` before the live
availability audit. Parent #59 and the #60 analysis-spec contract apply.

## Evidence and scope

On 2026-10-04 UTC, the laptop CLI verified user `MATTHEWCARAWAY`, role
`OH_LYME_DEV_READ`, database `ONE_HEALTH_LYME_GAP_ATLAS_DEV`, schema
`PRESENTATION`, warehouse `OH_LYME_DEV_INGEST_XS_WH`. Secondary roles were NONE.
The initial data object read was
`ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V`.
The audit set a session-only 60-second statement timeout and returned three
aggregate rows under LIMIT 10. No database object was written; no internal
SEMANTIC/RAW/STAGING/CONFORMED object or source artifact was scanned.

| Published measure | Source | Observation rows | Unique county FIPS |
| --- | --- | ---: | ---: |
| case_count_floor_2023 | human | 3,144 | 3,144 |
| human_status | human | 3,144 | 3,144 |
| incidence_floor_2023 | human | 3,144 | 3,144 |

Live release: `governed-2026-09-17-unknown-coverage`.
Profile query ID: `01c77e7b-040b-dea2-0064-2d070110a36e`.
These are **published county-measure observation counts**, not original source
row counts, eligible vector-group N or SVI complete-case N. The same counties
occur in three measures; 9,432 observations are not 9,432 independent counties.
At this initial stage, raw tick/SVI source-row counts, positive-state counts, source missingness,
geography exclusions, duplicate conflicts, and SVI outcome-state counts are all
unknown because their inputs are not published through this route.

The current [Data V127 consumer contract](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-release/current-county-observations-v1.md)
(Git blob `effe7315a908da1e44408a4e821e4b413ad0f40f`) closes its allowlist to
these three human measures. It explicitly excludes cumulative tick status for
lack of a governed start date and ACS context pending an explicit period
contract. It grants no access to release internals or source artifacts. Thus
absence here is **unpublished input**, never biological absence or missing SVI
at the source. The audit does not inspect human outcome values either.

## Corrected existing-consumer-route screen

Parent review identified the preexisting V072 route. The outcome-blind
amendment was committed at `ccb4d0e586a19b18a9d7e2accaa0c23550525997` before
executing [62-county-atlas-screen.sql](../../sql/validation/62-county-atlas-screen.sql).
The same least-privilege DEV context was reverified, with secondary roles NONE.
Only `CURRENT_RELEASE_V`, `CURRENT_SOURCE_METADATA_V` and
`CURRENT_COUNTY_ATLAS_V` were read; each statement had a 60-second timeout.
The screen returned one release row, two source rows, and two taxon/status
aggregate rows, within LIMIT 2/3/12 respectively. No county rows were exported.

Observed DEV release `governed-2026-09-17-unknown-coverage`, schema `1.0.0`,
method `semantic-1.0.0`, served bundle SHA-256
`55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`.
This is the served release digest, not an independently recomputed artifact hash.
Public source metadata reports CDC ArboNET tick status through 2025-12-31 and
CDC/ATSDR SVI 2022 (2018–2022 ACS), with their interpretation notes.

| Taxon consumer field | Exact observed state | County rows / unique FIPS | State/DC codes | Invalid FIPS | SVI null / invalid domain | ESTABLISHED / REPORTED |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| scapularis_status | Unknown | 3,144 / 3,144 | 51 | 0 | 0 / 0 | 0 / 0 |
| pacificus_status | Unknown | 3,144 / 3,144 | 51 | 0 | 0 / 0 | 0 / 0 |

Screen query ID: `01c77e8a-040b-d63b-0064-2d070110986a`.
These are consumer county-status units, not original tick sampling events,
abundance, source-row counts or a negative group. The taxon rows refer to the
same 3,144 counties and must not be pooled as independent units.
Both candidate taxa fail the preregistered positive-state N screen. All 3,144
counties per taxon are excluded as Unknown, not counted as REPORTED, NO_RECORDS
or biological absence. Invalid/sentinel SVI exclusions at this consumer screen
are zero. Full governed value-state/record authority is not exposed by this
aggregate. The 51 geographic codes describe the Unknown cohort only; positive
group concentration and within-state comparison are inapplicable with 0 / 0 N.

The [V072 contract](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-release/README.md)
defines immutable release rows and the accepted DEV Tier D
UNKNOWN_SOURCE_COVERAGE path, which contributes no tick source rows and
renders tick statuses Unknown. This contextualizes the result; the actual
current aggregate, not historical #276 counts, supplies the N evidence above.

The merged [DATA199 audit](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-domain/story-199-svi-residual-audit-2026-10-03.md)
(blob `592748e8274a67370e0d958ebe5bd9d323842a17`) confirms that the atlas route
retains SVI. [DATA200 receipt evidence](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/200#issuecomment-5965980365)
binds historical build/publication receipts to PROD release September 18 and
bundle `038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`,
narrowing source-tuple-to-bundle provenance. Those contributed receipts are
not a current per-observation record/hash/metadata authority packet and do not
establish tick positive-state eligibility. No previously denied private object
was retried; no alternate identity was used for restricted source access.

The parent assigned one shared outcome-blind consumer capture to #63. This
branch verified that input/digest/provenance instead of another row export.
Value visibility, exact source/version/run/artifact/release membership,
canonical county alignment and applicable reviewed metadata admission remain
separate checks before any alternative real-outcome execution.

## Verified shared inputs and bounded PROD detail check

The [capture gate](../../scripts/eda62_capture_gate.py) verifies raw-file
SHA-256 before parsing, stable before/after release identity, 3,144 unique FIPS,
canonical county-set digest, and DEV county/metadata release membership.
Only statuses, identity and field presence were screened; no SVI distributions
or derived score statistics were computed. All row-bearing inputs remain
private in ignored outputs; none is committed or uploaded.

| Shared input | Raw-file SHA-256 | Issue-specific conclusion |
| --- | --- | --- |
| DEV consumer capture | be74f3affff2e7753f14e7b804d672fb83d21eabe8f1dc4abead873ea21e8e45 | September 17 release/bundle above; both taxa Unknown in all 3,144 counties; independently reproduces 0 / 0 positive-group N. |
| PROD public scores summary | 5dbc0e4a66e1d702b5deafc3a430d62fe317984a6ee2e5c1759b74182f06e9ed | September 18 release/bundle above; no scapularis_status, pacificus_status or raw svi_percentile in its county projection. Species group N is unknown, not zero. |
| PROD public capture manifest | 1691467c100965fb6d5beb413179d4769dc51451cfb9424c8cd1df97186d0315 | Five public responses; stable before/after release/hash; cache consistency is not a warehouse transaction or private authority proof. |

Both county captures match canonical FIPS normalized SHA-256
`f2651ec6a9375476e3ff09efb4c2a699cd5690ffd3f0c982aeacad967c21c241`.
The PROD summary's combined `tick_status` is not species-specific evidence and
its derived `score` components cannot replace raw overall SVI. No substitution,
taxon selection or PROD scientific NOT_ESTIMABLE claim was made.

The documented [API detail contract](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-api/blob/main/src/lyme_gap_atlas_api/models.py)
and service expose species states and raw `svi_percentile` via
`GET /v1/counties/{fips}`. A **single** anonymous fixed-county probe used
`https://api.carawaylabs.com/v1/counties/01001?dataset_version=governed-2026-09-18-unknown-coverage`,
30-second timeout and 1 MB response limit. Response length 5,117 bytes,
SHA-256 `54b38cbd3de770f3a64b0eea6c24daf7bda5a5fd03cb5b46422605bd138942c6`.
Its nested release/hash match the shared PROD identity. All three needed fields
exist; their outcome values were not summarized or used for selection.
One probe is not a representative cohort or proof of adequate species N.
The response is retained only privately/ignored, without further county crawl.
[Probe code](../../scripts/eda62_detail_probe.py) fixes the endpoint and bounds,
restricts writes to this worktree's ignored outputs, and prints field/identity
evidence without raw outcome values.

Detail source metadata fields are `key`, `label`, `vintage`, `url`, `note`.
They do not expose current source-version/run/artifact/record-hash anchors or
reviewed metadata-state admission. The exact remaining input is a **bounded
approved immutable cohort projection** with canonical county/state,
taxon-specific source statuses and national overall SVI for enough counties
to screen the registered contrast, tied to the same release/hash and applicable
source/vintage/record/metadata authority. Existing historical receipts narrow
that provenance requirement; they are not ignored or presented as nonexistent.
The visible public detail fields establish a potential route, not permission
for a broad acquisition or a replacement for the parent's coordinated packet.

## Planned sources and method; not executed

The governed [manifest](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-release/governed-2026-09-15-manifest.json)
(Git blob `ef7e08c2919d38bdf6bdaa8ef79316b1bafd00f5`) identifies candidate
CDC sources below. Despite its filename, this manifest declares release
`governed-2026-09-18-unknown-coverage`, **different from the live release**.
These identities are documentary candidate provenance, not a verified linkage
to any analyzed live tick/SVI data. Freeze a matching release before resuming.

| Source | Definition | Source-version ID | Ingestion-run ID | Artifact SHA-256 |
| --- | --- | --- | --- | --- |
| CDC ArboNET cdc-ixodes-county-status-2025, through 2025-12-31 | 1 | b81c116f-d93d-4c6b-9d11-ac2477e0e242 | ec14cc85-85d6-4064-80f1-1354238b88d6 | e35a5066a7c77b2e79c50f315a18e042405ab7baa8a414a1a907792bb25d2adc |
| CDC/ATSDR atsdr-svi-2022-county-layer, ACS 2018–2022 | 1 | b8b6bf61-c6a3-4538-b0df-1b88c61720b1 | 331f367d-9282-4936-9b49-a480db995016 | dc042342a2e5abc108af67b439ec04c86da8b61f9bdd1cf1b1e5ee0462dea7b2 |

Candidate canonical contrast is ESTABLISHED versus REPORTED for one taxon;
not DETECTED pathogen-test results, pooled taxa, UNKNOWN or NO_RECORDS.
Exact source-to-canonical mappings and adequate unique-county N must be checked
before taxon selection. Legacy alpha snapshot counts and fictional fixtures
cannot supply governed eligible N. No substitution was made.

The registered plan screens IXODES_SCAPULARIS then IXODES_PACIFICUS using only
semantics/geography/positive-state N (>=30 each), then national overall SVI
percentile, county-weighted. Planned Mann–Whitney concerns distributions,
not medians alone; probability of superiority, central tendency and overlap
accompany uncertainty. State shares, dominance exclusions and within-state
checks address geographic concentration. There is no observed concentration
result yet. Independent county inference is not justified by county N alone.
The spec sets descriptive-only and NOT_ESTIMABLE limits when dependence-aware
inference cannot be supported. No causal or individual-risk inference is allowed.

Independent-review interpretation amendment was committed at
`df1fa7914647f35120deaac841128feb0b28c6cd` before real outcomes. Near-0.5
superiority supports little directional rank difference, not distribution
equivalence. IQR/range/common-range overlap and empirical CDF distance must
remain visible. The executable [offline pipeline](../../scripts/eda62_analysis.py)
implements outcome-blind taxon screening, distinct complete-case exclusions,
tie-adjusted/continuity-corrected Mann–Whitney, probability of superiority,
rank-biserial effect, central/spread/overlap descriptors, whole-state bootstrap
(seed 62, 2,000 draws), state shares, dominant-state exclusions and within-state
descriptors. It does not supply source authority or scientific admission.
The county-independence p-value is labelled ancillary and spatially unadjusted.
Synthetic regression tests include {0.1,0.9} versus {0.4,0.6}, whose superiority
is 0.5 despite different spreads. No such fixture replaces real cohort counts.

## Decision and next step

Keep #62 open pending independent review and the precise alternative
cohort-projection/source-authority input above.
The current DEV release is NOT_ESTIMABLE for this positive-state contrast,
without implying a zero effect or source-level biological absence. If an
approved alternative cohort projection has positive groups, validate its immutable source,
temporal/metadata and county authority and screen N before selecting a taxon.
Commit selection and matching source/capture identity before SVI summaries.
This work changes no shared contract/grant or source definition.

ML implication: no evidence yet that SVI confounds or adds information relative
to vector status. Product implication: no change to vector-evidence or SVI
interpretation. No material/small/no-difference claim follows from zero positive
group availability. DEV NOT_ESTIMABLE is a cohort result; the unresolved
PROD cohort-projection/authority gap is a separate access/provenance dependency.

## Reproduction and verification

From this repository, with an already selected least-privilege local connection:

```powershell
snow sql -c $env:SNOWFLAKE_CONNECTION_NAME --schema PRESENTATION --secondary-roles NONE -q 'SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE()' --format JSON
# Compare all five fields to the authorized DEV context before continuing.
New-Item -ItemType Directory -Force outputs | Out-Null
snow sql -c $env:SNOWFLAKE_CONNECTION_NAME --schema PRESENTATION --secondary-roles NONE -f sql/validation/62-vector-svi-availability.sql --format JSON | Tee-Object -FilePath outputs/62-availability-cli.txt
$audit62Raw = Get-Content outputs/62-availability-cli.txt -Raw | ConvertFrom-Json
$audit62Raw[1] | ConvertTo-Json | Set-Content outputs/62-profile.json -Encoding utf8
uv run python scripts/eda62_availability.py outputs/62-profile.json
# Existing completed aggregate screen; do not repeat warehouse reads when using shared capture.
# Its CLI output is ignored outputs/62-county-atlas-screen-cli.txt.
$screen62Raw = Get-Content outputs/62-county-atlas-screen-cli.txt -Raw | ConvertFrom-Json
$screen62Raw[3] | ConvertTo-Json | Set-Content outputs/62-atlas-screen.json -Encoding utf8
uv run python scripts/eda62_availability.py outputs/62-atlas-screen.json --atlas-screen
# Paths select the parent's existing private read-only captures; no recapture.
uv run python scripts/eda62_capture_gate.py --dev $env:EDA62_SHARED_DEV --prod $env:EDA62_SHARED_PROD --prod-manifest $env:EDA62_SHARED_PROD_MANIFEST
uv run pytest tests/test_eda62_analysis.py tests/test_eda62_availability.py tests/test_eda62_capture_gate.py -q
uv run python scripts/verify.py
```

SQL SHA-256 (LF UTF-8):
`da8f2baad19a8f0643b8687e106d93312580e39c22500b26dd1992e1d6cef887`.
Observed transient profile-byte SHA-256:
`3ee71bb02a1b2492dc580973532c7ebdd9916261ca9254fd42969b0b1236e337`.
JSON whitespace may change the latter; the table above retains substantive
evidence. The current pointer can advance, so a fresh audit must report its own
release and cannot silently reproduce historical identity from the pointer.

County-atlas screen SQL SHA-256 (LF UTF-8):
`0b401630102e45e9250e0cdacda10c369e41191a329afd00d181059ba29d6220`.
Observed screen-profile bytes SHA-256:
`abff779d6db3bbf15112d370f3a10d66c89a0c5091fa465d98d87dbb7cb46ad0`.
Screen SQL is for approved replay only; the existing aggregate plus the parent's
shared capture should be reused without repeated warehouse scans.

Mandatory checks passed: contracts/skills/lifecycle/hygiene, Ruff, format,
mypy, **181 pytest tests passed** after the shared-input gate addition, one
optional Arize SDK skip. Updated focused suites pass **44 tests** covering
view-scoped exclusions, Unknown-versus-positive N safety, publication-versus-eligibility,
single-taxon availability, ambiguous/truncated input, mixed releases,
duplicates, invalid counts, tie/math calculations, bootstrap reproducibility,
insufficient independent states, no outcome-driven taxon switching, zero/sentinel
semantics, geographic dominance and the rank-neutral unequal-spread case.
New gate tests cover digest substitution, canonical set versus mere shape/count,
duplicate identities, combined-versus-species semantics, changed release identity,
single-request bounds, ignored/private output and no raw-outcome stdout.
Test profiles are explicitly fictional and
were never used as analysis evidence. No predictive model/experiment/holdout
was created. Live context/profile evidence is separate from offline test proof.

Transient CLI output/profile JSON, caches and virtual environment are ignored
and intentionally not committed. No raw data export, credentials, production
write, paid model call, training, web change, posting, merge or closure occurred.
The [single issue comment draft](62-issue-comment-draft.md) awaits owner review.
