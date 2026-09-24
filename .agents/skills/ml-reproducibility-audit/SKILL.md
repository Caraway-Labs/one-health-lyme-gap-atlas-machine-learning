---
name: ml-reproducibility-audit
description: Audit whether an ML result has enough versioned inputs and evidence to reproduce it.
---

# ML reproducibility audit

Use to check a claimed result or release evidence. Read repository
`AGENTS.md` and approved experiment contract. Check snapshot/query,
features, split, configuration, code revision, dependencies, seeds, artifacts,
and known nondeterminism. State what was independently reproduced versus
inspected. Stop short of a pass claim when evidence is missing. Story #45 owns
the full audit; Story #46 owns its CI harness.
