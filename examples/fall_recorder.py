#!/usr/bin/env python3
"""Fall / non-fall event recorder for ML training data collection.

Prompts the operator to label live events:
  F = fall detected, N = non-fall (normal activity), Q = quit

Each label is POSTed to the fall-detector /api/fall/record endpoint together
with a snapshot of the current CSI + camera features."""

import sys

try:
    import requests
except ImportError:
    sys.exit("Install requests first:  pip install requests")

API_BASE = "http://localhost:8001"
RECORD_URL = f"{API_BASE}/api/fall/record"
DEVICES_URL = f"{API_BASE}/api/devices"

# label: True = fall, False = non-fall
LABELS = {"f": True, "n": False}
LABEL_NAMES = {True: "fall", False: "non-fall"}


def get_devices() -> list:
    """Fetch current device list to pick a device_id for auto feature extraction."""
    try:
        resp = requests.get(DEVICES_URL, timeout=3)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", []) if isinstance(data, dict) else []
    except requests.RequestException as exc:
        print(f"  [warn] Could not fetch devices: {exc}")
        return []


def pick_device(devices: list) -> str | None:
    """Return the first online device_id, or None."""
    for d in devices:
        if d.get("status") == "online":
            return d.get("id")
    return None


def record_event(label: bool, device_id: str | None):
    """POST a labelled event to the recording endpoint."""
    payload: dict = {"label": label}
    if device_id:
        payload["device_id"] = device_id
    try:
        resp = requests.post(RECORD_URL, json=payload, timeout=3)
        resp.raise_for_status()
        result = resp.json()
        print(f"  Recorded as '{LABEL_NAMES[label]}' (device={device_id or 'N/A'})")
        _ = result
    except requests.RequestException as exc:
        print(f"  [error] Failed to record: {exc}")


def main():
    print("=== Fall Event Recorder ===")
    print("Press:  F = fall  |  N = non-fall  |  Q = quit\n")

    devices = get_devices()
    device_id = pick_device(devices)
    if device_id:
        print(f"Active device: {device_id}\n")
    else:
        print("  [warn] No online devices found — recording without device_id\n")

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

        record_event(LABELS[key], device_id)
        count += 1

    print(f"\nDone. Recorded {count} event(s).")


if __name__ == "__main__":
    main()
