# Durable analysis evidence

Use this directory for material EDA, statistical analysis, feature investigation,
and experiment conclusions. Name each record `<issue-number>-<short-topic>.md`
(for example `061-governed-signal-association.md`) and start from
[template.md](template.md). A concise negative, inconclusive, blocked or
not-estimable finding is valuable evidence; do not manufacture a positive result.

Before statistical execution, use the concise
[analysis specification](../methodology/analysis-spec-v1.md) to state the question,
estimand, method assumptions and stop conditions. Link it from the findings record;
it is a planning input, not a second results store.

Keep conclusions and reproduction references here, not Snowflake extracts,
generated datasets, every exploratory chart, or notebook output dumps. Store
transient outputs in ignored `outputs/` or `data/local/`. Common generated export
formats are ignored as an accidental-commit guard. Only an explicit story can
justify a small fixture or curated governed artifact; review its classification
and diff even when adding an ignored file explicitly. Ignoring is not privacy
validation. Never commit credentials, local machine paths or raw sensitive data.

Reusable SQL, scripts and configuration belong in the existing source locations.
Reference repository-relative paths and exact commands, code revision, governed
release/version and configuration assumptions. Record randomness and remaining
nondeterminism when relevant. Do not include connection names or secrets.

Link this record from existing lifecycle stage evidence and independent review
inputs; preserve canonical lineage identity. A PROCEED disposition is permission
to propose the stated next analysis, not model promotion, release, new access or
paid training authorization. Do not reuse protected holdout labels for EDA.

Analysis PR descriptions and final summaries must give the question and material
conclusion, disposition, record link, exact verification/reproduction commands,
caveats and follow-ups, and transient outputs intentionally not committed.
Code/documentation-only work may state EDA artifact N/A. Use the existing
`uv run python scripts/verify.py` gate; no separate documentation service or gate
is introduced.
