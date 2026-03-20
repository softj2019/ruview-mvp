"""
ESP32-S3 device setup helper.

Detects a connected ESP32-S3, validates the chip, and optionally provisions
Wi-Fi settings using the project firmware tooling.
"""
import argparse
import os
import subprocess

from dotenv import load_dotenv
from serial.tools import list_ports


load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

ESP_PORT = os.getenv("ESP_PORT", "")
ESP_CHIP = os.getenv("ESP_CHIP", "esp32s3")
ESP_BAUD = os.getenv("ESP_BAUD", "460800")
ESP_FLASH_SIZE = os.getenv("ESP_FLASH_SIZE", "16MB")
WIFI_SSID = os.getenv("WIFI_SSID", "")
WIFI_PASSWORD = os.getenv("WIFI_PASSWORD", "")


def find_default_port():
    """Return the configured port or the first detected ESP32-S3 USB port."""
    if ESP_PORT:
        return ESP_PORT

    for port in list_ports.comports():
        if "VID:PID=303A:1001" in port.hwid.upper():
            return port.device
    return None


def detect_device(port):
    """Detect and validate the connected device on the given port."""
    print(f"[1/4] Detecting device on {port}...")
    try:
        result = subprocess.run(
            ["python", "-m", "esptool", "--port", port, "chip-id"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = result.stdout + result.stderr
        print(output)

        if "ESP32-S3" in output:
            print("[ok] ESP32-S3 detected")
            return "esp32s3"
        if "ESP32-D0" in output or "ESP32" in output:
            print("[warn] ESP32 (original) detected. RuView firmware requires ESP32-S3.")
            print("  Current device can be used for basic CSI collection only.")
            return "esp32"

        print("[warn] No compatible device found")
        return None
    except subprocess.TimeoutExpired:
        print("[warn] Timeout - check USB connection")
        return None
    except FileNotFoundError:
        print("[warn] esptool not found. Run: pip install esptool")
        return None


def build_firmware():
    """Build RuView firmware using Docker."""
    print(f"\n[2/4] Building firmware for {ESP_CHIP}...")
    firmware_dir = os.path.join(
        os.path.dirname(__file__),
        "../vendor/ruview-temp/firmware/esp32-csi-node",
    )

    if not os.path.exists(firmware_dir):
        print("[warn] Firmware source not found. Clone RuView first.")
        return False

    if ESP_CHIP != "esp32s3":
        print("[warn] Skipping firmware build - RuView requires ESP32-S3")
        return False

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{os.path.abspath(firmware_dir)}:/project",
        "-w",
        "/project",
        "espressif/idf:v5.2",
        "bash",
        "-c",
        "rm -rf build sdkconfig && idf.py set-target esp32s3 && idf.py build",
    ]

    print("Running: docker ...")
    result = subprocess.run(cmd, timeout=600)
    if result.returncode == 0:
        print("[ok] Firmware build successful")
        return True

    print("[warn] Firmware build failed")
    return False


def flash_firmware(port):
    """Flash firmware to ESP32-S3."""
    print(f"\n[3/4] Flashing firmware to {port}...")
    firmware_dir = os.path.join(
        os.path.dirname(__file__),
        "../vendor/ruview-temp/firmware/esp32-csi-node",
    )
    build_dir = os.path.join(firmware_dir, "build")

    bootloader = os.path.join(build_dir, "bootloader", "bootloader.bin")
    partition = os.path.join(build_dir, "partition_table", "partition-table.bin")
    app = os.path.join(build_dir, "esp32-csi-node.bin")

    for file_path in [bootloader, partition, app]:
        if not os.path.exists(file_path):
            print(f"[warn] Missing: {file_path}")
            print("  Run build_firmware() first or use pre-built binaries")
            return False

    cmd = [
        "python",
        "-m",
        "esptool",
        "--chip",
        "esp32s3",
        "--port",
        port,
        "--baud",
        ESP_BAUD,
        "write_flash",
        "--flash_mode",
        "dio",
        "--flash_size",
        ESP_FLASH_SIZE,
        "0x0",
        bootloader,
        "0x8000",
        partition,
        "0x10000",
        app,
    ]

    print(f"Flashing to {port} at {ESP_BAUD} baud...")
    result = subprocess.run(cmd, timeout=120)
    if result.returncode == 0:
        print("[ok] Flash successful")
        return True

    print("[warn] Flash failed")
    return False


def provision_wifi(port):
    """Provision Wi-Fi credentials to ESP32-S3."""
    print("\n[4/4] Provisioning WiFi...")
    if not WIFI_SSID:
        print("[warn] WIFI_SSID not set in .env")
        return False

    provision_script = os.path.join(
        os.path.dirname(__file__),
        "../vendor/ruview-temp/firmware/esp32-csi-node/provision.py",
    )

    if not os.path.exists(provision_script):
        print("[warn] provision.py not found")
        return False

    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        local_ip = sock.getsockname()[0]
    finally:
        sock.close()

    cmd = [
        "python",
        provision_script,
        "--port",
        port,
        "--ssid",
        WIFI_SSID,
        "--password",
        WIFI_PASSWORD,
        "--target-ip",
        local_ip,
    ]

    print(f"Setting WiFi: {WIFI_SSID}, Target IP: {local_ip}")
    result = subprocess.run(cmd, timeout=30)
    if result.returncode == 0:
        print("[ok] WiFi provisioned")
        return True

    print("[warn] WiFi provisioning failed")
    return False


def main():
    parser = argparse.ArgumentParser(description="ESP32-S3 Device Setup")
    parser.add_argument("--flash", action="store_true", help="Build and flash firmware")
    parser.add_argument("--provision", action="store_true", help="Provision WiFi only")
    parser.add_argument("--detect", action="store_true", help="Detect device only")
    args = parser.parse_args()

    print("=" * 50)
    print("  RuView ESP32-S3 Device Setup")
    print("=" * 50)

    port = find_default_port()
    if not port:
        print("[warn] No ESP32 USB serial device was detected")
        return

    chip = detect_device(port)

    if args.detect:
        return

    if chip == "esp32s3" and args.flash:
        if build_firmware():
            flash_firmware(port)
        provision_wifi(port)
    elif args.provision:
        provision_wifi(port)
    elif chip == "esp32s3":
        print(f"\nDevice ready on {port}. Use --flash to build and flash firmware.")
        print("Use --provision to set WiFi credentials only.")
    else:
        print("\n[warn] ESP32-S3 not detected. Current device limitations:")
        print("  - Cannot run RuView full firmware")
        print("  - Mock server available for development")
        print("  - Connect ESP32-S3-DevKitC-1 when available")


if __name__ == "__main__":
    main()
