# Arize agent tooling spike — Story #44

Decision (2026-10-01): **DEFER** optional agent tooling. The existing Atlas
SDK boundary and local evidence contracts are sufficient for the current use
case. This is a bounded tooling decision, not a hosted Arize capability benchmark.

## Current use case and tested evidence

An agent needs to inspect a telemetry failure and subsequent recovery without
changing an approved prediction or mistaking missing evidence for degradation.
The existing Story #43 JSON evidence and validators support that inspection
without another service or credential. From the repository root:

```powershell
uv run --extra dev pytest -q tests/test_monitoring_policy.py::test_telemetry_failure_and_recovery_preserve_prediction tests/test_monitoring_policy.py::test_label_states tests/test_monitoring_policy.py::test_revision_is_not_drift_or_degradation
```

Result: **3 passed**. Failure remains `unknown` / `unavailable_telemetry`, recovery
is a separate linked event, and the original prediction is unchanged. Missing
or immature labels and unavailable baselines remain unknown; small samples are
insufficient evidence. Source revision is not predictive degradation. These are
synthetic contract tests, not evidence of a live model's performance or delivery.

## One optional candidate

The [official Arize AX CLI README](https://github.com/Arize-ai/arize-ax-cli/blob/main/README.md)
was inspected on 2026-10-01. Its executable is `ax` (Python 3.11+), with an API-key
configuration surface. It documents `ax experiments export` for hosted experiment
runs and project/span/trace inspection. The latter does not establish support for
this Atlas traditional-ML monitoring evidence contract. No documented export was
shown to replace the current local failure/recovery inspection or preserve all
Atlas sufficiency and identity semantics automatically.

`ax` is not installed in this task environment; no Arize MCP tools are registered
in this session. The runtime API-key and approved test-space variables are absent
(presence checked only). No approved hosted model/evidence reference was supplied
for this spike. These observations describe this session, not account inventory.
The CLI was **not installed or executed**, and no hosted read or comparative
latency/usability measurement occurred. There is therefore no demonstrated
advantage sufficient to add a dependency and authentication surface now.

## Boundary and revisit condition

No CLI, MCP, upstream skill, tracing stack, credential, export destination, or
runtime implementation is added. No Snowflake objects or hosted Arize resources
were read or written. No EDA, profiling, model experimentation, or training was
performed; the EDA artifact requirement is **N/A**.

Atlas's [integration boundary](arize-integration.md),
[monitoring policy](contracts/monitoring-policy-v1.md), and
[canonical Arize skill](../.agents/skills/arize-ml-observability/SKILL.md) remain
authoritative. Vendor tools cannot authorize telemetry, change identity, approve
release, or reinterpret missing evidence. The existing optional synthetic DEV
delivery proof remains separate from this read-only tooling question.

Revisit only when a current task identifies an approved hosted evidence reference
and a concrete inspection pain point that the SDK/API cannot efficiently address.
Then test one bounded read against the existing path using approved least-privilege
access; retain the Atlas semantics and report actual comparative evidence before
adopting. No speculative integration is needed to close this story as DEFER.
