# Claude Codex Collaboration Agent

## Role

Claude handles implementation.
Codex handles live review, regression detection, issue triage, and follow-up fixes when needed.

## When To Use

Use this agent when a task needs:

- Claude-driven implementation with terminal execution
- Codex review of diffs or recent commits
- repeated fix/review loops
- GitHub issue drafting for findings
- commit hygiene with issue references

## Operating Loop

1. Define the task and affected files.
2. Ask Claude to implement with explicit verification requirements.
3. Ask Codex to review the diff or latest commit.
4. Convert unresolved findings into:
   - immediate fixes, or
   - GitHub issues for next-phase work
5. Re-run verification.
6. Commit with issue references when issue numbers exist.

## Priority Rules

- P1: runtime failure, crash, broken event path, data loss
- P2: incorrect behavior, stale UI, contract mismatch, likely regression
- P3: maintainability, cleanup, documentation

## Required Review Focus

- WebSocket payload contracts
- backend/frontend schema consistency
- hardware/live-data freshness and fallback behavior
- state drift between dashboard, floor view, and observatory
- verification coverage before commit

## GitHub Issue Workflow

- Turn unresolved next-phase work into GitHub issues.
- Keep each issue focused on one problem.
- Use clear reproduction context, risk, and acceptance criteria.
- Reference issue numbers in the commit message once the issue exists.

## Claude Prompting Rules

- State the task, active findings, constraints, and required verification.
- Require a response with:
  - Changed
  - Fixed
  - Risks
  - Verification

## Codex Review Rules

- Findings first, summary second.
- Prefer concrete file/line references.
- Separate "fix now" from "next phase".

## Completion Criteria

- P1 findings resolved
- P2 findings resolved or documented as GitHub issues
- verification completed or explicitly blocked
- commit message references created issue numbers where applicable
