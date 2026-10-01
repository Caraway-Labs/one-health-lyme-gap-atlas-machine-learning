# Analysis specification v1 — Story #60

Write the question before choosing a method. One Markdown spec per bounded
question is enough; no registry service is required. Copy the template below
into the owning issue's planning record, then link it from the durable
[EDA record](../eda/README.md) when execution produces material findings.
An example is [analysis-spec-v1-example.md](analysis-spec-v1-example.md).

Freeze the estimand, eligibility/missingness rules and chosen method before
confirmatory execution. Record amendments and their reason; results inspected
before a change make the affected analysis exploratory. Do not choose tests,
cohorts or reporting based on attractive p-values. Disclose all analyses in an
actual hypothesis family and justify multiplicity handling only when relevant.

## Copyable template

- **Spec/version and owning issue:** <stable question ID, v1, issue link>.
- **Question / decision / allowed interpretation:** <bounded question, user
  decision it informs, intended and prohibited claims>.
- **Estimand:** <quantity, population, contrast/direction and scale; not just a test name>.
- **Unit / cohort / geography / time:** <inclusion/exclusion, observation unit,
  time window, availability cutoff, and number of independent units if known>.
- **Variables / source / version:** <definitions, units/value states, governed
  table/view, exact release/snapshot/query, revision policy and join keys>.
- **Missingness rule:** <unknown/suppressed/not-applicable handling, denominator,
  exclusions and missingness summary; never silently replace missing with zero>.
- **Exploratory or confirmatory:** <status, prior inspection, prespecified family
  and amendments; exploratory associations do not establish causation>.
- **Method / assumption rationale:** <simplest valid method and one sentence
  explaining why its assumptions fit this estimand and available evidence>.
- **Spatial / temporal dependence:** <whether repeated/neighboring units matter;
  justified grouping, dependence-aware uncertainty or descriptive-only limit>.
- **Effect-size / uncertainty output:** <estimate on stated scale, interval or
  other uncertainty, sample/coverage counts; explain any not-estimable output>.
- **Key caveat / stop conditions:** <data quality, selection, comparability,
  insufficient independent evidence, protected holdout or unresolved authority>.
- **Result disposition:** <PLANNED before execution; STOP / NOT_ESTIMABLE when
  invalid or unsupported; afterward PROCEED / REJECT / DEFER / FOLLOW_UP /
  INCONCLUSIVE with evidence and smallest next step>.
- **Reproduction / evidence:** <repository code/query/config and exact command,
  version references/seed if relevant; durable EDA record and review references
  after execution; transient outputs intentionally not committed>.

## Stop and existing contracts

STOP when source/use authority or the question is unresolved; identify the needed
decision. NOT_ESTIMABLE when available data cannot identify the estimand (for
example a change contrast with only one period). Neither means an effect is zero.
Do not substitute a different estimand or method silently. Any inference treating
dependent county-period observations as independent needs a justified correction
or must remain descriptive; naming a dependence-aware method is not proof it fits.

Use existing Frame/Data evidence and lineage references where applicable. A
descriptive analysis need not invent a predictive target, model or holdout. If an
ML lifecycle stage is not applicable, use the existing reviewed rule, not this
template as an exemption. Independent review uses the existing scientific-review
contract; dispositions do not authorize release, new access or model training.
