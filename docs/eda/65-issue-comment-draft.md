# Prepared issue comment — held for Matthew's review

Do not post before independent scientific/code review of the exact PR head.

**Disposition: STRONG_ASSOCIATION by the preregistered point-estimate bin.**
For the source-compatible pairing **Ixodes scapularis OR Ixodes pacificus +
Borrelia burgdorferi sensu stricto**, the governed PROD aggregate documentation
states give **N = 3,109 unique eligible counties**, Cramer's **V = 0.560660**,
state-cluster 95% robustness interval **0.464977–0.652404**. The interval crosses
the moderate/strong bins; this is exploratory county documentation association.

The table (pathogen Present / No records) is Established **671 / 733**,
Reported **17 / 473**, and No records **1 / 1,214**. Minimum expected cell count
is 108.59, supporting the registered Pearson method despite one small observed
cell. The IID reference p-value is 6.11e-213; it does not supply spatial inference.
The fixed Established+Reported collapse gives **V = 0.425779**, robustness
interval **0.339043–0.515744**, demonstrating sensitivity to category detail.

There are **3,144 source projection rows and 3,144 unique counties**: 35 excluded
for scope, all with both aggregate states Unknown; 3,109 in scope have no unknown
vector or pathogen states and no missing scope. Source-native observation counts
are unavailable. These real PROD counts are distinct from the DEV release's N=0
and NOT_ESTIMABLE result.

**ML implication:** Co-occurrence does not establish feature interchangeability:
688/689 pathogen-Present counties have documented vector evidence, while
1,206/1,894 documented-vector counties have pathogen No records. Preserve the
finer documentation information; no predictive redundancy, conditional feature
value, causal effect, training or feature admission is established.

**Product implication:** Preserve Unknown versus No records. These cumulative
states are neither annual incidence nor biological absence or exposure risk.
The public aggregate is analyzed directly; species-specific states were not
reconstructed. Release-bound producer/source rules justify its union semantics,
with one preregistered fixed-county detail check, not a fresh private lineage audit.

Registration commits: v1 `459d53d`, PROD amendment `fb0a6a8`, public aggregate
amendment `00ad62d`, each before its dependent result inspection. PROD release
`governed-2026-09-18-unknown-coverage`; bundle
`038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`.
Retained capture digests, bounded queries/probe, provenance limitations, tests and
replay commands are in the [artifact](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/blob/codex/ml-65-vector-pathogen/docs/eda/65-vector-pathogen-state-association.md).
[Draft PR #91](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/91).
Keep #65 open until independent scientific/code review and merge. No source
contract, production, or Web change is included.
