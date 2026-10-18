# ML #119 lifecycle decision

Owning task: [ML #135](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/135). The inspection record is [119-surveillance-latent-class.json](../../config/examples/reviews/119-surveillance-latent-class.json).

## Disposition

**SELECT.** Keep both assignment tables as the experiment result for story #119. Offer the tick-and-pathogen class probabilities to a later story under the limit in [119-surveillance-latent-classes.md](../eda/119-surveillance-latent-classes.md). This disposition does not promote a model, retrain a model, write a production Snowflake object, or authorize an API.

The story owner dispatched completion of #119 on 2026-10-17. SELECT is the disposition defined by #135 for that completion: retain the experiment result and do not publish a score. The inspection disposition is PASS. That pass is evidence for this decision. It is not a release approval.

## What later stories may consume

A later linear model, and the isolation-forest story #122, may consume the tick-and-pathogen hard class and its four class probabilities. Those values do not include human status. They describe the tick and pathogen grouping in the evaluation note.

They may not consume the four-state class as an input to a model whose outcome is the human floor. That class was fit with human status in it. They may not treat either probability as disease risk, incidence, pathogen presence, biological absence, or as the 228-county list. The established-blacklegged tick-and-pathogen class assigns probability essentially 1 to both pathogen `Present` and pathogen `No records`.

## What this story does not do

No production score is published. The classes are not disease risk or incidence. API serving is out of scope for #119. No Snowflake object was written for the model or the county assignments.
