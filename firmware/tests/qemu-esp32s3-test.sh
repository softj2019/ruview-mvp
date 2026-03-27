#!/bin/bash
# QEMU ESP32-S3 firmware smoke test
# Usage: ./qemu-esp32s3-test.sh [firmware.bin]
#
# Requirements:
#   - QEMU with ESP32-S3 target support (requires esp-idf >= v5.5 with QEMU patches)
#   - Download: https://github.com/espressif/qemu/releases
#   - Build: esp-idf/tools/install.sh qemu
#
# What this tests:
#   - Firmware binary exists and is non-zero
#   - QEMU can load and boot the image without immediate panic
#   - Serial output contains expected boot messages
#   - CSI task initializes successfully (log: "csi_recv_cb registered")
#   - UDP socket opens on expected port (log: "UDP socket ready :5500")

set -euo pipefail

FIRMWARE="${1:-vendor/ruview-temp/firmware/esp32-csi-node/build/esp32-csi-node.bin}"
BOOT_TIMEOUT=10  # seconds to wait for boot messages
EXPECTED_LOGS=(
    "boot: ESP-IDF"
    "csi_recv_cb"
    "UDP socket ready"
)

# ── Colour helpers ──────────────────────────────────────────────────────────────
PASS_CLR='\033[0;32m'
FAIL_CLR='\033[0;31m'
SKIP_CLR='\033[1;33m'
INFO_CLR='\033[0;36m'
NC='\033[0m'

pass() { echo -e "${PASS_CLR}[PASS]${NC} $*"; }
fail() { echo -e "${FAIL_CLR}[FAIL]${NC} $*"; }
skip() { echo -e "${SKIP_CLR}[SKIP]${NC} $*"; }
info() { echo -e "${INFO_CLR}[QEMU]${NC} $*"; }

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

# ── Test: firmware binary exists ───────────────────────────────────────────────
info "Testing firmware: $FIRMWARE"
info "Checking binary exists..."
if [ -f "$FIRMWARE" ]; then
    SIZE=$(wc -c < "$FIRMWARE")
    pass "Firmware found (${SIZE} bytes)"
    ((PASS_COUNT++))
else
    skip "Firmware not built yet — run 'idf.py build' in esp32/ directory"
    ((SKIP_COUNT++))
    # Non-fatal: continue with remaining checks
fi

# ── Test: binary size sanity ───────────────────────────────────────────────────
if [ -f "$FIRMWARE" ]; then
    MIN_SIZE=65536  # 64 KB minimum for a real ESP32 image
    if [ "$SIZE" -ge "$MIN_SIZE" ]; then
        pass "Firmware size sane (${SIZE} >= ${MIN_SIZE} bytes)"
        ((PASS_COUNT++))
    else
        fail "Firmware too small (${SIZE} < ${MIN_SIZE} bytes) — possibly truncated build"
        ((FAIL_COUNT++))
    fi
fi

# ── Test: QEMU availability ────────────────────────────────────────────────────
info "ESP32-S3 QEMU target: requires esp-idf >= v5.5 with QEMU support"
info "Run: qemu-system-xtensa -machine esp32s3 -nographic -kernel $FIRMWARE"

if command -v qemu-system-xtensa &>/dev/null; then
    QEMU_VERSION=$(qemu-system-xtensa --version 2>&1 | head -1)
    info "QEMU found: $QEMU_VERSION"

    # Check for esp32s3 machine support
    if qemu-system-xtensa -machine help 2>&1 | grep -q "esp32s3"; then
        pass "QEMU ESP32-S3 machine target available"
        ((PASS_COUNT++))

        # ── Run QEMU boot test (if firmware exists) ────────────────────────────
        if [ -f "$FIRMWARE" ]; then
            info "Booting firmware in QEMU (timeout: ${BOOT_TIMEOUT}s)..."
            QEMU_LOG=$(mktemp /tmp/ruview-qemu-XXXXXX.log)

            timeout "$BOOT_TIMEOUT" qemu-system-xtensa \
                -machine esp32s3 \
                -nographic \
                -no-reboot \
                -serial file:"$QEMU_LOG" \
                -kernel "$FIRMWARE" \
                2>&1 || true

            for expected in "${EXPECTED_LOGS[@]}"; do
                if grep -q "$expected" "$QEMU_LOG" 2>/dev/null; then
                    pass "Boot log contains: '$expected'"
                    ((PASS_COUNT++))
                else
                    fail "Boot log missing: '$expected'"
                    ((FAIL_COUNT++))
                fi
            done

            rm -f "$QEMU_LOG"
        fi
    else
        skip "QEMU ESP32-S3 machine not available in this build — install Espressif QEMU fork"
        skip "  https://github.com/espressif/qemu/releases"
        ((SKIP_COUNT++))
    fi
else
    skip "qemu-system-xtensa not found in PATH"
    skip "Install: https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/get-started/tools.html"
    ((SKIP_COUNT++))
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "=================================="
echo " QEMU Smoke Test Results"
echo "=================================="
echo -e "  ${PASS_CLR}PASS${NC}: $PASS_COUNT"
echo -e "  ${FAIL_CLR}FAIL${NC}: $FAIL_COUNT"
echo -e "  ${SKIP_CLR}SKIP${NC}: $SKIP_COUNT"
echo "=================================="

if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi
exit 0
