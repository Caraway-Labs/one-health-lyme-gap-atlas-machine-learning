# Surveillance-situation batch v1

**Batch:** `surveillance-situation-batch` `v1`.
**Owner:** Atlas ML, [story #138](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/138), [task #142](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/142).
**Model contract:** [138-surveillance-situation-models-v1.json](../../config/models/138-surveillance-situation-models-v1.json).
**Schema:** [138-surveillance-situation-batch-v1.schema.json](138-surveillance-situation-batch-v1.schema.json).

This is the handoff a Data consumer can checksum. Matthew Caraway approved `surveillance-situation-batch` v1 for that handoff at `2026-10-18T11:37:14-06:00` in [138-surveillance-situation-batch-v1-approval.json](../../config/models/138-surveillance-situation-batch-v1-approval.json). The note for the publisher is [138-surveillance-situation-data-handoff-v1.md](138-surveillance-situation-data-handoff-v1.md). This repository does not mutate production Snowflake. Release compatibility for the current Atlas release is recorded in [143-release-compatibility.md](../eda/143-release-compatibility.md). Refresh, replay, failure, rollback, and the non-risk limits are in [138-surveillance-situation-batch-v1.md](../runbooks/138-surveillance-situation-batch-v1.md).

## Artifacts

| Artifact | Path | In public Git |
| --- | --- | --- |
| Manifest | `config/models/138-surveillance-situation-batch-v1.json` | yes |
| Class dictionary | `config/models/138-surveillance-situation-class-dictionary-v1.json` | yes |
| County rows | `outputs/138-surveillance-situation-batch-v1/county-assignments.json` | no |

The county file has one row per county per fit: 3,144 five-digit FIPS rows for `surveillance-situation-four-state` v1 and 3,144 for `surveillance-situation-tick-pathogen` v1. Each row carries the version-scoped class identifier and four probabilities in contract class order. Names, descriptions, and the non-risk limits stay in the class dictionary.

The manifest records the algorithm, experiment config, dependency versions, seed `1192026`, fit git SHA, input release, bundle SHA-256, feature and missingness contracts, population scope, EM stop rule, and both checksums. `git_sha` is the fit code revision that produced the stored assignments. `result_commit` is the merge that published that result. The original fit did not record wall-clock seconds.

SHA-256 is computed on the UTF-8 JSON with LF newlines. `config/models/138-surveillance-situation-*.json` for this batch is checked out with LF endings so the dictionary checksum matches the file.

## Replay

```powershell
uv run python scripts/assemble_138_surveillance_situation_batch.py
```

The script rewrites the county file under `outputs/` and checks it against the committed manifest. It does not refit the model. A count drift stops the replay for an explicit versioned change. `--write-committed` is only for that change.

On the pinned release the four-state counts are 801, 35, 112, and 2,196. The tick-and-pathogen counts are 1,325, 1,687, 97, and 35. The 35 Unknown rows are the Alaska and Hawaii counties. Probability vectors have length 4, are finite, lie between 0 and 1, and sum to 1 within `1e-6`.

A later Atlas release does not silently inherit these assignments.
