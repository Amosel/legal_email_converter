# Coordination Policy for MCP Migration

## 1) Handoff Contract

Each agent handoff must be a single JSON object:

```json
{
  "contractVersion": "1.0.0",
  "runId": "string",
  "stage": "string",
  "status": "pass|partial|fail",
  "inputs": {},
  "outputs": {},
  "warnings": [{"code": "string", "message": "string"}],
  "errors": [{"code": "string", "message": "string", "details": {}}],
  "nextActions": ["string"]
}
```

## 2) Routing Constraints

- Planner can emit plans only, cannot write production code.
- Implementer can modify code in owned modules only.
- Verifier cannot modify code; verifier only validates evidence.
- Workflow agent controls retries/resume decisions, not implementation details.

## 3) Evidence-Based Completion

A stage is complete only when:

- Output schema validates.
- Stage invariants validate.
- Required artifacts exist on disk and are referenced in output.
- Verifier confirms evidence supports status.

## 4) Failure Taxonomy and Policy

- `validation_error`: stop immediately; return actionable parameter guidance.
- `dependency_missing`: stop; emit install/remediation checklist.
- `io_error`: retry once if transient, else fail with path context.
- `parse_partial`: continue with warning and partial metrics.
- `contract_violation`: block downstream stages until resolved.

## 5) Retry and Resume

- Retries allowed only for `io_error` and transient subprocess/network/tool startup errors.
- Resume must restart from the last failed or not-started stage only.
- Completed stages are immutable unless explicit `force` is provided.

## 6) Change Control

- Contract schema changes require:
  - version bump,
  - migration note,
  - updated tests,
  - downstream approval.

## 7) Observability

- Every tool call logs: start time, end time, args hash, outcome, warning/error counts.
- Every run emits a final manifest with:
  - input references,
  - output artifacts,
  - per-stage durations,
  - failure/warning summary.

