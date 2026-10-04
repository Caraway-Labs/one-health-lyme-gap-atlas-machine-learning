# ML #65 input amendment v3: governed public aggregate Ixodes state

Status: PLANNED; register and commit before public PROD category profiling,
contingency statistics or detail-probe results. This is an input representation
amendment to [v2](65-prod-scope-amendment.md), not a species-specific analysis.

## Prior inspection and reason

The supplied #63 PROD shared capture digest has been verified, and its schema
does not contain the two species states required by the v2 six-field input path.
It does contain the governed aggregate `tick_status`, `burgdorferi_status`,
scope and FIPS, with a top-level release ID. No status distribution, association
effect or uncertainty has been inspected by this agent. DEV results and public
metadata/manifest/source definitions have been inspected previously. This remains
exploratory; preserve that sequence and do not claim confirmatory registration.

Use the direct public aggregate category **only if its release/source/producer
meaning is proved compatible**. Never synthesize two species fields from it.
Question and pairing remain aggregate host-seeking **Ixodes scapularis or
Ixodes pacificus + Borrelia burgdorferi sensu stricto**. No species-specific
association, species attribution or per-species missingness counts are estimable
from this bulk payload.

## Contract-backed category meaning

At the actual reviewed build head
`7b80373187b8aa665891e2f39e6bf7f8c6fb35a1`, Data
`src/lyme_gap_atlas_data/semantic_release.py`:

- `_assemble_counties` stores `tick_status = _tick_status(scapularis_status,
  pacificus_status)` alongside the distinct species fields.
- `_tick_status` emits Established if either species is Established, otherwise
  Reported if either is Reported, otherwise Unknown if a species is Unknown,
  otherwise No records.
- `_surveillance_values` requires both explicit species statuses from each
  county source row; missing tick coverage is assigned Unknown to **both**
  species together. The restricted PROD source loader V088 validates both
  source categories as Established / Reported / No records. This is a producer
  contract/receipt guarantee, not a fresh private row-level audit.

Under this source-backed domain (both source statuses known, or both unknown),
the public aggregate equals the previously declared conservative v1/v2 union.
No records is a documentation state, not absence; Unknown is excluded, not
negative. A future producer allowing partially unknown species or changed
category/rollup meaning must stop this route; `_tick_status` alone does not
prove that partial unknowns cannot occur. Record the dependence on the closed
source domain and historical receipt binding in results.

## Fixed input and gates, before statistics

Use the supplied private #63 retained `prod-api-scores.json`, byte SHA-256
`5dbc0e4a66e1d702b5deafc3a430d62fe317984a6ee2e5c1759b74182f06e9ed`.
Use its existing five-response manifest and retained metadata/source files.
No second bulk fetch, warehouse identity, grant, internal/raw source access or
3,144-detail fanout is permitted. Required gates:

1. Scores file and every manifest-referenced retained response agree with their
   SHA-256/byte bounds; verify top-level release ID and method.
2. Before/after metadata agree on published release
   `governed-2026-09-18-unknown-coverage`, bundle
   `038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026`,
   schema 1.0.0, method semantic-1.0.0, with cumulative tick/pathogen vintages
   through 2025-12-31. Scores request is pinned via `dataset_version`.
3. Public source identities and separate dataset IDs match the exact historical
   build manifest; preserve source version/run/artifact/SHA receipt references.
   Public visibility does not independently establish private metadata authority
   or fresh raw source lineage. No training/admission/publication is authorized.
4. Validate exactly 3,144 unique five-digit FIPS, explicit scope boolean and
   source-faithful aggregate/pathogen states; verify the supplied normalized FIPS
   digest. Do not use derived score components or human outcomes.
5. Make **one** documented county-detail GET for fixed FIPS `01001`, pinned to
   this release, at most 30 seconds / 262,144 bytes. Compare its release/hash,
   FIPS, scope, species-domain validity and aggregate rollup with the shared bulk
   county record. This checks projection compatibility, not representative
   sampling or an association. No county selection based on observed outcomes,
   no retries/fanout. An inaccessible detail route is an access/projection blocker,
   not scientific NOT_ESTIMABLE. Any mismatch stops aggregate execution.

The detail probe cannot prove the entire cohort's private source lineage; the
closed source domain and whole-release producer meaning must come from the
existing source/manifest/build-publication contracts. If those gates cannot be
supported, report the precise remaining paired-state/meaning input rather than
relaxing the rule or generalizing DEV nonestimability to PROD.

## Unchanged analysis and limits

Estimand: county-level Cramer's V on aggregate Established / Reported /
source-reported No records versus pathogen Present / source-reported No records,
restricted to explicit contiguous scope and known categories. Unknown families,
scope exclusions and overlap remain explicit. Source observation counts remain
unavailable; unique county N is separate. Population/percentiles/score components
are unused. Cumulative states are not annual incidence or biological absence.

Use the same expected-cell rule, capped fixed-margin exact alternative,
effect/uncertainty, state-cluster robustness plan (2,000 replicates, seed 6501),
heuristic disposition bins, and **one** prespecified sensitivity collapsing
Established + Reported to Documented while retaining No records. No additional
pairing, category or significance-driven method choice. No causal/exposure
claims. State robustness does not eliminate spatial/reporting dependence.

Implement and test direct aggregate analysis without manufacturing species
states. If gates pass, run once on the retained real payload and commit material
aggregate conclusions only. Scientific/code review and the final single issue
comment remain held; no merge/close or new capture is authorized by this plan.
