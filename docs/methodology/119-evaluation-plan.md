# ML #119 frozen evaluation plan

Owning task: [ML #134](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/134). This plan was written against the completed fit in [119-class-count-selection.md](119-class-count-selection.md). It does not change that fit.

## What is already fixed

The class count, the primary seed `1192026`, the alternate seeds, and the hard assignments are the ones in [119-latent-class-v1-result.json](../../config/experiments/119-latent-class-v1-result.json). Code revision `cd936fe345664e606c916b137dd642caa0d6d73b`. Release `governed-2026-10-15-january-climate-prod`. Bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. Task #134 names the earlier October 6 release. [ML #136](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/136) replaced that identity before the fit. This plan records the release that was actually fit.

No new class count is chosen here. The 228-county list is opened only as a comparison to the finished assignments.

## Checks

1. For each estimand and each class, report the county count, county share, population total, and population share. Population is the reporting denominator.
2. For each class, report the most common level of each indicator and the share of the class on that level.
3. Give each class a plain-language name taken from those modal levels. The name describes the surveillance situation. It does not call the class disease risk, incidence, or a production score.
4. Alaska and Hawaii pass when every one of those counties has hard class membership in the class whose modal tick and pathogen levels are `Unknown`.
5. Restate the stability table already recorded for K = 2 through 6. The chosen count stays the one the frozen rule selected.
6. After the names exist, count how the 228-county pattern falls across the four-state classes. That pattern is the baseline cells with a human blank, one tick species `Established`, the other tick species `No records`, and pathogen `Present`. A match is a description of overlap. It is not a reason to refit.
7. State separately whether the tick-and-pathogen class probabilities are fit to offer to a later linear model or to the isolation-forest story. That statement uses the tick-and-pathogen fit only.

## Stop

If Alaska or Hawaii land outside the Unknown class, say so and do not rename another class to hide it. If the 228-county rows split across classes, report the split. Do not refit either model from this plan.
