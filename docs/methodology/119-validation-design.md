# ML #119 validation design

Owning task: [ML #132](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/132). This design cites the class-count range K = 2, 3, 4, 5, and 6 in [119-analysis-spec.md](../eda/119-analysis-spec.md). The same design applies separately to the four-state fit and the tick-and-pathogen-only fit.

## Why this is not a county holdout

The estimand is a description of one national snapshot, release `governed-2026-10-15-january-climate-prod`. Every one of the 3,144 counties is in the described population. A random county K-fold would hold out counties from a census and treat dependent counties as separate draws. That is not the generalization this story asks for.

There is also no second time period, so a temporal split cannot be built. A leave-one-state-out split would answer whether a grouping travels to a hidden state. That is a different question. It is not the check used to choose the class count.

There is no outcome label, so there is no protected label holdout. `holdout_history` stays empty. The 228-county follow-up list is an evaluation question. It is not an input to class-count selection, and it is not a holdout label.

## The check that is in scope

Stability across the predeclared class counts and seeds, using the rule already frozen in the analysis spec:

1. Primary seed `1192026`. Alternate seeds `1192027`, `1192028`, `1192029`, and `1192030`. Twenty random starts at each seed. Keep the best log-likelihood start at that seed.
2. A K is stable when the median adjusted Rand index of the four alternate-seed hard assignments against the primary-seed assignment is at least 0.90.
3. A K is eligible when it is stable and every class has at least 30 counties.
4. Among eligible K, choose the smallest K whose BIC is no more than 6 above the lowest BIC in the eligible set.
5. If no K is eligible, stop. Do not widen the range, do not open the 228-county list, and do not name classes in that run.

The versioned record of those settings is [119-latent-class-v1.json](../../config/experiments/119-latent-class-v1.json). Split reference `surveillance-latent-class-stability` `v1` means the full 3,144-county release plus these five stability seeds. Experiment reference `surveillance-latent-class-experiment` `v1` is that configuration. No fit has been run.

## Nondeterminism

The seeds, the start count, and the selection rule are fixed before the fit. A different library version or a different floating-point result must be recorded with the fit. It is not a reason to change the class count after looking at the 228-county list.
