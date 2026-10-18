# Data handoff for surveillance-situation batch v1

**Approver:** Matthew Caraway.
**Approved at:** `2026-10-18T11:37:14-06:00`.
**Batch:** `surveillance-situation-batch` `v1`.
**Approval record:** [138-surveillance-situation-batch-v1-approval.json](../../config/models/138-surveillance-situation-batch-v1-approval.json).
**Publisher:** [Data #702](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/issues/702).
**Downstream of that publication:** [API #253](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-api/issues/253) and [web #650](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-web/issues/650).

This note authorizes Data #702 to receive one immutable batch. This repository does not mutate production Snowflake. API routes and web screens stay downstream of the Data publication.

## What to publish

| Item | Location |
| --- | --- |
| Schema | [138-surveillance-situation-batch-v1.schema.json](138-surveillance-situation-batch-v1.schema.json) |
| Manifest | [138-surveillance-situation-batch-v1.json](../../config/models/138-surveillance-situation-batch-v1.json) |
| Class dictionary | [138-surveillance-situation-class-dictionary-v1.json](../../config/models/138-surveillance-situation-class-dictionary-v1.json) |
| County rows | `outputs/138-surveillance-situation-batch-v1/county-assignments.json` |
| Operating procedure | [138-surveillance-situation-batch-v1.md](../runbooks/138-surveillance-situation-batch-v1.md) |
| Release decision | [143-release-compatibility.md](../eda/143-release-compatibility.md) |

The county file is not in public Git. Rebuild it with:

```powershell
uv run python scripts/assemble_138_surveillance_situation_batch.py
```

County SHA-256: `02b62d7a4cb8970b3cd2506f5206a386a9ceed7cb2253baea16299be2d06ec9b`.

Class-dictionary SHA-256: `c0fecc0766c7e485b670624793cd2b02a1c8bafd49c740bcc8db9c62e9d2494b`.

## Models and lineage

| Model | Version |
| --- | --- |
| `surveillance-situation-four-state` | `v1` |
| `surveillance-situation-tick-pathogen` | `v1` |

The fit git SHA is `cd936fe345664e606c916b137dd642caa0d6d73b`. The result commit is `a2f9bad41f1ddb793e364399afbdd5fbad008b7a`. The input release is `governed-2026-10-15-january-climate-prod`. The bundle SHA-256 is `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. Compatibility is carry forward, dated 2026-10-18. A later Atlas release does not silently inherit this batch.

## Missing rows and errors

Each fit has 3,144 counties. A probability vector has length 4, is finite, lies between 0 and 1, and sums to 1 within `1e-6`. Four-state counts are 801, 35, 112, and 2,196. Tick-and-pathogen counts are 1,325, 1,687, 97, and 35. The 35 Unknown rows are the Alaska and Hawaii counties. `Unknown` is a real class. `No records` stays a category. Do not impute.

A missing county, a repeated FIPS, a bad probability, a release mismatch, a count change without a new batch version, or an unavailable county file stops the handoff. The consumer returns an explicit unavailable state and does not substitute another class, a zero, or a Tier 1 priority. API and web must not infer a class when this batch is unavailable.

Class membership and class probability are not pathogen presence, disease risk, incidence, or a surveillance priority. `surveillance-situation-tick-pathogen.v1.class-0` groups pathogen present and no pathogen record. Its probability does not measure pathogen presence.
