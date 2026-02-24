# MCP Agent DAG

## Nodes

- `A0` Contract Architecture
  - Owner: Architect
  - Output: tool schemas, run manifest schema, error taxonomy
- `A1` Repository Decomposition
  - Owner: Refactor Lead
  - Output: modular library boundaries, migration map
- `A2` Safety Policy
  - Owner: Security Engineer
  - Output: allowed-root and write policy, idempotency rules
- `A3` MCP Runtime Scaffold
  - Owner: Platform Engineer
  - Output: server skeleton, tool routing, validation layer
- `A4` Export Vertical Slice
  - Owner: Feature Engineer
  - Output: `export_mbox_for_llm` as non-interactive MCP tool
- `A5` Full Tool Migration
  - Owner: Feature Squad
  - Output: archive/convert/report/filter tools
- `A6` Run Orchestrator
  - Owner: Workflow Engineer
  - Output: `run_id`, stage state machine, resume semantics
- `A7` UX Reliability Layer
  - Owner: UX Systems Engineer
  - Output: preflight, dry-run, progress, remediation messages
- `A8` Performance Hardening
  - Owner: Performance Engineer
  - Output: streaming, concurrency, retry/timeout, cancellation
- `A9` Verification and Release
  - Owner: QA and Docs
  - Output: full test matrix, release checklist, operator docs

## Edges (Adjacency List)

- `A0 -> A1`
- `A0 -> A2`
- `A1 -> A3`
- `A2 -> A3`
- `A3 -> A4`
- `A3 -> A5`
- `A4 -> A7`
- `A5 -> A6`
- `A5 -> A8`
- `A6 -> A7`
- `A6 -> A8`
- `A7 -> A9`
- `A8 -> A9`

## Coordination Rules

- Every edge requires a machine-validated handoff artifact (`JSON`).
- No downstream agent starts until schema validation passes.
- Contract changes require Architect approval and version bump.
- Verifier gate is mandatory after each node (`pass`, `partial`, `fail`).
- Failures must emit typed `failure_code` plus remediation text.

## Skill Prompts (Templates)

- Architect prompt:
  - "Define minimal MCP tool contracts with explicit parameters and typed outputs; remove hidden state."
- Refactor prompt:
  - "Extract pure services from scripts; keep wrappers thin; no behavior changes unless required by contract."
- Platform prompt:
  - "Implement strict input/output validation, structured errors, and deterministic result payloads."
- Verifier prompt:
  - "Validate evidence against expected contract; reject unsupported success claims."
- Workflow prompt:
  - "Model stage execution as finite states with resumability and idempotent reruns."

