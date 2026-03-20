"""
Provision multiple ESP32-S3 boards from the local .env configuration.

The script reads WIFI_SSID/WIFI_PASSWORD from .env, auto-detects connected
ESP32-S3 USB serial ports unless a port list is supplied, and assigns unique
node IDs and TDM slots so the boards can run as separate nodes.
"""
import argparse
import os
import socket
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from serial.tools import list_ports


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DEFAULT_PORTS = os.getenv("ESP_PORTS", "")
DEFAULT_BAUD = os.getenv("ESP_BAUD", "460800")
DEFAULT_TARGET_PORT = os.getenv("ESP_TARGET_PORT", "5005")
WIFI_SSID = os.getenv("WIFI_SSID", "")
WIFI_PASSWORD = os.getenv("WIFI_PASSWORD", "")
PROVISION_SCRIPT = ROOT / "vendor" / "ruview-temp" / "firmware" / "esp32-csi-node" / "provision.py"


def detect_target_ip():
    """Use a best-effort route lookup to find the host IP the ESP32 should target."""
    override = os.getenv("ESP_TARGET_IP", "").strip()
    if override:
        return override

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    finally:
        sock.close()


def detect_ports():
    """Return detected ESP32-S3 USB serial ports."""
    configured = [item.strip() for item in DEFAULT_PORTS.split(",") if item.strip()]
    if configured:
        return configured

    ports = []
    for port in list_ports.comports():
        if "VID:PID=303A:1001" in port.hwid.upper():
            ports.append(port.device)
    return ports


def run_provision(port, node_id, slot, total, target_ip, baud, target_port):
    """Provision a single board with node-specific settings."""
    cmd = [
        "python",
        str(PROVISION_SCRIPT),
        "--port",
        port,
        "--baud",
        str(baud),
        "--ssid",
        WIFI_SSID,
        "--password",
        WIFI_PASSWORD,
        "--target-ip",
        target_ip,
        "--target-port",
        str(target_port),
        "--node-id",
        str(node_id),
        "--tdm-slot",
        str(slot),
        "--tdm-total",
        str(total),
        "--edge-tier",
        "2",
    ]
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description="Provision all connected ESP32-S3 boards")
    parser.add_argument("--ports", help="Comma-separated serial ports, for example COM5,COM6")
    parser.add_argument("--target-ip", help="Aggregator IP address override")
    parser.add_argument("--target-port", type=int, default=int(DEFAULT_TARGET_PORT))
    parser.add_argument("--start-node-id", type=int, default=1)
    parser.add_argument("--baud", type=int, default=int(DEFAULT_BAUD))
    args = parser.parse_args()

    if not WIFI_SSID:
        raise SystemExit("WIFI_SSID is not set in .env")
    if not PROVISION_SCRIPT.exists():
        raise SystemExit(f"Missing provision script: {PROVISION_SCRIPT}")

    ports = detect_ports()
    if args.ports:
        ports = [item.strip() for item in args.ports.split(",") if item.strip()]
    if not ports:
        raise SystemExit("No ESP32-S3 USB serial ports detected")

    target_ip = args.target_ip or detect_target_ip()
    total = len(ports)

    print(f"Provisioning {total} ESP32-S3 device(s) to Wi-Fi '{WIFI_SSID}'")
    print(f"Target: {target_ip}:{args.target_port}")

    for index, port in enumerate(ports):
        node_id = args.start_node_id + index
        print(f"\n[{index + 1}/{total}] {port} -> node_id={node_id}, tdm_slot={index}/{total}")
        run_provision(
            port=port,
            node_id=node_id,
            slot=index,
            total=total,
            target_ip=target_ip,
            baud=args.baud,
            target_port=args.target_port,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
