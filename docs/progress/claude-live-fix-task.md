# Claude Live Fix Task

Read [claude-implementation-agent.md](/D:/home/ruView/agents/claude-implementation-agent.md) before making changes.

You are the implementation owner for this task.
Codex is acting as reviewer and monitor.
Treat the findings below as active issues to fix, not optional suggestions.

## Goal

Stabilize the recent live-hardware integration changes so the backend and frontend stay consistent under real runtime conditions.

## Active Findings

1. `services/signal-adapter/main.py`
   - In `handle_vitals_frame()`, the fall-event path still references `metadata` even though the code now builds `vitals_payload`.
   - This will raise a runtime error when `flags & 0x02` is true.
   - Fix this so fall events still carry correct vitals-related metadata without crashing.

2. `apps/web-monitor/src/App.tsx`
   - The `vitals` WebSocket message is currently passed into `addSignalPoint(...)`.
   - That is a schema mismatch because `signalStore` expects signal-history fields such as `time`, `rssi`, `snr`, and `csi_amplitude`.
   - Fix this with the smallest safe change.
   - If vitals data does not belong in `signalStore`, do not send it there.

3. End-to-end review
   - Re-check the live flow across:
     - `services/signal-adapter/main.py`
     - `apps/web-monitor/public/observatory/js/main.js`
     - `apps/web-monitor/src/App.tsx`
     - `apps/web-monitor/src/components/charts/KpiCards.tsx`
     - any directly related store file if needed
   - Keep live vitals support for the observatory.
   - Preserve the KPI fixes that moved occupancy to zone-based state.

## Constraints

- Make the smallest safe change set.
- Do not revert unrelated work.
- Keep the current direction of live vitals support.
- Keep the current zone-based KPI correction unless you find a real regression.

## Verification

Run relevant verification if possible.
At minimum, do one or more of:

- a targeted web-monitor build
- a relevant test command
- a Python syntax/runtime sanity check for `services/signal-adapter/main.py`

If something cannot be run, say so clearly.

## Required Response Format

### Changed
- files changed

### Fixed
- issue-by-issue summary

### Risks
- remaining concerns, if any

### Verification
- commands run and result
