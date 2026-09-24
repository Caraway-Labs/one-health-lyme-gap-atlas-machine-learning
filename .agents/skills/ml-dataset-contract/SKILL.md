---
name: ml-dataset-contract
description: Review ML dataset scope, provenance, and contract dependencies before dataset work.
---

# ML dataset contract

Use for an ML dataset definition or change. Read repository `AGENTS.md`,
the [structure guide](../../../docs/repository-structure.md), and approved
source contract. Identify owner, snapshot/query, geography, time range,
target/label source, permitted use, and unknowns. Governed ingestion and
canonical normalization belong to the data repository. Stop if source
authorization, target meaning, or lineage is ambiguous. Story #41 owns the
declarative contract; do not invent its schema here.
