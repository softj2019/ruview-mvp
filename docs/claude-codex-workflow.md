# Claude x Codex Workflow

## Roles

Claude Code owns implementation.
Codex owns review, monitoring, regression detection, and risk reporting.

## Default Loop

1. Claude reads the task and makes code changes.
2. Codex reviews the current diff or latest commit.
3. Claude fixes Codex findings, prioritizing P1 then P2.
4. Claude runs relevant verification when possible.
5. Codex performs a follow-up review.
6. The user decides when to commit or push.

## Claude Rules

- Treat Codex findings as active issues, not optional suggestions.
- Do not declare the task complete while unresolved P1 findings remain.
- Resolve P2 findings unless there is a clear reason not to; if not resolved, explain why.
- Prefer minimal, targeted changes over broad refactors unless the task requires otherwise.
- Preserve existing user changes.

## Codex Rules

- Focus review on runtime failures, data-contract mismatches, regressions, and missing verification.
- Report findings first, ordered by severity.
- Keep summaries short and actionable.

## Priority Levels

- P1: crash risk, runtime exception, broken data flow, severe logic failure
- P2: incorrect behavior, stale or misleading UI, contract mismatch, likely regression
- P3: maintainability, readability, low-risk cleanup

## Required Checks For Live Hardware Changes

- WebSocket payload shape matches frontend expectations.
- Removed variables are not still referenced on event paths.
- Stores only receive data matching their expected schema.
- Dashboard values come from authoritative live state, not stale derived guesses.
- Fallback UI values do not mask real live data.

## Claude Reporting Format

After each implementation pass, report:

### Changed
- files changed

### Fixed
- issues resolved

### Risks
- remaining assumptions or open concerns

### Verification
- tests/builds run, or clearly state what could not be run

## Completion Criteria

The task is only complete when:

- P1 findings are resolved
- P2 findings are resolved or explicitly documented
- relevant verification has been run, or inability to run it is stated clearly
