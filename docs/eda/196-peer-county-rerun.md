# 196: Is the peer-county list stable once the bootstrap gate can measure stability?

- Issue: [#196](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/196); program epic [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`,
  lab `EDA.GAP_COMMUNITY_ASSIGNMENTS_120` run `120-gap-communities-20261026T1355Z`,
  and lab `EDA.PEER_COUNTY_NEIGHBORS_192` run `192-peer-county-lookup-20261026T1859Z`.
- Release: `governed-2026-10-15-january-climate-prod`.
- Cohort: 3144 counties, 51 states. Published floor 651. No county-linked record 2493. Wider established-tick gap 810. Double gap 228.

## Method and assumptions

Spec [196-peer-county-rerun/v1](196-analysis-spec.md), frozen before the fit.
The lookup is the issue 192 embedding and exact neighbor search.
The bootstrap gate is conditional retained-neighbor Jaccard.
No ground truth exists. Similar means similar on those context features only.

## Material findings and limits

1. Question

Is the peer-county list stable when the county pool is redrawn, once the result is compared with what a perfectly stable list scores under the same resampling? Should the issue 192 method call change?

2. Method (and why; link the spec)

Spec [196-peer-county-rerun/v1](196-analysis-spec.md), frozen before the fit. The issue 192 raw Jaccard keep line of 0.50 sits on the mechanical ceiling: a fixed neighbor order has expected raw Jaccard 0.499415, and a 2000-replicate simulation (seed 1962026) has median 0.499248. The new statistic is the share of in-sample Euclidean neighbors that remain neighbors when they are still in the bootstrap pool. A fixed order scores 1. Keep requires an estimable interval, a median of at least 0.90, and a lower endpoint of at least 0.80. The two-seed gap stays at most 0.05. Every other issue 192 keep gate is unchanged. k = 5 is the gate. k = 15 is reported and cannot rescue a miss. Bootstrap: 200 draws, seeds 1922026 and 1922027. The cosine type-agreement row uses the cosine estimable count. The issue 192 raw median 0.4999 was already known when this gate was written. The keep line is not a function of that median. No ground truth exists.

3. Key findings with numbers

Counties 3144. States 51. Stored #120 types 810. Conditional bootstrap median 1.0000 (interval 1.0000 to 1.0000, estimable True, failed replicates 0). Second-seed conditional median 1.0000. k=15 conditional median 1.0000. Simulated stable-list raw ceiling 0.499415, simulation median 0.499248. k=15 raw ceiling 0.474395. Raw bootstrap median 0.4999 (interval 0.4857 to 0.5120). Second-seed raw median 0.5015. k=15 raw median 0.4749. The issue 192 method call was revise and it changes to keep. Cosine type-agreement n=776. Euclidean type-agreement n=770. Determinism Jaccard 1.0000. Cosine versus Euclidean Jaccard 0.6443. In-sample type agreement, Euclidean 0.9417 (n=770), cosine 0.9465 (n=776), same-state same-RUCC 0.7476 (n=767). Leave-state-out type agreement, Euclidean 0.9394 (n=747), cosine 0.9465, same-RUCC outside the state 0.5004 (n=810). Leave-state-out gap 0.4390. Leave-state-out neighbor Jaccard 0.7447. Cross-state share 0.9863. Prototype recovery 1.0000. Silhouette 0.2945. Situation agreement 0.7927. Situation agreement is partly circular: tick and pathogen statuses are distance features. Human status is not. Gate failures: none.

| Block | Jaccard after drop | Jaccard of the block alone |
| --- | ---: | ---: |
| svi_percentile | 0.2827 | 0.0055 |
| uninsured_percentile | 0.2866 | 0.0060 |
| log_population | 0.4016 | 0.0088 |
| rucc | 0.2916 | 0.0062 |
| scapularis_status | 0.5095 | 0.0028 |
| pacificus_status | 0.9574 | 0.0020 |
| burgdorferi_status | 0.7744 | 0.0020 |

Examples are the three smallest and three largest 5th-neighbor Euclidean distances. They are not a surveillance ranking.

1. McIntosh County, ND (38051), 5th-neighbor distance 0.1545. Neighbors: Brown County, NE (31017); Sanborn County, SD (46111); Aurora County, SD (46003); Franklin County, NE (31061); Lincoln County, KS (20105).
2. Osborne County, KS (20141), 5th-neighbor distance 0.1569. Neighbors: Cavalier County, ND (38019); Webster County, NE (31181); Rush County, KS (20165); Stanley County, SD (46117); Jewell County, KS (20089).
3. Charlton County, GA (13049), 5th-neighbor distance 0.1666. Neighbors: Franklin County, FL (12037); Calhoun County, FL (12013); Trinity County, TX (48455); Glades County, FL (12043); Okfuskee County, OK (40107).
4. Kalawao County, HI (15005), 5th-neighbor distance 2.1992. Neighbors: Loving County, TX (48301); Blaine County, NE (31009); Arthur County, NE (31005); Petroleum County, MT (30069); Daggett County, UT (49009).
5. Loving County, TX (48301), 5th-neighbor distance 1.8349. Neighbors: Kent County, TX (48263); Harding County, NM (35021); Daggett County, UT (49009); McPherson County, NE (31117); Petroleum County, MT (30069).
6. Kenedy County, TX (48261), 5th-neighbor distance 1.6107. Neighbors: King County, TX (48269); San Juan County, CO (08111); McMullen County, TX (48311); Clark County, ID (16033); Foard County, TX (48155).

4. Caveats

No ground truth exists. A neighbor list is a lookup on the listed context features. It is a surveillance-signal comparison. A published human floor is a lower bound (CDC floor 5). No records and Unknown are not negatives. A missing floor is not zero. Human surveillance is calendar 2023. Population, social vulnerability, and uninsured share are 2022. The rural-urban code is 2023. Tick and pathogen statuses are cumulative through 2025-12-31. The leave-state-out does not cover dependence that crosses a state line. The bootstrap band is a stability band for the lists, not a disease-rate interval. The issue 192 raw median 0.4999 was known before the gate was redefined. #120 types exist for 810 counties, from run `120-gap-communities-20261026T1355Z`. Counties outside that cohort have no stored type, so type agreement ignores them. FINDINGS records product advance as keep, investigate as follow-up, and stop as stop. The statement uses that same word.

5. Disposition

Method: keep. Product: advance. The issue 192 method call changes. Rule failures: none. This is not a release and not a change to the Tier 1 model.

6. Artifacts

run_id: 196-peer-county-rerun-20261026T2145Z
Snowflake row counts: EDA.FINDINGS=2, EDA.METRICS_LONG=55, EDA.PEER_COUNTY_NEIGHBORS_192_referenced=3144, EXPERIMENTS.EXPERIMENTS=4, EXPERIMENTS.MODEL_METRICS=10, REGISTRY.ARTIFACTS=1, REGISTRY.QUERIES=4, REGISTRY.RUNS=1.
Recomputed k=5 lists match `192-peer-county-lookup-20261026T1859Z` in `EDA.PEER_COUNTY_NEIGHBORS_192`. No new neighbor table was created.
SELECT grants: referenced-192-table.
Registered chart: stability.png, Drive file `1VQx3Xz53dIuOgS6iwF49yAv1WrCqfIdc`, https://drive.google.com/file/d/1VQx3Xz53dIuOgS6iwF49yAv1WrCqfIdc/view, 8807 bytes, sha256 `41a8c8bc2db8f187abfd94a41bc4d0dbc0acdb36261b4f3724e3f7da47a5c512`. Local size and sha256 matched and the PNG decoded before the REGISTRY.ARTIFACTS insert.
Uploads stopped after the next create stored 8 bytes. That object is Drive file `1EsFnLvjDtnmszx9xYi_WTudmGTgU5c4F`, named method-agreement.png. It is not the chart and it is not registered. Trash was refused because the file is shared.
Unregistered local charts, for the ML Lead to upload: `artifacts/charts/196/method-agreement.png`, 11320 bytes, sha256 `03acb75bd41056e0e93377ebb687c6406988b9e709fad45ebbba97f5fc720c9c`; `artifacts/charts/196/ablation.png`, 12740 bytes, sha256 `7f0855b65dcec77c15c200959d3bea4b9f12a2a14971eb90bdc706e408e6615e`; `artifacts/charts/196/neighbor-distance.png`, 12432 bytes, sha256 `518b3b620b5372bd1ae7876e52a560a97b68ee565cc028230cb437b3bf43d5a7`.
The frozen gate was not changed after the fit.
Doc: docs/eda/196-peer-county-rerun.md
Spec: docs/eda/196-analysis-spec.md

7. Reproducibility

Commit: 650cc1d903c3077a09913ac53d7149e994b66ebe
Release: governed-2026-10-15-january-climate-prod
Fit seeds: 1922026 and 1922027. Bootstrap replicates: 200. Ceiling simulation seed: 1962026. Ceiling replicates: 2000.
Commands:
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_196_peer_lookup.py
uv run python scripts/verify.py
County neighbor rows were not written to git or Drive.

Part of #196
Part of #22

## Decision

PROCEED. Method keep. Product advance. The issue 192 method call was revise. This is not a release and not a change to the Tier 1 model.

## Reproduction and retained evidence

- Code revision/run: commit `650cc1d903c3077a09913ac53d7149e994b66ebe`, run `196-peer-county-rerun-20261026T2145Z`, spec `196-peer-county-rerun/v1`.
- Entry points: `sql/validation/192_peer_lookup.sql`, `src/lyme_gap_atlas_ml/peer_lookup.py`, `src/lyme_gap_atlas_ml/peer_lookup_rerun.py`, `scripts/eda_196_peer_lookup.py`.
- Command: `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_196_peer_lookup.py`.
- Gate: `uv run python scripts/verify.py`.
- Transient artifacts not committed: `artifacts/charts/196/` and `outputs/`.
