# ML #32 selected Tier 1 batch evidence

**State:** Local DEV regeneration verified; governed Snowflake publication pending review of [ADR 0003](../adr/0003-tier1-output-persistence-boundary.md) and a data-owned protected migration. This report does not claim a persisted approved batch.

On 2026-10-06 UTC, the committed #30 statistical reference was regenerated through the read-only DEV connection after validating `MATTHEWCARAWAY`, role `OH_LYME_DEV_READ`, database `ONE_HEALTH_LYME_GAP_ATLAS_DEV`, and warehouse `OH_LYME_DEV_INGEST_XS_WH`. Only `PRESENTATION.CURRENT_RELEASE_V` and `PRESENTATION.CURRENT_COUNTY_ATLAS_V` were read. The release and bundle matched the pinned feature contract. The ignored local artifact is `.local/ml-32/{manifest,lineage,county-output}.json`.

| Identity or measurement | Verified value |
| --- | --- |
| Selected model | `tier1-statistical-reference-v1` |
| Rejected model excluded | `tier1-isolation-forest-v1` |
| Feature set | `tier1-county-features-v1` |
| Evaluation | `tier1-selection-evaluation-v1` |
| Tier policy | `tier1-review-percentile-v1` |
| Selected model baseline commit | `b94d776f8367a48153cb080027175083f5f9300b` |
| Batch builder/source commit | `e5479af24e73b9d060ac0df045d14022794b8a47` |
| Batch ID / run ID | `tier1-review-priority-6ae6d3ef989c1220` |
| Generated UTC | `2026-10-06T05:03:35Z` |
| Canonical output SHA-256 | `312a95d9e54da277bfeed2ed34494464c84b768efd0a9fb8d8daeb9c5eb70359` |
| County rows | 3,144 |
| Tiers | HIGH 315; MEDIUM 628; LOW 2,201 |
| Sufficiency | SUFFICIENT 651; INSUFFICIENT 2,493; NOT_ESTIMABLE 0 |
| Persistence destination | Proposed data-owned `FEATURE_STORE.TIER1_COUNTY_REVIEW_OUTPUTS`; not yet created |

The observed tier-by-sufficiency distribution matches #30: all HIGH are SUFFICIENT, MEDIUM is 336 SUFFICIENT and 292 INSUFFICIENT, and all LOW are INSUFFICIENT. These numbers are acceptance checks for this pinned release only. The batch output retains raw states and two or three descriptive reason codes per county. The limitation reference points to the output contract, which prohibits disease-risk, incidence, probability, clinical, and causal interpretation.

Reproduce with `SNOWFLAKE_CONNECTION_NAME` set to the approved read-only DEV connection and `uv run python -m lyme_gap_atlas_ml.tier1_persisted --output-dir .local/ml-32`. The command rebuilds features from the governed release and scores the selected statistical reference directly. It does not read an old CSV, train or publish the Forest, or write Snowflake.

The proposed publisher must accept only this selected model and a complete validated batch, verify the digest, and transactionally activate it after all rows are stored. A failed or partial attempt must leave the previous approved batch active. The exact migration, owner procedure, publisher role, DEV publication, and API read-role proof are outstanding. PROD requires the protected promotion path and separate approval; no PROD action occurred.
