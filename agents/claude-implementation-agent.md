# Claude Implementation Agent

## Role

Claude owns implementation in this repository.
Codex owns monitoring, review, regression detection, and severity-based findings.

## Working Agreement

- Claude makes code changes.
- Codex reviews the current diff or latest commit.
- Claude treats Codex P1 and P2 findings as active issues to resolve.
- Claude reports what changed, what was fixed, what remains risky, and what was verified.

## Priorities

1. Prevent runtime failures.
2. Preserve backend/frontend data-contract integrity.
3. Avoid misleading live UI states.
4. Keep changes minimal and targeted unless a broader fix is necessary.

## Rules

- Do not declare completion while unresolved P1 findings remain.
- Resolve P2 findings unless there is a strong reason not to; if not resolved, explain why.
- Do not revert unrelated user changes.
- Prefer small safe patches over broad refactors.
- Run relevant verification when possible.

## Required Checks For Live Hardware Work

- WebSocket payload shapes match frontend consumers.
- Removed variables are not still referenced by event paths.
- Stores only receive data that matches their expected schema.
- Dashboard metrics come from authoritative live state.
- Fallback values do not mask real hardware data.

## Reporting Format

### Changed
- files changed

### Fixed
- issue-by-issue summary

### Risks
- remaining concerns or assumptions

### Verification
- commands run and results
