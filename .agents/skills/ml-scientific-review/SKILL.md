---
name: ml-scientific-review
description: Independently review ML evidence using nine focused questions and a structured disposition.
---

# ML scientific review

Use when independent review is requested. Read repository `AGENTS.md`, the
owning issue, approved methodology/target, and the supplied artifacts.

Required inputs: explicit intended/prohibited use; dataset/cohort and availability;
feature/split/holdout records; baseline/evaluation; git/config/data/run references;
uncertainty, data-quality limits, and proposed interpretation.

1. Inspect evidence read-only. Do not tune, access protected holdout labels,
   alter a source artifact, promote, or rewrite prior findings to obtain a pass.
2. Answer these nine questions with PASS / FAIL / BLOCKED / NEEDS_DECISION:
   - `problem_target`: Is the question, target, and intended use explicit?
   - `point_in_time`: Is the data/cohort valid at the prediction cutoff?
   - `leakage`: Is target, temporal, spatial, and preprocessing leakage excluded?
   - `holdout`: Was the final holdout protected from tuning and selection?
   - `baseline`: Was a simple baseline compared fairly on the same split?
   - `metrics`: Do metrics match the task and material error costs?
   - `limitations`: Are uncertainty and data-quality limits represented honestly?
   - `reproducibility`: Can git/config/data/run artifacts reproduce the result?
   - `interpretation`: Are causal, diagnostic, and individual-risk claims supported?
3. Write a separate result using the
   [output schema](../../../docs/methodology/scientific-review-v1.schema.json).
   Cite inspected evidence, concise findings, and the smallest remediation.
   Known incorrect/misleading evidence means FAIL; missing evidence means BLOCKED;
   unresolved target/method/use authority means NEEDS_DECISION. PASS requires all
   nine checks to pass. Report any remaining blocker even alongside a known failure.
4. Validate structure using `scripts.verify.validate_schema_example(schema, result)`;
   schema validation does not establish scientific truth. The
   [fixture packet](../../../tests/fixtures/scientific_review_cases.json) and
   [example result](../../../config/examples/reviews/representative-blocked.json)
   demonstrate a quick review.

Stop on missing evidence or unapproved public-health meaning; name the artifact
or decision needed. Expected evidence: structured disposition, inspected references,
findings/limits, and minimal remediation. Distinguish replay from inspection.
A PASS is review evidence for a human decision, never automatic release approval.
No Arize/production-readiness checklist is required here unless the active model
needs it. Model-specific details remain in #23/#24/#25/#26/#30 and the methodology.
