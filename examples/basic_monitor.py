#!/usr/bin/env python3
"""Basic real-time monitor -- connects to signal-adapter WebSocket and prints
presence count, per-zone status, and vitals to the terminal."""

import asyncio
import json
import signal
import sys

try:
    import websockets
except ImportError:
    sys.exit("Install websockets first:  pip install websockets")

WS_URL = "ws://localhost:4100/ws/state"

ZONE_NAMES = {
    "zone_living": "Living Room",
    "zone_bedroom": "Bedroom",
    "zone_kitchen": "Kitchen",
    "zone_bathroom": "Bathroom",
}


async def monitor():
    print(f"Connecting to {WS_URL} ...")
    async with websockets.connect(WS_URL) as ws:
        print("Connected. Waiting for data...\n")
        async for raw in ws:
            msg = json.loads(raw)
            ts = msg.get("timestamp", "?")
            zones = msg.get("zones", {})
            vitals = msg.get("vitals", {})

            total = sum(1 for z in zones.values() if z.get("present"))
            lines = [f"[{ts}]  Presence: {total} person(s)"]

            for zid, zdata in zones.items():
                name = ZONE_NAMES.get(zid, zid)
                status = "OCCUPIED" if zdata.get("present") else "empty"
                lines.append(f"  {name:15s} {status}")

            if vitals:
                br = vitals.get("breathing_bpm", "--")
                hr = vitals.get("heart_bpm", "--")
                lines.append(f"  Vitals: BR {br} bpm  |  HR {hr} bpm")

            # Clear previous output and print
            print("\033[2J\033[H" + "\n".join(lines), flush=True)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    asyncio.run(monitor())
