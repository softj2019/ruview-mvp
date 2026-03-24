#!/usr/bin/env python3
"""Fall / non-fall event recorder for ML training data collection.

Prompts the operator to label live events:
  F = fall detected, N = non-fall (normal activity), Q = quit

Each label is POSTed to the fall-detector /api/fall/record endpoint together
with a snapshot of the current CSI + camera features."""

import json
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("Install requests first:  pip install requests")

API_BASE = "http://localhost:4200"
RECORD_URL = f"{API_BASE}/api/fall/record"
STATE_URL = f"{API_BASE}/api/state/snapshot"

LABELS = {"f": "fall", "n": "non-fall"}


def get_snapshot():
    """Fetch current feature snapshot from the fall-detector service."""
    try:
        resp = requests.get(STATE_URL, timeout=3)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        print(f"  [warn] Could not fetch snapshot: {exc}")
        return {}


def record_event(label: str, snapshot: dict):
    """POST a labelled event to the recording endpoint."""
    payload = {
        "label": label,
        "timestamp": time.time(),
        "features": snapshot,
    }
    try:
        resp = requests.post(RECORD_URL, json=payload, timeout=3)
        resp.raise_for_status()
        result = resp.json()
        print(f"  Recorded as '{label}' -- id={result.get('id', '?')}")
    except requests.RequestException as exc:
        print(f"  [error] Failed to record: {exc}")


def main():
    print("=== Fall Event Recorder ===")
    print("Press:  F = fall  |  N = non-fall  |  Q = quit\n")

    count = 0
    while True:
        try:
            key = input("Label> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if key == "q":
            break
        if key not in LABELS:
            print("  Invalid key. Use F, N, or Q.")
            continue

        snapshot = get_snapshot()
        record_event(LABELS[key], snapshot)
        count += 1

    print(f"\nDone. Recorded {count} event(s).")


if __name__ == "__main__":
    main()
