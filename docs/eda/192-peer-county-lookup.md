# 192: Which counties look alike on the #120 context features?

- Issue: [#192](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/192); program epic [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`,
  and lab `EDA.GAP_COMMUNITY_ASSIGNMENTS_120` run `120-gap-communities-20261026T1355Z`.
- Release: `governed-2026-10-15-january-climate-prod`.
- Cohort: 3144 counties, 51 states. Published floor 651. No county-linked record 2493. Wider established-tick gap 810. Double gap 228. Reference gap counts matched 810 and 228.

## Method and assumptions

Spec [192-peer-county-lookup/v1](192-analysis-spec.md), frozen before the fit.
Euclidean and cosine neighbors use one embedding of the #120 feature set.
The baseline is the same state and the same rural-urban code.
No ground truth exists. Similar means similar on those context features only.

## Material findings and limits

1. Question

For a county, which other counties are nearest on the #120 context features, does that short list survive a redraw of the county pool and a held-out state, and does it beat a same-state same-RUCC match on #120 type agreement?

2. Method (and why; link the spec)

Spec [192-peer-county-lookup/v1](docs/eda/192-analysis-spec.md), frozen before the fit. The embedding is the #120 feature set: z-scored social-vulnerability percentile, uninsured percentile, and log population, plus one-hot rural-urban code and the three surveillance statuses scaled so squared Euclidean distance matches gamma 0.5. Cosine uses that same embedding. k = 5 is the short list. k = 15 is reported and cannot rescue a miss. The baseline peer set is every other county in the same state with the same rural-urban code. When the state is held out, that set is empty, so the leave-state-out type comparison uses other-state counties with the same code. Bootstrap: 200 draws, seeds 1922026 and 1922027. Nearest prototype uses the stored #120 labels and is not a new clustering. No ground truth exists.

3. Key findings with numbers

Counties 3144. States 51. Stored #120 types 810. Determinism Jaccard 1.0000. Cosine versus Euclidean Jaccard 0.6443. In-sample type agreement, Euclidean 0.9417 (n=770), cosine 0.9465, same-state same-RUCC 0.7476 (n=767). In-sample gap 0.1941. Leave-state-out type agreement, Euclidean 0.9394 (n=747), cosine 0.9465, same-RUCC outside the state 0.5004 (n=810). Leave-state-out gap 0.4390. Leave-state-out neighbor Jaccard 0.7447. Cross-state share 0.9863. Bootstrap median Jaccard 0.4999 (interval 0.4857 to 0.5120, estimable True, failed replicates 0). Second-seed bootstrap median 0.5015. k=15 bootstrap median 0.4749. k=15 leave-state-out type agreement 0.9267. Prototype recovery 1.0000. Silhouette 0.2945. Situation agreement 0.7927. Situation agreement is partly circular: tick and pathogen statuses are distance features. Human status is not. Gate failures: bootstrap.

| Block | Jaccard after drop | Jaccard of the block alone |
| --- | ---: | ---: |
| svi_percentile | 0.2827 | 0.0055 |
| uninsured_percentile | 0.2866 | 0.0060 |
| log_population | 0.4016 | 0.0088 |
| rucc | 0.2916 | 0.0062 |
| scapularis_status | 0.5095 | 0.0028 |
| pacificus_status | 0.9574 | 0.0020 |
| burgdorferi_status | 0.7744 | 0.0020 |

Examples are the three smallest and three largest 5th-neighbor Euclidean distances. They are not a disease ranking.

1. McIntosh County, ND (38051), 5th-neighbor distance 0.1545. Neighbors: Brown County, NE (31017); Sanborn County, SD (46111); Aurora County, SD (46003); Franklin County, NE (31061); Lincoln County, KS (20105).
2. Osborne County, KS (20141), 5th-neighbor distance 0.1569. Neighbors: Cavalier County, ND (38019); Webster County, NE (31181); Rush County, KS (20165); Stanley County, SD (46117); Jewell County, KS (20089).
3. Charlton County, GA (13049), 5th-neighbor distance 0.1666. Neighbors: Franklin County, FL (12037); Calhoun County, FL (12013); Trinity County, TX (48455); Glades County, FL (12043); Okfuskee County, OK (40107).
4. Kalawao County, HI (15005), 5th-neighbor distance 2.1992. Neighbors: Loving County, TX (48301); Blaine County, NE (31009); Arthur County, NE (31005); Petroleum County, MT (30069); Daggett County, UT (49009).
5. Loving County, TX (48301), 5th-neighbor distance 1.8349. Neighbors: Kent County, TX (48263); Harding County, NM (35021); Daggett County, UT (49009); McPherson County, NE (31117); Petroleum County, MT (30069).
6. Kenedy County, TX (48261), 5th-neighbor distance 1.6107. Neighbors: King County, TX (48269); San Juan County, CO (08111); McMullen County, TX (48311); Clark County, ID (16033); Foard County, TX (48155).

4. Caveats

No ground truth exists. A neighbor list is a lookup aid, not a validated similarity. Similar means similar on the listed context features only. It is not similar disease burden, not risk, and not causation. A published human floor is a lower bound (CDC floor 5). No records and Unknown are not negatives. A missing floor is not zero. Human surveillance is calendar 2023. Population, social vulnerability, and uninsured share are 2022. The rural-urban code is 2023. Tick and pathogen statuses are cumulative through 2025-12-31. The leave-state-out does not cover dependence that crosses a state line. The bootstrap band is a stability band for the lists, not a confidence interval for a disease rate. #120 types exist for 810 counties, from run `120-gap-communities-20261026T1355Z`. Counties outside that cohort have no stored type, so type agreement ignores them.

5. Disposition

Method: revise. Product: investigate. Rule failures: bootstrap. This is not a release and not a change to the Tier 1 model.

6. Artifacts

run_id: 192-peer-county-lookup-20261026T1859Z
Snowflake row counts: EDA.FINDINGS=2, EDA.METRICS_LONG=48, EDA.PEER_COUNTY_NEIGHBORS_192=3144, EXPERIMENTS.EXPERIMENTS=4, EXPERIMENTS.MODEL_METRICS=9, REGISTRY.ARTIFACTS=4, REGISTRY.QUERIES=3, REGISTRY.RUNS=1.
SELECT grants: OH_LYME_PROD_READ=pass, OH_LYME_ML_LAB_READ=pass.
Drive folder: https://drive.google.com/drive/folders/10a28-e2qw1kfaZwPfITA5ZPfGpv_7OZj

The four registered charts are palette PNGs. Every pixel matches the fit render. The unused alpha channel is dropped. That is the encoding whose Drive bytes matched the local file. The frozen analysis rules did not change.

- method-agreement.png, 3949 bytes, sha256 f90c75947bf1fa3941dd3746572d615608e5a3ac12845843ed2b9b93fe03fdd8, https://drive.google.com/file/d/1kus6xBAs6oWBllekxtNYuSTqiwyb3pKb/view
- stability.png, 4344 bytes, sha256 117b91e54f7fac8f690e505ab331191d1a830e1a48a741b4cd231f5529c15218, https://drive.google.com/file/d/1c2FnZ66_ZFEgSm1yrT8OGh7gDvhukHez/view
- ablation.png, 4840 bytes, sha256 85bea5b19295d9ef91aad213142189994cb479c8d389d683fa727c2a0a2164b8, https://drive.google.com/file/d/1qFGkYAUiH9dmbBl4Bq2lirZ93a_iRGJZ/view
- neighbor-distance.png, 4835 bytes, sha256 8242fcb505501e32dd9ebf56f827ba8b961d9a37ed242a5a46cad49206886bcc, https://drive.google.com/file/d/1rzk49NT4YBPj3aZXwsLiy4vmxJeg7iIr/view
Doc: docs/eda/192-peer-county-lookup.md
Spec: docs/eda/192-analysis-spec.md

7. Reproducibility

Commit: 38687f32b3171cb81bf5bc9405c0f8ff69759b61
Release: governed-2026-10-15-january-climate-prod
Seeds: 1922026 and 1922027. Bootstrap replicates: 200.
Commands:
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_192_peer_lookup.py
uv run python scripts/verify.py
County neighbor rows were not written to git or Drive. They stay in EDA.PEER_COUNTY_NEIGHBORS_192.

Part of #192
Part of #22

## Decision

INCONCLUSIVE. Method revise. Product investigate. This is not a release and not a change to the Tier 1 model.

## Reproduction and retained evidence

- Code revision/run: commit `38687f32b3171cb81bf5bc9405c0f8ff69759b61`, run `192-peer-county-lookup-20261026T1859Z`, spec `192-peer-county-lookup/v1`.
- Entry points: `sql/validation/192_peer_lookup.sql`, `src/lyme_gap_atlas_ml/peer_lookup.py`, `scripts/eda_192_peer_lookup.py`.
- Command: `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_192_peer_lookup.py`.
- Gate: `uv run python scripts/verify.py`.
- Transient artifacts not committed: `artifacts/charts/192/` and `outputs/`.
