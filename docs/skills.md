# Shared ML agent skills

`.agents/skills/<name>/SKILL.md` is the canonical version-controlled project
skills surface. Read a matching entry point when its description fits the task.
Repository and workspace `AGENTS.md`, the governance baseline, accepted ADRs,
and approved contracts remain authoritative. A skill is a procedure, not new
permission or scientific policy. Story #38 establishes this catalog.

## Catalog

| Skill | Trigger |
| --- | --- |
| `snowflake-context-check` | Before any agent Snowflake action |
| `snowflake-readonly-analysis` | Approved bounded Snowflake inspection |
| `agentic-ml-lifecycle` | Lifecycle stage or gate planning/reporting |
| `ml-dataset-contract` | ML dataset scope or contract work |
| `ml-experiment` | Experiment planning or implementation |
| `ml-model-evaluation` | Evaluation design or evidence review |
| `arize-ml-observability` | Arize integration or telemetry planning |
| `ml-scientific-review` | Independent scientific review |
| `ml-reproducibility-audit` | Reproduction evidence audit |

Read only applicable skills. Add references, templates, or scripts only when
they have a current use.

## Maintenance

- Use lowercase `kebab-case` names matching the directory and frontmatter.
  Keep names stable. The Git revision versions a skill. Record breaking
  workflow changes in the owning issue and review affected contracts or ADRs.
- Extend an existing skill when trigger and authority stay the same. Create a
  new skill for a distinct recurring workflow. Review scope, safety boundaries,
  description, and links against the owning issue.
- Before deprecation, document the successor and migration here and in the
  skill. Search for callers and wrappers; update them in the same review.
- Validate frontmatter, directory/name agreement, relative links, and actual
  discovery in available harnesses. Run repository quality gates. Discovery
  checks do not prove future lifecycle, Snowflake, or Arize integration.

## Harnesses

The workspace exposes canonical `.agents/skills/` entries to Codex and OpenCode.
Cursor also has `.cursor/skills/` discovery entries in this checkout; each
contains only frontmatter and a relative link to the canonical ML skill.
Local path resolution is verified, while interactive Cursor loading has not
been tested. Cortex Code repository discovery is also unverified; open the
canonical entry point explicitly until demonstrated. Harness wrappers must
never copy the policy body. Harness-specific subagents are secondary and
cannot define competing scientific, security, or access policy.
