# Atlas ML opportunity map v1

Source of product decisions: [Epic #50](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/50),
recorded 2026-10-01 for [Story #51](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/51).
This map records current direction; it is not scientific validation or approval
to train, publish predictions, change access, or deploy a model.

| Capability | Classification | Owning backlog / repository | Rationale |
| --- | --- | --- | --- |
| Cross-signal anomaly / disagreement | **GO** — statistical/residual baseline first | ML [#52](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/52), [contract](contracts/cross-signal-disagreement-v1.md) | Transparent evidence-discordance review is the first GO capability; approved comparable signals/reference/thresholds are still prerequisites, and missing evidence cannot become an anomaly. |
| County prediction / forecasting | **DEFER** — EDA-gated, paused/tabled | ML [#23](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/23), [#54](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/54) | No prediction target, horizon or evaluation approval is inferred from data availability; #23 remains paused until an explicit evidence-grounded product decision. |
| County Review Priority | **HEURISTIC** — first | ML decision [#53](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/53); downstream [API](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-api) / [web](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-web) | Use an explainable review-priority heuristic rather than learning-to-rank by default; this is not a clinical or individual-risk score. |
| Literature / knowledge graph / Ask Atlas | **RETRIEVAL** — synthesis (`NLP_RETRIEVAL`) | ML boundary [#55](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/55); [knowledge-graph](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-knowledge-graph) / [API](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-api) / [web](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-web) | Retrieve and synthesize evidence in the owning application repositories; LLM output is not an epidemiological label or predictor and needs no duplicate ML infrastructure. |
| Nowcasting | **DEFER** | ML [#54](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/54), distinct from paused risk-prediction [#23](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/23) | Reopen only after a concrete user decision defines the reporting-delay question and timing (forecast origin, horizon/lead time, and reporting window), with suitable time/availability evidence. It remains distinct from the paused county disease-risk target. |
| Underreporting / true-incidence estimation | **DEFER** | ML [#56](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/56) | Surveillance gaps or disagreement do not establish hidden disease or true incidence. Reopen only with explicit labels, an evaluation contract, and prohibited-use boundaries; this map approves no estimate. |
| Bayesian / spatial model complexity | **DEFER** until simpler methods justify it | ML [#2](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/2), [#11](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/11) | Additional complexity needs evidence that a simpler approved baseline cannot answer the actual question. |

New ML implementation needs an explicit GO with a real user need, approved data
path and bounded question. GO is direction to pursue that scope, not blanket
execution authority. Deferred ideas create no implementation dependencies; existing
backlog tickets do not override this map's source decisions. Governed ingestion
and normalization remain in the [data repository](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data).

Use the existing [analysis spec](methodology/analysis-spec-v1.md) for a selected
statistical question and [durable EDA evidence](eda/README.md) when it is executed.
This document performs no EDA, analysis or experiment: EDA artifact **N/A**; no
source extracts or transient outputs are produced. Update this versioned map when
the owning product decision changes, citing its evidence; no machine-readable
companion, registry or new architecture is required.
