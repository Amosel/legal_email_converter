# Proposal: Research Before Implementation Skill

## Document Status

- Date: 2026-03-10
- Status: Draft
- Audience: Builder agent
- Proposed skill name: `research-before-implementation`

## Purpose

Build a reusable Codex skill named `research-before-implementation` that helps turn fuzzy project discussions into structured planning artifacts before implementation begins.

This proposal is for the agent that will build the skill. It summarizes the intended scope, artifact model, data flow, decision rules, and constraints derived from the work already completed in this repository.

## Why This Skill Exists

The workflow developed in this repository revealed a repeatable pattern:

- define canonical requirements first
- separate open questions from product decisions
- turn stories into repeatable eval cases
- maintain a dependency-aware research tracker
- avoid implementing until ambiguity is reduced enough

This is more than generic organization. It is a research and readiness workflow for complex, ambiguous software work.

## Intended Skill Outcome

Given a new feature, product, migration, workflow, or skill idea, the skill should help another Codex instance produce a compact planning set such as:

- canonical PRD artifact
- stateful research tracker
- machine-readable eval cases
- optional contract audit
- optional decision log
- optional heuristics ledger

The skill should bias toward reducing uncertainty before code is written.

## Scope

### In Scope

- turning loose problem statements into a canonical PRD
- extracting user stories into structured, addressable entries
- extracting unresolved questions into a stateful research tracker
- splitting bundled research questions into atomic items
- adding dependencies, complexity, priority, and next actions to research items
- deriving eval cases from requirements
- distinguishing canonical requirements from audits and supporting artifacts
- documenting decision rules for prioritization and evidence standards

### Out of Scope

- implementing the target product or feature itself
- acting as a domain-specific skill for one product area
- forcing a heavyweight project-management system
- requiring a single repo layout for all users
- building a full task runner unless a minimal one becomes necessary

## Proposed Skill Name

`research-before-implementation`

## Core Skill Promise

Use this skill when Codex should reduce ambiguity, model dependencies, and create structured planning artifacts before writing implementation code.

## Source Artifacts To Learn From

These files in the current repository already contain the relevant patterns:

- `skill_prd.yaml`
- `research.yaml`
- `skill_eval_cases.json`
- `SKILL_USER_STORIES.md`
- `proposals/research-before-implementation-skill-proposal.md`

These files are examples and source material. The new skill should not copy them verbatim. It should generalize the workflow.

## Artifact Model

The skill should be able to produce or guide production of the following artifacts.

### 1. Canonical PRD

Preferred shape:

- machine-readable first
- markdown companion optional

Recommended filename pattern:

- `*_prd.yaml`

Required characteristics:

- clear scope and non-goals
- structured user stories
- requirements separated from audits
- explicit implementation and testing decisions

### 2. Research Tracker

Preferred shape:

- YAML

Recommended filename:

- `research.yaml`

Required characteristics:

- stable item IDs
- explicit state
- priority
- complexity
- dependencies
- next action
- evidence
- decision field

### 3. Eval Fixture

Preferred shape:

- JSON

Recommended filename:

- `*_eval_cases.json`

Required characteristics:

- stable case IDs
- prompt or scenario input
- expected route or behavior
- assertions
- forbidden claims
- optional evidence level

### 4. Contract Audit

Preferred shape:

- Markdown

Optional filename:

- `contract_audit.md`

Required characteristics:

- clearly not canonical requirements
- maps requirements to current system behavior
- highlights `match`, `partial`, `mismatch`

### 5. Decision Log

Preferred shape:

- YAML

Optional filename:

- `decisions.yaml` or `adr_log.yaml`

Required characteristics:

- local decisions
- rationale
- consequences
- references to upstream heuristics or research items when applicable

## Data Flow

The skill should guide work in this sequence unless there is a strong reason to deviate.

1. Intake
- Gather the project idea, request, or problem statement.
- Identify whether the user wants planning, implementation, or both.

2. Canonicalize
- Produce or normalize the PRD first.
- Keep user stories in the PRD.

3. Extract uncertainty
- Move unresolved implementation, validation, and policy questions into `research.yaml`.
- Split combined questions into atomic items.

4. Prioritize research
- Add dependencies, complexity, and next actions.
- Rank upstream blockers before downstream refinements.

5. Derive evals
- Convert PRD user stories into machine-readable eval cases.
- Keep evals aligned with current contract boundaries.

6. Audit if needed
- Produce a contract audit only if there is an existing system to compare against.

7. Decide implementation readiness
- If critical research items remain unresolved, do not proceed directly to implementation.

## Decision Rules

The skill should apply these rules consistently.

### Rule 1: User Stories Live In The PRD

- User stories should not live primarily in audit or research documents.

### Rule 2: Research Is Stateful

- Open questions are not prose notes.
- They should be tracked as structured items with state and next action.

### Rule 3: Canonical Beats Companion

- Prefer one canonical structured artifact and optional readable companions.
- Do not let multiple files compete as the source of truth.

### Rule 4: Separate Discovery From Policy

- If one item asks both "what is true?" and "how should we phrase it?", split it.

### Rule 5: Dependency Pressure Beats Local Convenience

- Upstream blockers should be ranked before downstream refinement items.

### Rule 6: Do Not Overclaim Verification

- If behavior is only specified in product docs but not validated in runtime review, mark it as partial rather than verified.

### Rule 7: Research Before Implementation

- Do not jump into code when critical ambiguity remains and a planning artifact would resolve it more cheaply.

## Prioritization Method

Use a dependency-first prioritization model with economic calibration.

Primary ordering:

- critical path and dependency structure

Secondary ordering:

- cost of delay, risk reduction, and enablement

Tertiary ordering:

- effort and confidence

The current repository encoded this as:

- dependency-first sequencing
- WSJF-style value and risk thinking
- confidence as a caution flag, not the main sort key

## Considerations For The Builder Agent

### Keep It General

- Do not overfit the skill to legal evidence processing.
- The legal-email-converter repository is the source example, not the target domain.

### Keep It Lightweight

- The skill should not require a heavy framework.
- It should work for small, medium, and large efforts.

### Prefer Structured Artifacts

- YAML for planning and research
- JSON for eval cases
- Markdown only for narrative companions and audits

### Support Multi-Agent Use

- Research items should be assignable and independently actionable.
- Artifacts should support many terminal windows and many concurrent agents without ambiguity.

### Avoid Parallel Sources Of Truth

- If a canonical YAML exists, companion markdown should say so explicitly.

## Minimum Deliverables For V1

The builder agent should aim to create a skill with:

- `SKILL.md`
- `agents/openai.yaml`
- `references/`
  - `artifact-model.md`
  - `research-tracker.md`
  - `prioritization.md`
  - `eval-fixtures.md`

The skill should teach another agent to generate:

- `*_prd.yaml`
- `research.yaml`
- `*_eval_cases.json`
- optional `contract_audit.md`
- optional `decisions.yaml`

## Suggested Skill Trigger Description

Use when Codex is asked to design, scope, plan, or prepare implementation for a feature, product, workflow, migration, or skill and should first reduce ambiguity, identify dependencies, create structured planning artifacts, and determine readiness before writing code.

## Suggested Evaluation Questions For The New Skill

- Does it keep user stories in the PRD?
- Does it create a stateful research tracker instead of prose-only notes?
- Does it derive eval cases from requirements?
- Does it avoid making audits into the canonical requirements source?
- Does it split bundled research items into atomic tasks?
- Does it prioritize upstream blockers before downstream refinements?
- Does it avoid implementation when unresolved research remains on the critical path?

## Build Sequence Recommendation

1. Read `skill_prd.yaml`, `research.yaml`, and `skill_eval_cases.json` from this repository as source patterns.
2. Draft the new skill’s `SKILL.md` around the workflow, not around this repo’s domain.
3. Define the skill’s artifact model in focused reference files.
4. Generate `agents/openai.yaml`.
5. Validate the skill structure.
6. Run the new skill against one or two fresh planning problems to see whether it produces clean artifacts.

## Notes On Current Repo Knowledge

The current repository produced several useful conclusions that should be generalized into the new skill:

- canonical structured artifacts reduce ambiguity
- companion markdown can remain useful, but should not compete with the canonical artifact
- contract audits are useful but should stay non-canonical
- research questions should be split into atomic items when they mix discovery and policy
- eval cases should be machine-readable and derived from user stories

## Handoff Summary

Build a general-purpose planning skill that teaches Codex to research before implementation. Use the artifacts in this repository as evidence of the workflow, but generalize them into a reusable, lightweight skill rather than a domain-specific one.
