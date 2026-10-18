# ML #119 class-count selection

Owning task: [ML #133](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/133). The class count for each estimand was chosen by the rule in [119-validation-design.md](119-validation-design.md). The follow-up county list was not an input.

Code revision at the fit: `cd936fe345664e606c916b137dd642caa0d6d73b`. The estimator is the categorical latent class EM in `lyme_gap_atlas_ml.latent_class_fit`. scikit-learn supplied the adjusted Rand index only. Each start keeps the best of 20 random initializations and stops at 2,000 EM iterations or when the log-likelihood change is within 1e-8. Training ran on the local machine. No Snowflake object was written. The read context was user MATTHEWCARAWAY, role OH_LYME_PROD_READ, database ONE_HEALTH_LYME_GAP_ATLAS_PROD, schema PRESENTATION, warehouse COMPUTE_WH, and empty secondary roles. Objects read: PRESENTATION.CURRENT_RELEASE_V and PRESENTATION.CURRENT_COUNTY_ATLAS_V. The model parameters and county assignments are in [119-latent-class-v1-result.json](../../config/experiments/119-latent-class-v1-result.json).

Class identifiers are arbitrary labels from the primary seed. This note does not give them plain-language names.

Reproduce the fit from the ignored county extract after the release check:

```powershell
uv run python scripts/fit_119_latent_class.py --counties outputs/119-latent-class/counties.json --release-id governed-2026-10-15-january-climate-prod --bundle-sha256 53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d --output config/experiments/119-latent-class-v1-result.json --note docs/methodology/119-class-count-selection.md
```

## four-state

Selected class count: `4`.
Primary-seed model converged: `True`.

| Classes | BIC | Median adjusted Rand index | Smallest class | Eligible |
| ---: | ---: | ---: | ---: | --- |
| 2 | 12836.468 | 1.0000 | 820 | True |
| 3 | 12253.163 | 0.9471 | 35 | True |
| 4 | 12054.338 | 1.0000 | 35 | True |
| 5 | 12083.116 | 0.9990 | 35 | True |
| 6 | 12162.629 | 0.8060 | 33 | False |

## tick-pathogen

Selected class count: `4`.
Primary-seed model converged: `True`.

| Classes | BIC | Median adjusted Rand index | Smallest class | Eligible |
| ---: | ---: | ---: | ---: | --- |
| 2 | 10653.471 | 1.0000 | 673 | True |
| 3 | 10093.738 | 1.0000 | 68 | True |
| 4 | 9939.742 | 0.9997 | 35 | True |
| 5 | 10002.975 | 0.5700 | 15 | False |
| 6 | 10075.454 | 0.7801 | 0 | False |

A difference in library version or floating-point summation is recorded with the result dependencies. It is not a reason to change the class count.
