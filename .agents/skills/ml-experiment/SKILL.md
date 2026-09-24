---
name: ml-experiment
description: Plan or review a reproducible ML experiment within an approved target and dataset scope.
---

# ML experiment

Use for an approved experiment. Read repository `AGENTS.md`, target/dataset
decision, and [structure guide](../../../docs/repository-structure.md). Record
versioned inputs, features, split, configuration, code revision, dependencies,
seeds, and nondeterminism. Protect holdout membership and labels from tuning.
Stop if target, data rights, split, or write scope is unapproved. Stories #40
and #41 own execution and declarative contracts. Use the
[canonical lineage contract](../../../docs/architecture/declarative-ml-contracts-v1.md)
for model, dataset, feature, split, evaluation, experiment, and run identity;
stop on missing or incompatible references.
