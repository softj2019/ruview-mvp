# Claude Task Prompt

Read [claude-codex-workflow.md](/D:/home/ruView/docs/claude-codex-workflow.md) first and follow it for this task.

You are the implementation owner. Codex is acting as reviewer/monitor. Treat Codex findings as active issues to fix.

## Current Task

Fix the remaining issues in the latest live-hardware integration work.

## Confirmed Findings To Address

1. `services/signal-adapter/main.py`
   - In `handle_vitals_frame()`, the fall-event path still references `metadata` even though the code was changed to use `vitals_payload`.
   - This will raise a runtime error when `flags & 0x02` is true.
   - Fix it safely so fall events still include the correct vitals-related metadata.

2. `apps/web-monitor/src/App.tsx`
   - The new `vitals` websocket message is currently passed into `addSignalPoint(...)`.
   - That is a schema mismatch because `signalStore` expects signal-history fields like `time`, `rssi`, `snr`, and `csi_amplitude`.
   - Fix this so `vitals` messages do not corrupt signal history.
   - Prefer a minimal fix. If vitals do not belong in the signal store, do not send them there.

3. Review the related flow end-to-end:
   - `services/signal-adapter/main.py`
   - `apps/web-monitor/public/observatory/js/main.js`
   - `apps/web-monitor/src/App.tsx`
   - `apps/web-monitor/src/components/charts/KpiCards.tsx`
   - any directly related store file if needed

## Constraints

- Make the smallest safe change set.
- Do not revert unrelated work.
- Keep live vitals support for the observatory.
- Preserve the KPI fixes that moved occupancy to zone-based state.

## Verification

Run relevant verification if possible.
At minimum, do one of:

- a targeted build for the web monitor, or
- a relevant test command, or
- a quick runtime syntax check for the Python service

If something cannot be run, say so clearly.

## Required Output

When done, report exactly in this structure:

### Changed
- files changed

### Fixed
- issue-by-issue summary

### Risks
- remaining concerns, if any

### Verification
- commands run and result
