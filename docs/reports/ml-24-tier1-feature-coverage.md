# ML #24 Tier 1 feature coverage — DEV snapshot

Regenerated 2026-10-05 21:48 MDT (`2026-10-06T03:48:06Z`) from
`tier1-county-features-v1` and governed release
`governed-2026-09-17-unknown-coverage`, bundle SHA-256
`55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`.
This is a local, read-only DEV generation. The matrix CSV is ignored and not
committed. Reproduce with the command in the feature contract.
The revised implementation commit is recorded in PR #100.

| Check | Observed |
| --- | ---: |
| Expected canonical counties | 3,144 |
| Matrix rows / distinct FIPS | 3,144 / 3,144 |
| Duplicate keys | 0 |
| Feature-complete numeric rows | 3,144 |
| Partial evidence rows | 2,493 |
| Not estimable for feature construction | 0 |
| Excluded counties | 0 |

Feature-complete means the selected numeric columns can be constructed; it
does not assert epidemiologic sufficiency or model scoring eligibility. Partial
means no county-linked human record or unknown pathogen coverage. ML #27/#30
must examine that state before deciding score eligibility and interpretation.

| Predictor | Non-null | Missing | Encoded zeros | Distinct values |
| --- | ---: | ---: | ---: | ---: |
| `human_published_floor` | 3,144 | 0 | 2,493 | 2 |
| `human_case_count_floor_log1p` | 3,144 | 0 | 2,493 modeling placeholders | 250 |
| `pathogen_present` | 3,144 | 0 | 2,455 | 2 |
| `pathogen_no_records` | 3,144 | 0 | 724 | 2 |
| `pathogen_unknown` | 3,144 | 0 | 3,109 | 2 |
| `svi_percentile_2022` | 3,144 | 0 | 1 observed numeric zero | 3,082 |

The count-floor source has **651 non-null published rows** and **2,493
no-county-record rows**. Among published rows, raw floor min/median/max is
**5 / 49 / 3,262 cases**; `log1p` min/median/max is
**1.791759 / 3.912023 / 8.090402**. There are **zero observed numeric zero
floors**. Across all matrix rows, transformed min/median/max is
**0.0 / 0.0 / 8.090402**; the 0.0 values are modeling placeholders, not
observations. `human_published_floor=0` and
`human_evidence_state=no_county_linked_record` identify every placeholder.
Published values have `human_published_floor=1`, so an actual published zero
would remain distinguishable if a later reviewed release contained one.

Indicator zeros mean the named category is not present; they are not source
numeric zeros or biological absence. The one SVI zero is a valid source
percentile. SVI range is 0.0–1.0. No selected predictor is constant. The
rare `pathogen_unknown` indicator is 35/3,144; #27 should inspect its score
effect rather than treating it as an outcome.

| Evidence/context state | Distribution |
| --- | --- |
| Human | `published_count_floor` 651; `no_county_linked_record` 2,493 |
| Pathogen | `Present` 689; `No records` 2,420; `Unknown` 35 |
| Vector | *I. scapularis* `Unknown` 3,144; *I. pacificus* `Unknown` 3,144 |
| RUCC context | 1: 443; 2: 385; 3: 358; 4: 201; 5: 76; 6: 379; 7: 247; 8: 466; 9: 589 |

The vector states are constant and excluded. RUCC is retained for slicing,
not a predictor. No priority score, priority tier, derivative of either,
numeric FIPS, state/region predictor, or supervised label was selected. The
query projection names only county FIPS and the governed source fields
needed for the matrix and context; it does not read the deterministic score.
The generator fails on duplicate keys, changed release, unreviewed states,
invalid count floors or SVI/RUCC ranges, and constant selected predictors.

The DEV read role was `OH_LYME_DEV_READ` in
`ONE_HEALTH_LYME_GAP_ATLAS_DEV`, warehouse `OH_LYME_DEV_INGEST_XS_WH`.
No Snowflake object was written. Direct read of `SEMANTIC_DATA_SOURCES` was
denied under this role, so exact source membership is cited through the
immutable release bundle rather than through an unverified table extract.
