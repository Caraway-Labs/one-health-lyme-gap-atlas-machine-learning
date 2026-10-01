# Shared ML agent skills

`.agents/skills/<name>/SKILL.md` is the canonical version-controlled project
skills surface. Read a matching entry point when its description fits the task.
Repository and workspace `AGENTS.md`, the governance baseline, accepted ADRs,
and approved contracts remain authoritative. A skill is a procedure, not new
permission or scientific policy. Story #38 establishes the four essential entry points below.

## Essential starting set

Start with `snowflake-context-check`, `agentic-ml-lifecycle`, `ml-experiment`, and
`ml-scientific-review`. Open only the skill needed for the current task.
The auxiliary entries below remain available for existing callers.
Add no further skill unless an active story demonstrates repeated workflow value
that `AGENTS.md` or an existing skill cannot handle cleanly.

## Existing entries

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

Keep one concise canonical body per skill; reference authoritative policy and
existing scripts/docs. Keep lowercase `kebab-case` names aligned with directory
and frontmatter. Run `uv run python scripts/verify.py` after changes; review
adapter links when changing a name or location.

## Harnesses

The workspace exposes canonical `.agents/skills/` entries to Codex and OpenCode.
Cursor also has `.cursor/skills/` discovery entries in this checkout; each
contains only frontmatter and a relative link to the canonical ML skill.
Local path resolution is verified, while interactive Cursor loading has not
been tested. Cortex Code repository discovery is also unverified; open the
canonical entry point explicitly until demonstrated. Harness wrappers must
never copy the policy body. Harness-specific subagents are secondary and
cannot define competing scientific, security, or access policy.
