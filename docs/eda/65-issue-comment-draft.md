# Prepared issue comment — held for Matthew's review

Do not post before independent scientific/code review of the exact PR head.

**Superseded DEV-only candidate; not ready as the final #65 result comment.**
The pre-result PROD amendment is registered at `fb0a6a8`; shared capture and
PROD analysis are pending. Replace the disposition, eligible N, table, effect,
uncertainty and implications below after that analysis and scientific review.
Keep #65 open. Retain the DEV counts as release-specific evidence only.

### EDA #65 result

**Disposition:** NOT_ESTIMABLE

**Pairing:** Ixodes scapularis or Ixodes pacificus + Borrelia burgdorferi sensu
stricto, matching the source's host-seeking Ixodes scope.

**N:** 0 eligible counties; 3,144 unique projected counties, 3,109 in scope.

**Table:** All-source vector Unknown crosses pathogen Present = 689,
source-reported No records = 2,420, Unknown = 35. The eligible 3-by-2 table
(Established / Reported / No records versus Present / No records) is all zero.
These are eligible-pair counts, not absence counts.

**Effect size:** Cramer's V and uncertainty undefined. No test/bootstrap was
run: no eligible vector contrast. The predeclared category-collapse sensitivity
also has N = 0 and an undefined effect.

**Unknown/excluded:** Both species statuses Unknown in all 3,144 counties;
3,109 in-scope counties excluded for vector unknown; 35 excluded for scope.
Pathogen Unknown = 35 overall, 0 in scope. Source-native observation counts are
not exposed by the governed projection. No access blocker: DEV read succeeded.

**ML implication:** Current release cannot establish redundancy or independent
feature value. Vector evidence has no observed variation; retain pathogen
documentation and vector availability separately. No training authorized.

**Product implication:** Preserve Unknown versus source-reported No records;
these are cumulative documentation states, not annual incidence, pathogen
absence, causal effects or individual exposure risk.

**Links:** [draft PR #91](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/pull/91);
[artifact](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/blob/codex/ml-65-vector-pathogen/docs/eda/65-vector-pathogen-state-association.md);
[source contract](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data/blob/614dbb7e95766e586e4cac6332d126e53e23933e/docs/contracts/semantic-release/README.md).
Preregistration commit `459d53d`; release
`governed-2026-09-17-unknown-coverage`. A future association requires a separately
governed release with explicit vector states; this issue makes no source-contract
or production change. Independent review and merge remain pending.

Public PROD metadata was also reachable and identifies a different immutable
release/hash; its county association was not inspected. DEV nonestimability is
not a claim about PROD or the underlying source workbook. No additional county
export was made after the shared-capture coordination instruction.
