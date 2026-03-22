"""
Morning monitoring session — 3 hours of camera + CSI data collection.

Logs camera person count vs CSI node readings every 10 seconds.
Builds a dataset for calibration and accuracy analysis.

Usage:
    python morning_monitor.py
    python morning_monitor.py --duration 180  # minutes
"""
import argparse
import csv
import json
import os
import time
import urllib.request
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "services", "signal-adapter", "logs")
SIGNAL_ADAPTER = "http://localhost:8001"
CAMERA_SERVICE = "http://localhost:8002"
INTERVAL = 10  # seconds


def fetch_json(url, timeout=2):
    try:
        r = urllib.request.urlopen(url, timeout=timeout)
        return json.loads(r.read())
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Morning monitoring session")
    parser.add_argument("--duration", type=int, default=180, help="Duration in minutes")
    args = parser.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)
    now_kst = datetime.now(KST)
    log_file = os.path.join(LOG_DIR, f"monitor_{now_kst.strftime('%Y%m%d_%H%M')}.csv")

    print(f"=== RuView Morning Monitor ===")
    print(f"Start: {now_kst.strftime('%Y-%m-%d %H:%M KST')}")
    print(f"Duration: {args.duration} minutes")
    print(f"Log: {log_file}")
    print(f"Interval: {INTERVAL}s")
    print()

    with open(log_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp_kst",
            "camera_persons",
            "csi_presence_count",
            "node1_n_persons", "node1_breath", "node1_motion", "node1_rssi",
            "node2_n_persons", "node2_breath", "node2_motion", "node2_rssi",
            "node3_n_persons", "node3_breath", "node3_motion", "node3_rssi",
            "node4_n_persons", "node4_breath", "node4_motion", "node4_rssi",
        ])

        end_time = time.time() + args.duration * 60
        sample = 0

        while time.time() < end_time:
            sample += 1
            ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

            # Camera
            cam = fetch_json(f"{CAMERA_SERVICE}/cam/health")
            cam_persons = cam.get("person_count", -1) if cam else -1

            # Signal adapter
            devices_data = fetch_json(f"{SIGNAL_ADAPTER}/api/devices")
            zones_data = fetch_json(f"{SIGNAL_ADAPTER}/api/zones")

            csi_presence = 0
            if zones_data and zones_data.get("data"):
                csi_presence = zones_data["data"][0].get("presenceCount", 0)

            nodes = {}
            if devices_data and devices_data.get("data"):
                for d in devices_data["data"]:
                    nodes[d["id"]] = d

            row = [ts, cam_persons, csi_presence]
            for nid in ["node-1", "node-2", "node-3", "node-4"]:
                n = nodes.get(nid, {})
                row.extend([
                    n.get("n_persons", -1),
                    round(n.get("breathing_bpm", 0), 1),
                    round(n.get("motion_energy", 0), 2),
                    n.get("signalStrength", 0),
                ])

            writer.writerow(row)
            f.flush()

            # Console output every 30 seconds
            if sample % 3 == 1:
                print(f"[{ts}] cam:{cam_persons} csi:{csi_presence}", end="")
                for nid in ["node-1", "node-2", "node-3", "node-4"]:
                    n = nodes.get(nid, {})
                    np_ = n.get("n_persons", "?")
                    print(f" | {nid[-1]}:{np_}", end="")
                print()

            time.sleep(INTERVAL)

    print()
    print(f"=== Monitor complete: {sample} samples ===")
    print(f"Log: {log_file}")

    # Summary
    analyze(log_file)


def analyze(log_file):
    """Quick summary of collected data."""
    import csv
    with open(log_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return

    cam_vals = [int(r["camera_persons"]) for r in rows if r["camera_persons"] != "-1"]
    csi_vals = [int(r["csi_presence_count"]) for r in rows]
    n3_vals = [int(r["node3_n_persons"]) for r in rows if r["node3_n_persons"] != "-1"]

    print()
    print("=== Summary ===")
    print(f"Samples: {len(rows)}")
    if cam_vals:
        print(f"Camera avg persons: {sum(cam_vals)/len(cam_vals):.1f} (max: {max(cam_vals)})")
    print(f"CSI avg presence: {sum(csi_vals)/len(csi_vals):.1f} (max: {max(csi_vals)})")
    if n3_vals:
        print(f"Node3 avg n_persons: {sum(n3_vals)/len(n3_vals):.1f} (max: {max(n3_vals)})")


if __name__ == "__main__":
    main()
