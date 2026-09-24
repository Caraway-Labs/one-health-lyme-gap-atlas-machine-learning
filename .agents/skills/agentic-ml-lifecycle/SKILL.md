---
name: agentic-ml-lifecycle
description: Validate Atlas ML lifecycle state, inspect gates, and resume bounded work safely.
---

# Agentic ML lifecycle

Use for lifecycle stage planning, execution or reporting. Read the owning issue,
repository `AGENTS.md`, [Epic #36](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/36), and the [v1 methodology](../../../docs/methodology/agentic-ml-lifecycle-v1.md).

1. Load state with `lyme_gap_atlas_ml.lifecycle.load_state` or validate a parsed
   object with `validate_state`. Do not infer status from an invalid state.
2. Call `resume` to identify completed stages, their evidence references, the
   current stage, blocker and next stage. Inspect referenced artifacts and
   governing issue decisions; a reference string alone is not evidence of a pass.
3. Work only on the first nonterminal stage. For a blocker, resolve its named
   dependency before work. For `not_applicable`, require reason, evidence and
   approved reviewer decision. Never rerun completed stages or fabricate evidence.
4. Before a transition, check the stage outputs and versioned references in the
   methodology, holdout access history, and required human decision. Update the
   state and validate it again. Preserve previous evidence and access events.
5. Stop on missing source/target approval, unsafe split or holdout use, missing
   evidence, ambiguous environment, or unapproved promotion, production write,
   retraining or public release. Report the unresolved gate and reviewer needed.

The [schema](../../../docs/methodology/lifecycle-state-v1.schema.json) and
[template](../../../docs/methodology/lifecycle-state-v1.template.json) describe
the machine-readable surface. Existing stories #23–#35 own their detailed
model-specific requirements; this skill cannot approve them.
