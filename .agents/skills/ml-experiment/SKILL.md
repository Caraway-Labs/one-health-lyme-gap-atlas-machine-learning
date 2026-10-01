---
name: ml-experiment
description: Plan or review a reproducible ML experiment within an approved target and dataset scope.
---

# ML experiment

Use for approved experiment planning, implementation, or reproduction. Read
repository `AGENTS.md`, the target/dataset decision, and the
[structure guide](../../../docs/repository-structure.md).

1. Check the approved inputs and scope against the
   [canonical lineage contract](../../../docs/architecture/declarative-ml-contracts-v1.md).
   Stories #40 and #41 own execution and declarative contracts.
2. Record versioned inputs, features, split, configuration, code revision,
   dependencies, seeds, and nondeterminism using existing artifacts.
3. Run only the approved bounded experiment and simple baseline, following
   repository leakage and holdout rules. Retain negative/inconclusive results.
4. Record the reproduction command, metrics, limitations, and result references
   for independent review; run repository verification before handoff.

Stop on missing or incompatible lineage or unapproved target, data rights,
split, or execution/write scope. Report the dependency instead of inventing approval.

Required inputs: owning issue, approved target/dataset decision, versioned data and split references, experiment configuration, and approved execution scope.

Expected evidence: versioned configuration and lineage, reproduction command, result/baseline references (or a blocker), and limitations; planning alone is not execution evidence.
