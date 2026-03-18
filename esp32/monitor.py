"""
ESP32 Serial Monitor
Connects to ESP32 and displays CSI data output.

Usage:
    python esp32/monitor.py
    python esp32/monitor.py --port COM7 --baud 115200
"""
import os
import sys
import argparse
import serial
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))


def main():
    parser = argparse.ArgumentParser(description="ESP32 Serial Monitor")
    parser.add_argument("--port", default=os.getenv("ESP_PORT", "COM3"))
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--json", action="store_true", help="Parse JSON output")
    args = parser.parse_args()

    print(f"Connecting to {args.port} at {args.baud} baud...")
    print("Press Ctrl+C to exit\n")

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
        while True:
            line = ser.readline()
            if line:
                decoded = line.decode("utf-8", errors="replace").strip()
                if args.json and decoded.startswith("{"):
                    try:
                        data = json.loads(decoded)
                        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{ts}] {json.dumps(data, indent=2)}")
                    except json.JSONDecodeError:
                        print(decoded)
                else:
                    print(decoded)
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
    finally:
        if 'ser' in locals():
            ser.close()


if __name__ == "__main__":
    main()
