---
name: ml-scientific-review
description: Prepare independent scientific review of ML evidence and identify unresolved promotion blockers.
---

# ML scientific review

Use when independent review is requested. Read repository `AGENTS.md`,
approved methodology, and available experiment/evaluation evidence.

1. Examine leakage, holdout integrity, baselines, uncertainty, reproducibility,
   and claim limits against governing rules; distinguish evidence from assumptions.
2. Record findings with artifact references and unresolved dependencies.
   Findings do not authorize promotion or release.

Stop on missing evidence or unapproved public-health meaning. Story #45 owns
the full review workflow and gate.

Required inputs: owning issue, approved target/claim scope and methodology, experiment/evaluation artifacts, lineage, and reproduction evidence.

Expected evidence: concise findings tied to inspected artifacts, limitations, unresolved blockers or reviewer decision, including negative findings.
