# MCP Migration TODO

Status legend: `[ ]` not started, `[-]` in progress, `[x]` done.

## P0 Foundation

- [ ] P0-1 Create `src/legal_email_converter/` and move shared logic out of scripts.
  - Size: M
  - Depends on: none
- [ ] P0-2 Remove interactive prompts from MCP paths and require explicit params.
  - Size: M
  - Depends on: P0-1
- [ ] P0-3 Define MCP tool schemas and error taxonomy.
  - Size: M
  - Depends on: P0-1
- [ ] P0-4 Build MCP server scaffold and wire first vertical slice (`export_mbox_for_llm`).
  - Size: M
  - Depends on: P0-2, P0-3
- [ ] P0-5 Add path safety and idempotency policy (allowed roots, overwrite handling).
  - Size: M
  - Depends on: P0-1
- [ ] P0-6 Add `preflight` tool for dependencies and filesystem checks.
  - Size: S
  - Depends on: P0-3, P0-5
- [ ] P0-7 Add structured run/result manifest schema.
  - Size: M
  - Depends on: P0-3, P0-4
- [ ] P0-8 Deduplicate `.msg -> mbox` logic into one shared service.
  - Size: M
  - Depends on: P0-1
- [ ] P0-9 Add contract tests for schemas and error handling.
  - Size: M
  - Depends on: P0-3, P0-4
- [ ] P0-10 Refresh docs for MCP mode and remove stale references.
  - Size: S
  - Depends on: P0-4

## P1 Core UX and Reliability

- [ ] P1-1 Implement full MCP tool set (extract, convert, OCR, reports, filter, export).
  - Size: L
  - Depends on: P0-1, P0-3, P0-8
- [ ] P1-2 Add `run_id` lifecycle and persisted stage states.
  - Size: L
  - Depends on: P0-7
- [ ] P1-3 Add stage resume support.
  - Size: L
  - Depends on: P1-2
- [ ] P1-4 Replace silent failures with structured warnings/errors by file context.
  - Size: M
  - Depends on: P0-3
- [ ] P1-5 Add scan-only and dry-run estimate tools.
  - Size: M
  - Depends on: P1-1
- [ ] P1-6 Add deterministic artifact naming/versioning.
  - Size: S
  - Depends on: P0-5, P0-7
- [ ] P1-7 Expand test coverage across all pipeline modules.
  - Size: L
  - Depends on: P1-1, P1-4
- [ ] P1-8 Add per-run audit log resource.
  - Size: M
  - Depends on: P1-2

## P2 Scale and Operations

- [ ] P2-1 Stream large mailbox processing to keep memory bounded.
  - Size: L
  - Depends on: P1-1
- [ ] P2-2 Add bounded concurrency + retry/timeout policy for OCR.
  - Size: L
  - Depends on: P1-1
- [ ] P2-3 Add cancellation support for long-running jobs.
  - Size: M
  - Depends on: P1-2
- [ ] P2-4 Add benchmark/regression suite for large datasets.
  - Size: M
  - Depends on: P2-1, P2-2
- [ ] P2-5 Add PII-redacted logging and retention controls.
  - Size: M
  - Depends on: P1-8
- [ ] P2-6 Add operator playbook mapped by error code.
  - Size: S
  - Depends on: P1-4, P1-8

## Active Work Queue

- [-] A1 Introduce reusable non-interactive export service entrypoint.
- [ ] A2 Add MCP contracts and first tool schema.
- [ ] A3 Scaffold MCP server and wire export vertical slice.

