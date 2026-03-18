"""
ESP32-S3 Device Setup Script
Detects connected ESP32 device, validates chip type, and prepares for RuView firmware.

Usage:
    python esp32/setup_device.py
    python esp32/setup_device.py --flash  (flash firmware after build)
"""
import os
import sys
import subprocess
import argparse
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

ESP_PORT = os.getenv("ESP_PORT", "COM3")
ESP_CHIP = os.getenv("ESP_CHIP", "esp32s3")
ESP_BAUD = os.getenv("ESP_BAUD", "460800")
ESP_FLASH_SIZE = os.getenv("ESP_FLASH_SIZE", "8MB")
WIFI_SSID = os.getenv("WIFI_SSID", "")
WIFI_PASSWORD = os.getenv("WIFI_PASSWORD", "")


def detect_device():
    """Detect and validate connected ESP32 device."""
    print(f"[1/4] Detecting device on {ESP_PORT}...")
    try:
        result = subprocess.run(
            ["python", "-m", "esptool", "--port", ESP_PORT, "chip-id"],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout + result.stderr
        print(output)

        if "ESP32-S3" in output:
            print("✓ ESP32-S3 detected!")
            return "esp32s3"
        elif "ESP32-D0" in output or "ESP32" in output:
            print("⚠ ESP32 (original) detected. RuView firmware requires ESP32-S3.")
            print("  Current device can be used for basic CSI collection only.")
            return "esp32"
        else:
            print("✗ No compatible device found")
            return None
    except subprocess.TimeoutExpired:
        print("✗ Timeout - check USB connection")
        return None
    except FileNotFoundError:
        print("✗ esptool not found. Run: pip install esptool")
        return None


def build_firmware():
    """Build RuView firmware using Docker."""
    print(f"\n[2/4] Building firmware for {ESP_CHIP}...")
    firmware_dir = os.path.join(os.path.dirname(__file__), "../vendor/ruview-temp/firmware/esp32-csi-node")

    if not os.path.exists(firmware_dir):
        print("✗ Firmware source not found. Clone RuView first.")
        return False

    if ESP_CHIP != "esp32s3":
        print("⚠ Skipping firmware build - RuView requires ESP32-S3")
        return False

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{os.path.abspath(firmware_dir)}:/project",
        "-w", "/project",
        "espressif/idf:v5.2",
        "bash", "-c",
        "rm -rf build sdkconfig && idf.py set-target esp32s3 && idf.py build"
    ]

    print(f"Running: docker ...")
    result = subprocess.run(cmd, timeout=600)
    if result.returncode == 0:
        print("✓ Firmware build successful!")
        return True
    else:
        print("✗ Firmware build failed")
        return False


def flash_firmware():
    """Flash firmware to ESP32-S3."""
    print(f"\n[3/4] Flashing firmware to {ESP_PORT}...")
    firmware_dir = os.path.join(os.path.dirname(__file__), "../vendor/ruview-temp/firmware/esp32-csi-node")
    build_dir = os.path.join(firmware_dir, "build")

    bootloader = os.path.join(build_dir, "bootloader", "bootloader.bin")
    partition = os.path.join(build_dir, "partition_table", "partition-table.bin")
    app = os.path.join(build_dir, "esp32-csi-node.bin")

    for f in [bootloader, partition, app]:
        if not os.path.exists(f):
            print(f"✗ Missing: {f}")
            print("  Run build_firmware() first or use pre-built binaries")
            return False

    cmd = [
        "python", "-m", "esptool",
        "--chip", "esp32s3",
        "--port", ESP_PORT,
        "--baud", ESP_BAUD,
        "write_flash",
        "--flash_mode", "dio",
        "--flash_size", ESP_FLASH_SIZE,
        "0x0", bootloader,
        "0x8000", partition,
        "0x10000", app,
    ]

    print(f"Flashing to {ESP_PORT} at {ESP_BAUD} baud...")
    result = subprocess.run(cmd, timeout=120)
    if result.returncode == 0:
        print("✓ Flash successful!")
        return True
    else:
        print("✗ Flash failed")
        return False


def provision_wifi():
    """Provision WiFi credentials to ESP32-S3."""
    print(f"\n[4/4] Provisioning WiFi...")
    if not WIFI_SSID:
        print("⚠ WIFI_SSID not set in .env")
        return False

    provision_script = os.path.join(
        os.path.dirname(__file__),
        "../vendor/ruview-temp/firmware/esp32-csi-node/provision.py"
    )

    if not os.path.exists(provision_script):
        print("⚠ provision.py not found, using esptool NVS write")
        return False

    # Get local IP for target-ip
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
    finally:
        s.close()

    cmd = [
        "python", provision_script,
        "--port", ESP_PORT,
        "--ssid", WIFI_SSID,
        "--password", WIFI_PASSWORD,
        "--target-ip", local_ip,
    ]

    print(f"Setting WiFi: {WIFI_SSID}, Target IP: {local_ip}")
    result = subprocess.run(cmd, timeout=30)
    if result.returncode == 0:
        print("✓ WiFi provisioned!")
        return True
    else:
        print("✗ WiFi provisioning failed")
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

    chip = detect_device()

    if args.detect:
        return

    if chip == "esp32s3" and args.flash:
        if build_firmware():
            flash_firmware()
        provision_wifi()
    elif args.provision:
        provision_wifi()
    elif chip == "esp32s3":
        print("\nDevice ready. Use --flash to build and flash firmware.")
        print("Use --provision to set WiFi credentials only.")
    else:
        print("\n⚠ ESP32-S3 not detected. Current device limitations:")
        print("  - Cannot run RuView full firmware")
        print("  - Mock server available for development")
        print("  - Connect ESP32-S3-DevKitC-1 when available")


if __name__ == "__main__":
    main()
