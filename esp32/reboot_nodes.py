"""
Reboot all ESP32 nodes by re-uploading the current firmware via OTA.

OTA upload triggers esp_restart() on the device, effectively rebooting it.
Run this when the room is empty so calibration captures ambient noise level.

Usage:
    python reboot_nodes.py
    python reboot_nodes.py --nodes 10.0.0.246 10.0.0.199
"""
import argparse
import subprocess
import sys
import time
import urllib.request
import json

DEFAULT_FIRMWARE = "d:/home/ruView/vendor/ruview-temp/firmware/esp32-csi-node/build/esp32-csi-node.bin"
SIGNAL_ADAPTER_URL = "http://localhost:8001/api/devices"
OTA_PORT = 8032


def get_node_ips():
    """Fetch online node IPs from signal-adapter."""
    try:
        r = urllib.request.urlopen(SIGNAL_ADAPTER_URL, timeout=3)
        data = json.loads(r.read())["data"]
        return [d["mac"] for d in data if d.get("status") == "online" and d.get("mac")]
    except Exception as e:
        print(f"[warn] Could not fetch nodes from signal-adapter: {e}")
        return []


def reboot_node(ip, firmware_path):
    """Reboot a node by OTA re-upload."""
    url = f"http://{ip}:{OTA_PORT}/ota"
    print(f"  Rebooting {ip} via OTA...")
    try:
        result = subprocess.run(
            [
                "curl", "-s", "--max-time", "60",
                "-X", "POST", url,
                "--data-binary", f"@{firmware_path}",
                "-H", "Content-Type: application/octet-stream",
            ],
            capture_output=True, text=True, timeout=70,
        )
        if result.returncode == 0:
            print(f"  {ip}: OK (rebooting)")
        else:
            print(f"  {ip}: failed ({result.stderr.strip()})")
    except Exception as e:
        print(f"  {ip}: error ({e})")


def main():
    parser = argparse.ArgumentParser(description="Reboot ESP32 nodes via OTA")
    parser.add_argument("--nodes", nargs="+", help="Node IPs (default: auto-detect)")
    parser.add_argument("--firmware", default=DEFAULT_FIRMWARE, help="Firmware binary path")
    args = parser.parse_args()

    ips = args.nodes or get_node_ips()
    if not ips:
        print("[error] No nodes found")
        sys.exit(1)

    print(f"Rebooting {len(ips)} node(s) for calibration...")
    print(f"Firmware: {args.firmware}")
    print()

    for ip in ips:
        reboot_node(ip, args.firmware)
        time.sleep(2)

    print()
    print("All nodes rebooting. Calibration will complete in ~60 seconds.")


if __name__ == "__main__":
    main()
