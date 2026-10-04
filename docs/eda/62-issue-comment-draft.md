# Draft only — wait for independent review before posting

### EDA #62 result

**Disposition:** NOT_ESTIMABLE for current DEV release
`governed-2026-09-17-unknown-coverage`. Shared PROD bulk lacks species/raw-SVI
cohort fields; a one-county detail probe confirms field availability only.
PROD cohort/source-authority admission remains blocked, not scientifically
NOT_ESTIMABLE; this is not a global source-absence conclusion.

**Groups:** Planned source-defined ESTABLISHED / REPORTED for one compatible
taxon. Neither IXODES_SCAPULARIS nor IXODES_PACIFICUS meets the positive-N screen.

**N:** ESTABLISHED / REPORTED = **0 / 0 for each taxon** in the current DEV
atlas; 3,144 unique counties per taxon are exactly `Unknown` and excluded.
Unknown is never a biological negative. Original source sampling-row N is unknown.

**Effect:** Not computed; no positive cohort, interval or real outcome statistics.

**Method:** Mann-Whitney planned, not executed on real outcomes. Spec registered
at `a05e83ccce4e27f717a16dd24f2fe1105bb59dbd`; outcome-blind atlas-route amendment
at `ccb4d0e586a19b18a9d7e2accaa0c23550525997`; directional-rank interpretation
amended before outcomes at `df1fa7914647f35120deaac841128feb0b28c6cd`.
Executable inference/effect/bootstrap code is tested on fictional inputs only.
Near-0.5 superiority is not distribution equivalence; spread/overlap retained.

**Sensitivity:** All Unknown counties span 51 state/DC codes. Positive-group
concentration/within-state contrast are inapplicable at 0 / 0. Dominant-state
exclusion, within-state descriptors and state-cluster uncertainty are implemented.

**ML implication:** No evidence yet that SVI confounds/adds information relative
to vector status. Verified shared DEV digest reproduces no positive contrast.
PROD combined tick status/derived score cannot replace species evidence/raw SVI.
A bounded approved immutable species/SVI cohort with matching source/release/
vintage/metadata authority is needed before N screening and taxon selection.
One detail record and clean visible values do not grant scientific admission.

**Product implication:** No interpretation change; Unknown is not absence.
Keep issue open pending independent review and precise PROD cohort/provenance input.

**Links:** [draft PR #88](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/88);
[artifact](62-svi-by-vector-evidence-state.md),
[spec](../methodology/62-svi-vector-evidence-spec.md),
[atlas source contract](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/main/docs/contracts/semantic-release/README.md).

Actual atlas aggregate screen `01c77e8a-040b-d63b-0064-2d070110986a`, served bundle
`55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233`:
SVI null/invalid-domain and malformed FIPS counts are zero for both taxa.
The initial observation-view-only exclusion was too narrow; the accessible
atlas route corrects that finding. No private-object retries, alternate
restricted-source identity or atlas row exports. Historical DATA200 PROD
receipts narrow provenance but do not prove current record/metadata authority.
Shared DEV SHA be74f3affff2e7753f14e7b804d672fb83d21eabe8f1dc4abead873ea21e8e45;
PROD summary SHA 5dbc0e4a66e1d702b5deafc3a430d62fe317984a6ee2e5c1759b74182f06e9ed.
One public county-detail probe, 30 seconds / 1 MB, matched PROD September 18
release/hash and exposes species/SVI fields; no national cohort N follows.
No raw rowdata uploaded or broad detail crawl. Focused suites: 44 passed;
final mandatory checks recorded in PR/artifact.
