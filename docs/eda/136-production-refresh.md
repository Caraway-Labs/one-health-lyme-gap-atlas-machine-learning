# 136: Did the production Atlas change enough to reopen the latent-class frame?

- Issue: [ML #136](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/136), under [ML #119](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/119). Question: is the live production release still the snapshot assumed by the completed frame and data tasks, and do the four latent-class inputs still mean the same thing?
- Data: `ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION`, read-only role `OH_LYME_PROD_READ`, warehouse `COMPUTE_WH`. Compared with [prod-exhaustive-eda.md](prod-exhaustive-eda.md).
- Cohort: all counties on `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. Human status is 2023. Tick and pathogen status are cumulative through 2025-12-31. Population is the 2022 county layer.

## Method and assumptions

Read-only aggregates and metadata. No model was fit. No county-level extract was kept. The class-count rule was not rerun, and the cross-tab was not used to choose a class count.

Context before the data queries, 2026-10-17: user `MATTHEWCARAWAY`, role `OH_LYME_PROD_READ`, database `ONE_HEALTH_LYME_GAP_ATLAS_PROD`, schema `PRESENTATION`, warehouse `COMPUTE_WH`, secondary roles empty. The connection had no default schema or warehouse; both were selected for the session.

## Material findings and limits

The release identity changed. The surveillance counts did not.

| | Earlier catalog | This read |
| --- | --- | --- |
| Release | `governed-2026-10-06-nlcd-demo-cohort` | `governed-2026-10-15-january-climate-prod` |
| Schema / method | `1.0.0` / `semantic-1.0.0` | `2.0.0` / `semantic-2.0.0` |
| Bundle SHA-256 | `603afb135a1a5c958d1d56d48d580d9942c67eb38986caf8b4b3acf69fcde2c9` | `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d` |
| Generated / loaded | 2026-10-05 / 2026-10-10 | 2026-10-15 13:51 -0700 / 2026-10-15 14:08 -0700 |

The county table is still one row for each of 3,144 five-digit FIPS codes, 51 state codes, and 331,097,593 people. Population still runs from 50 to 9,936,690. Human status is still `published_count_floor` for 651 counties (158,701,707 people) and `no_county_linked_record` for 2,493 counties (172,395,886 people). The case and incidence floors are still null for exactly those 2,493 counties. Alaska is still 30 counties and Hawaii is still 5, all with tick and pathogen status `Unknown` and outside the contiguous tick scope. No other state has an `Unknown` tick or pathogen status. No county has both tick species established.

The 12-cell human × tick × pathogen table matches the earlier catalog county for county and person for person, including the 228-county cell where ticks are established, pathogen is present, and the human floor is blank. The allowed levels are unchanged: human `published_count_floor` and `no_county_linked_record`; each tick species `Established`, `Reported`, `No records`, and `Unknown`; pathogen `Present`, `No records`, and `Unknown`.

The atlas view still has the same 21 columns. The read role still sees 14 views. Those views now have 280 columns rather than 268. The added columns are on `CURRENT_COUNTY_OBSERVATIONS_V`, which grew from 29 columns to 41. The measure dictionary still lists the same surveillance, context, and two-county land-cover measures. It does not list a climate measure. The September review tier is still pinned to `governed-2026-09-18-unknown-coverage` and `tier1-statistical-reference-v1`, so it remains an older score rather than a new input.

Source vintages are unchanged: human 2023, ticks and pathogen through 2025-12-31, SVI 2022, RUCC 2023, and NLCD 2025 for the two-county demonstration. The release text still says published human values are floors, `No records` is not absence, and land cover is not automatic model input.

Climate and intelligence views are still present. Their row counts did not return in this pass, so this note does not say whether those views are still empty. The release name mentions January climate. The indicator list does not add climate as a surveillance input.

## Decision

PROCEED to the baseline task, [ML #132](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/132).

The question, class-count range, selection rule, and missingness rule in [119-analysis-spec.md](119-analysis-spec.md) stay in place. The dataset contract is amended from `v1` to `v1.1` so the fit checks the current release instead of the October 6 bundle. That is an identity amendment, not a new scientific frame. Another full EDA pass is not required before the baseline. A later count of the climate and intelligence views is a separate follow-up and does not change the four latent-class inputs.

## Reproduction and retained evidence

- Code at read time: `9afd510`. SQL: [119_refresh_eda.sql](../../sql/validation/119_refresh_eda.sql).
- Objects read: `PRESENTATION.CURRENT_RELEASE_V`, `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `PRESENTATION.CURRENT_TIER1_COUNTY_REVIEW_V`, `PRESENTATION.CURRENT_SOURCE_METADATA_V`, `PRESENTATION.CURRENT_INDICATOR_METADATA_V`, `PRESENTATION.CURRENT_MEASURE_METADATA_V`, and `INFORMATION_SCHEMA.COLUMNS` for the visible views. No base table was queried. No object was written.
- Command shape: `snow sql` as the verified read role, with schema `PRESENTATION` and warehouse `COMPUTE_WH`. The local connection name is not recorded.
- Lifecycle: frame and data remain complete. `resume` should report `baseline` as the current stage.
- Transient artifacts not committed: ignored `outputs/119-refresh-eda/` query results.
- Verification: `uv run python scripts/verify.py`.
