# 111: Where do human, tick, and pathogen documentation states disagree?

- Issue: [ML #111](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/111), part of [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Question: which documentation gaps are reporting or source-coverage artifacts, and which remain a follow-up list?
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`, and `CURRENT_SOURCE_METADATA_V`. Pinned release `governed-2026-10-15-january-climate-prod`.
- Cohort: one row per county on that release, including the District of Columbia, Connecticut planning-region FIPS, Alaska, and Hawaii. Rows read: 3144. Vulnerability rescaled by 100: no.

## Method and assumptions

Spec [111-cross-signal-disagreement/v1](111-analysis-spec.md), frozen before any disagreement count. The contract residual, score, and flag are absent. The class rules, the publishing-state cohort, seeds `1112026` and `1112027`. The disposition rule is in the spec. State counts are points. National and Census-region counts use the #116 state-cluster percentile interval. Holm adjusts the four publishing-state tail shares when every interval is estimable. Benjamini-Hochberg is not used.

## Material findings and limits

October 13 comparison, exact integers:

| Check | Observed | Reference |
| --- | ---: | ---: |
| counties | 3144 | 3144 |
| published_floor | 651 | 651 |
| no_county_linked_record | 2493 | 2493 |
| positive_cdc_no_human | 1269 | 1269 |
| human_without_vector | 25 | 25 |
| unknown_or_out_of_scope | 35 | 35 |
| double_gap | 228 | 228 |
| established_tick_gap | 810 | 810 |
| zero_floor_states | 19 | 19 |

Zero-floor state set matches the nineteen-state list: yes (19 states).

Documentation classes:

| Class | Counties |
| --- | ---: |
| insufficient_unknown | 35 |
| human_without_vector_documentation | 25 |
| double_gap | 228 |
| established_no_pathogen_record | 582 |
| reported_pathogen_present | 16 |
| reported_no_pathogen_record | 442 |
| pathogen_without_tick_record | 1 |
| concordant_undocumented | 1189 |
| concordant_documented | 626 |

Double-gap counties explained by a zero-floor state: 9. Double-gap follow-up counties, in states that publish a floor: 219. Human floor with neither tick nor pathogen record: 25. Unknown or out of scope, unranked: 35.

Publishing-state associations. The interval is the state-cluster percentile interval.

| Contrast | Estimate | Low | High | Holm | Material sensitivity |
| --- | ---: | ---: | ---: | ---: | --- |
| h1_metro_share_diff | -0.1043 | -0.1757 | -0.0306 | 0.0160 | yes |
| h2_svi_share_diff | -0.1617 | -0.2869 | -0.0305 | 0.0300 | yes |
| h3_spearman_rucc | 0.0997 | 0.0128 | 0.1843 | 0.0300 | yes |
| h4_spearman_log_population | -0.1722 | -0.2835 | -0.0612 | 0.0180 | yes |

Companion Cramér's V for the metro table, not a test: 0.1042. Holm family was applied.

False-positive review, smallest FIPS in each prespecified group. These rows illustrate the flag. They are not a rank.

### Double gap in a state that publishes no county floor

- Liberty County, GA (13179): double_gap, reading reporting_artifact. Tick Established; pathogen Present; human no_county_linked_record. population 65550. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.
- McIntosh County, GA (13191): double_gap, reading reporting_artifact. Tick Established; pathogen Present; human no_county_linked_record. population 11183. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.
- West Feliciana Parish, LA (22125): double_gap, reading reporting_artifact. Tick Established; pathogen Present; human no_county_linked_record. population 15358. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.

### Human floor with neither tick nor pathogen record

- Pima County, AZ (04019): human_without_vector_documentation, reading source_coverage. Tick No records; pathogen No records; human published_count_floor. population 1042393. Supporting `human_published_floor`. Gap tokens `tick_no_records,pathogen_no_records`.
- Baltimore City, MD (24510): human_without_vector_documentation, reading source_coverage. Tick No records; pathogen No records; human published_count_floor. population 584548. Supporting `human_published_floor`. Gap tokens `tick_no_records,pathogen_no_records`.
- Mecosta County, MI (26107): human_without_vector_documentation, reading source_coverage. Tick No records; pathogen No records; human published_count_floor. population 40128. Supporting `human_published_floor`. Gap tokens `tick_no_records,pathogen_no_records`.

### Double gap in a state that publishes a county floor

- Butte County, CA (06007): double_gap, reading follow_up. Tick Established; pathogen Present; human no_county_linked_record. population 213605. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.
- Calaveras County, CA (06009): double_gap, reading follow_up. Tick Established; pathogen Present; human no_county_linked_record. population 45674. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.
- Colusa County, CA (06011): double_gap, reading follow_up. Tick Established; pathogen Present; human no_county_linked_record. population 21811. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.

### Region counts

| Class | Northeast | Midwest | South | West |
| --- | ---: | ---: | ---: | ---: |
| insufficient_unknown | 0 | 0 | 0 | 35 |
| human_without_vector_documentation | 0 | 6 | 18 | 1 |
| double_gap | 0 | 158 | 42 | 28 |
| established_no_pathogen_record | 1 | 126 | 396 | 59 |
| reported_pathogen_present | 0 | 7 | 9 | 0 |
| reported_no_pathogen_record | 0 | 112 | 315 | 15 |
| pathogen_without_tick_record | 0 | 0 | 1 | 0 |
| concordant_undocumented | 0 | 414 | 475 | 300 |
| concordant_documented | 217 | 232 | 166 | 11 |

A 1–10 cell is exact in this write-up and suppressed in the lab metrics and charts. State counts are in `EDA.METRICS_LONG` for this run, with that suppression.

## Decision

**INVESTIGATE.** The October 13 counts match, and 219 double-gap counties sit in states that publish a county floor. That residual list is the follow-up candidate set in `EDA.CROSS_SIGNAL_CANDIDATES_111` where `REVIEW_READING` is `follow_up`. It is a review list, not a score. Advance is not available from this run: epic #22 says to inspect and not to rank by risk, and a public map or workflow needs a separate review. Keep the lab table for analyst inspection of the follow-up rows. Do not train a model on the class or the reading.

## Reproduction and retained evidence

- Code revision/run: `1b76baf9689bfacc5e12f09b888bb410344c7fcc`, run `111-cross-signal-disagreement-20261026T0238Z`, spec `111-cross-signal-disagreement/v1`.
- Entry points: `sql/validation/111_cross_signal_disagreement.sql`, `scripts/eda_111_cross_signal.py`, `src/lyme_gap_atlas_ml/cross_signal_disagreement.py`.
- Commands: `uv run python scripts/check_ml_agent_context.py`, then `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_111_cross_signal.py`, then `uv run python scripts/verify.py`.
- Lab row counts: `REGISTRY.RUNS` 1, `EDA.METRICS_LONG` 1040, `EDA.FINDINGS` 3, `REGISTRY.QUERIES` 4, `EDA.CROSS_SIGNAL_CANDIDATES_111` 1294, `REGISTRY.ARTIFACTS` 2.
- Drive: folder https://drive.google.com/drive/folders/191hhct-v-vch7tHVmcTO1iPO1WTDXs4_ ; state-review-counts.png https://drive.google.com/file/d/1HmzHz-NpIFQzbJlzzqfInWRExG_92ah1/view (13093 bytes; Drive metadata size matches the local PNG). disagreement-type-matrix.png https://drive.google.com/file/d/1Jpw5rGYfsVSKiVZ14QNx0CJab2mlbgbU/view (28831 bytes; in the issue-111 Drive folder and registered in REGISTRY.ARTIFACTS).
- Transient artifacts intentionally not committed: PNG files under `artifacts/charts/111/` and any in-memory county rows. Candidate rows stay in `EDA.CROSS_SIGNAL_CANDIDATES_111`. No county extract was committed.

## 1. Question

Where do the published human, tick, and pathogen documentation states disagree, and which part is a state-reporting or source-coverage artifact rather than a follow-up candidate?

## 2. Method

Spec [111-cross-signal-disagreement/v1](docs/eda/111-analysis-spec.md), frozen before the counts. The numeric residual in the cross-signal disagreement contract is not computed: the three signals are not on one approved comparison scale. Classes come from `HUMAN_STATUS`, `TICK_STATUS`, and `BURGDORFERI_STATUS`. `No records` and `Unknown` stay unobserved. A missing human floor is not zero. Associations use the #116 state-cluster bootstrap and Holm step-down on states that publish at least one county floor. Seeds 1112026 and 1112027.

## 3. Key findings

October 13 comparison, exact integers:

| Check | Observed | Reference |
| --- | ---: | ---: |
| counties | 3144 | 3144 |
| published_floor | 651 | 651 |
| no_county_linked_record | 2493 | 2493 |
| positive_cdc_no_human | 1269 | 1269 |
| human_without_vector | 25 | 25 |
| unknown_or_out_of_scope | 35 | 35 |
| double_gap | 228 | 228 |
| established_tick_gap | 810 | 810 |
| zero_floor_states | 19 | 19 |

Zero-floor state set matches the nineteen-state list: yes (19 states).

Documentation classes:

| Class | Counties |
| --- | ---: |
| insufficient_unknown | 35 |
| human_without_vector_documentation | 25 |
| double_gap | 228 |
| established_no_pathogen_record | 582 |
| reported_pathogen_present | 16 |
| reported_no_pathogen_record | 442 |
| pathogen_without_tick_record | 1 |
| concordant_undocumented | 1189 |
| concordant_documented | 626 |

Double-gap counties explained by a zero-floor state: 9. Double-gap follow-up counties, in states that publish a floor: 219. Human floor with neither tick nor pathogen record: 25. Unknown or out of scope, unranked: 35.

Publishing-state associations. The interval is the state-cluster percentile interval.

| Contrast | Estimate | Low | High | Holm | Material sensitivity |
| --- | ---: | ---: | ---: | ---: | --- |
| h1_metro_share_diff | -0.1043 | -0.1757 | -0.0306 | 0.0160 | yes |
| h2_svi_share_diff | -0.1617 | -0.2869 | -0.0305 | 0.0300 | yes |
| h3_spearman_rucc | 0.0997 | 0.0128 | 0.1843 | 0.0300 | yes |
| h4_spearman_log_population | -0.1722 | -0.2835 | -0.0612 | 0.0180 | yes |

Companion Cramér's V for the metro table, not a test: 0.1042. Holm family was applied.

False-positive review, smallest FIPS in each prespecified group. These rows illustrate the flag. They are not a rank.

### Double gap in a state that publishes no county floor

- Liberty County, GA (13179): double_gap, reading reporting_artifact. Tick Established; pathogen Present; human no_county_linked_record. population 65550. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.
- McIntosh County, GA (13191): double_gap, reading reporting_artifact. Tick Established; pathogen Present; human no_county_linked_record. population 11183. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.
- West Feliciana Parish, LA (22125): double_gap, reading reporting_artifact. Tick Established; pathogen Present; human no_county_linked_record. population 15358. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.

### Human floor with neither tick nor pathogen record

- Pima County, AZ (04019): human_without_vector_documentation, reading source_coverage. Tick No records; pathogen No records; human published_count_floor. population 1042393. Supporting `human_published_floor`. Gap tokens `tick_no_records,pathogen_no_records`.
- Baltimore City, MD (24510): human_without_vector_documentation, reading source_coverage. Tick No records; pathogen No records; human published_count_floor. population 584548. Supporting `human_published_floor`. Gap tokens `tick_no_records,pathogen_no_records`.
- Mecosta County, MI (26107): human_without_vector_documentation, reading source_coverage. Tick No records; pathogen No records; human published_count_floor. population 40128. Supporting `human_published_floor`. Gap tokens `tick_no_records,pathogen_no_records`.

### Double gap in a state that publishes a county floor

- Butte County, CA (06007): double_gap, reading follow_up. Tick Established; pathogen Present; human no_county_linked_record. population 213605. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.
- Calaveras County, CA (06009): double_gap, reading follow_up. Tick Established; pathogen Present; human no_county_linked_record. population 45674. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.
- Colusa County, CA (06011): double_gap, reading follow_up. Tick Established; pathogen Present; human no_county_linked_record. population 21811. Supporting `tick_established,pathogen_present`. Gap tokens `human_no_county_linked_record`.

## 4. Caveats

Human surveillance is calendar 2023. Tick and pathogen statuses are cumulative through 2025-12-31. Social vulnerability is 2022. Those windows are not one time base. A blank human floor in a state that publishes no county floor is that state's publication rule. `No records` is not evidence of absence. Counts are surveillance signals and lower bounds where a floor is published (CDC floor 5). They are not incidence, risk, or causation. State-cluster intervals do not cover dependence that crosses a state line. Northeast has fewer than 10 states, so its interval is not estimable. Review yield is not estimable: the examples illustrate the flags and are not an adjudicated sample.

## 5. Disposition

**INVESTIGATE.** The October 13 counts match, and 219 double-gap counties sit in states that publish a county floor. That residual list is the follow-up candidate set in `EDA.CROSS_SIGNAL_CANDIDATES_111` where `REVIEW_READING` is `follow_up`. It is a review list, not a score. Advance is not available from this run: epic #22 says to inspect and not to rank by risk, and a public map or workflow needs a separate review. Keep the lab table for analyst inspection of the follow-up rows. Do not train a model on the class or the reading.

## 6. Artifacts

- Run id: `111-cross-signal-disagreement-20261026T0238Z`
- Snowflake, ML Lab only:
- `REGISTRY.RUNS` 1
- `EDA.METRICS_LONG` 1040
- `EDA.FINDINGS` 3
- `REGISTRY.QUERIES` 4
- `EDA.CROSS_SIGNAL_CANDIDATES_111` 1294
- `REGISTRY.ARTIFACTS` 2
- Drive folder https://drive.google.com/drive/folders/191hhct-v-vch7tHVmcTO1iPO1WTDXs4_
- state-review-counts.png https://drive.google.com/file/d/1HmzHz-NpIFQzbJlzzqfInWRExG_92ah1/view (13093 bytes; Drive metadata size matches the local PNG)
- disagreement-type-matrix.png https://drive.google.com/file/d/1Jpw5rGYfsVSKiVZ14QNx0CJab2mlbgbU/view (28831 bytes; in the issue-111 Drive folder and registered in REGISTRY.ARTIFACTS)
- Doc: `docs/eda/111-cross-signal-disagreement.md`
- `OH_LYME_PROD_READ` cannot count `EDA.CROSS_SIGNAL_CANDIDATES_111` until an owner grants SELECT. This run does not grant it.

## 7. Reproducibility

- Commit: `1b76baf9689bfacc5e12f09b888bb410344c7fcc`
- Release: `governed-2026-10-15-january-climate-prod`
- Seeds: cluster `1112026`, county resample `1112027`
- Commands:

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_111_cross_signal.py
uv run python scripts/verify.py
```
