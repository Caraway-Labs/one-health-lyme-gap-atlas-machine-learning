# Surveillance-situation batch operations v1

**Batch:** `surveillance-situation-batch` `v1`.
**Manifest:** [138-surveillance-situation-batch-v1.json](../../config/models/138-surveillance-situation-batch-v1.json).
**Compatibility:** carry forward, dated 2026-10-18, in [143-release-compatibility.md](../eda/143-release-compatibility.md).
**Owner of this procedure:** Atlas ML, [task #144](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/144).

This procedure applies only to `surveillance-situation-batch` version `v1`. That batch is pinned to release `governed-2026-10-15-january-climate-prod` and bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. Its approval state is `not_yet_approved`. This procedure writes no production Snowflake object.

A later run must not edit this batch in place. A failure must not look like a surveillance class.

## Refresh

**Owner:** the Atlas ML scientific owner. Only that owner may start a refresh, and only by a dated decision that names the new release id and bundle SHA-256.

**Release match:** before assembly, read `PRESENTATION.CURRENT_RELEASE_V` with the approved read-only role. The live release id and bundle SHA-256 must equal the pair named in that decision. A matching title or an equal county count is not enough.

**New version:** the refresh creates the next batch version, such as `surveillance-situation-batch` `v2`, with new class identifiers, a new manifest, a new dictionary, and a new county checksum. It does not change the v1 manifest, dictionary, class identifiers, or county file.

**Stop:** stop when the dated decision is missing, when the live release id or bundle differs from that decision, or when the run would overwrite v1. No scheduler, agent, or publication job may start a refresh.

## Replay

**Owner:** Atlas ML. A reviewer may replay v1. Replay does not authorize a refresh or a publication.

**Command and inputs:** from this repository, with the committed manifest, class dictionary, model contract, and stored result `config/experiments/119-latent-class-v1-result.json`:

```powershell
uv run python scripts/assemble_138_surveillance_situation_batch.py
```

The command rewrites only the gitignored county file and checks it against the committed checksums. County SHA-256 `02b62d7a4cb8970b3cd2506f5206a386a9ceed7cb2253baea16299be2d06ec9b`. Class-dictionary SHA-256 `c0fecc0766c7e485b670624793cd2b02a1c8bafd49c740bcc8db9c62e9d2494b`. The v1 release and bundle remain the carry-forward pair above. Do not pass `--write-committed` for a replay.

**Stop:** stop when the county file is missing, the checksum differs, a county is missing or duplicated, a probability is not finite, is outside 0 to 1, has a length other than 4, or sums outside `1e-6` of 1, or the release identity differs from the pin. Do not rewrite the committed manifest to make a drifted replay match.

## Failure

**Owner:** Atlas ML stops the handoff. Data, API, and Web leave the consumer unavailable. None of them may mark a partial file current.

**Stop:** a missing county, a bad probability, a release mismatch, or an unavailable county file stops the handoff. Do not fill a class, impute `Unknown`, or keep a partial batch as the current batch. `Unknown` stays the real 35-county Alaska and Hawaii class. It is not a bucket for a failed row. The consumer returns an explicit unavailable state and does not substitute another class, a zero, or a Tier 1 priority. API and web must not infer a class when this batch is unavailable.

## Rollback

**Owner:** Atlas ML names the batch a consumer may return to. Data moves the consumer pointer. API and Web display that pointer and do not choose a substitute class.

**Previous batch:** v1 is not yet approved, so there is no approved batch to restore. Until [task #145](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/145) approves one compatible batch, consumers stay unavailable. After an approval, rollback may point only at an earlier approved batch whose own compatibility note still matches the live release id and bundle SHA-256.

**Stop:** stop when no approved batch is compatible with the live release. Leave the consumer in an explicit unavailable state. Do not point at v1 while it is unapproved, and do not edit v1 rows so they resemble another batch.

## Interpretation

Class membership and class probability are not pathogen presence, disease risk, incidence, or a surveillance priority. Each class carries `must_not_be_read_as` values `disease risk`, `incidence`, `pathogen absence`, and `tier 1 priority`.

`surveillance-situation-tick-pathogen.v1.class-0`, named Established blacklegged tick, groups counties with pathogen present and counties with no pathogen record. Its probability does not measure pathogen presence. The same short name on `surveillance-situation-four-state.v1.class-0` is a different set of counties. A class identifier from one model is not a class in the other model.

`No records` stays a category. Unavailable surveillance is not zero. A later Atlas release does not silently inherit v1.
