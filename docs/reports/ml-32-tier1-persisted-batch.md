# ML #32 selected Tier 1 batch evidence

**State:** PRE-MERGE / UNPUBLISHED local DEV review evidence. The product owner approved the persistence direction in [ADR 0003](../adr/0003-tier1-output-persistence-boundary.md); exact Data implementation and security review remain pending. No batch in this report is authorized for publication.

On 2026-10-06 UTC, the committed #30 statistical reference was regenerated through the read-only DEV connection after validating `MATTHEWCARAWAY`, role `OH_LYME_DEV_READ`, database `ONE_HEALTH_LYME_GAP_ATLAS_DEV`, and warehouse `OH_LYME_DEV_INGEST_XS_WH`. Only `PRESENTATION.CURRENT_RELEASE_V` and `PRESENTATION.CURRENT_COUNTY_ATLAS_V` were read. The release and bundle matched the pinned feature contract. The ignored local artifact is `.local/ml-32/{manifest,lineage,county-output}.json`.

| Identity or measurement | Verified value |
| --- | --- |
| Selected model | `tier1-statistical-reference-v1` |
| Rejected model excluded | `tier1-isolation-forest-v1` |
| Feature set | `tier1-county-features-v1` |
| Evaluation | `tier1-selection-evaluation-v1` |
| Tier policy | `tier1-review-percentile-v1` |
| Selected model baseline commit | `b94d776f8367a48153cb080027175083f5f9300b` |
| Batch builder/source commit | `5d1bb95a18a9030571df492d712f255528169b4a` |
| PRE-MERGE review batch ID / run ID | `tier1-review-priority-aec96f0cbff7c081` |
| Generated UTC | `2026-10-06T05:20:15Z` |
| PRE-MERGE review output SHA-256 | `fa6b71f9c95d983cf36308819fbd295e3c82646c13257dbace0236ac3d72f7b7` |
| County rows | 3,144 |
| Tiers | HIGH 315; MEDIUM 628; LOW 2,201 |
| Sufficiency | SUFFICIENT 651; INSUFFICIENT 2,493; NOT_ESTIMABLE 0 |
| Persistence destination | Proposed data-owned `FEATURE_STORE.TIER1_COUNTY_REVIEW_OUTPUTS`; not yet created |

The observed tier-by-sufficiency distribution matches #30: all HIGH are SUFFICIENT, MEDIUM is 336 SUFFICIENT and 292 INSUFFICIENT, and all LOW are INSUFFICIENT. These numbers are acceptance checks for this pinned release only. The batch output retains raw states and two or three descriptive reason codes per county. The limitation reference points to the output contract, which prohibits disease-risk, incidence, probability, clinical, and causal interpretation. The revised validator passed exact output FIPS-set equality with the regenerated governed feature matrix; unique 3,144-row output and five-digit formatting alone cannot pass. All 3,144 rows use the selected model, and none use the rejected Forest.

Reproduce with `SNOWFLAKE_CONNECTION_NAME` set to the approved read-only DEV connection and `uv run python -m lyme_gap_atlas_ml.tier1_persisted --output-dir .local/ml-32`. The command rebuilds features from the governed release and scores the selected statistical reference directly. It does not read an old CSV, train or publish the Forest, or write Snowflake.

The pre-merge ID and digest above are **not publishable**. The earlier review artifact `tier1-review-priority-6ae6d3ef989c1220` (builder commit `e5479af24e73b9d060ac0df045d14022794b8a47`) is also pre-merge, unpublished evidence and is superseded by this validation revision. After PR #103 merges, fetch final `origin/main` and regenerate from that exact commit; a squash merge changes the SHA and intentionally produces a different batch ID and digest. Record the final source commit, batch ID, digest, UTC timestamp, FIPS-set proof, and counts from that post-merge run before requesting publication. Never reuse a pre-merge identity to make the batch appear final.

The Data-owned publisher must accept only this selected model and a complete validated batch, independently compare the county set to the pinned governed feature population, verify the digest, and transactionally activate it after all rows are stored. A failed or partial attempt must leave the previous approved batch active. The exact migration, owner procedure, publisher role, DEV publication, and API read-role proof are outstanding. PROD requires the protected promotion path and separate approval; no PROD action occurred.
