#!/bin/bash
# Generates a SHA-256 witness bundle for reproducibility verification
# Usage: ./generate-witness-bundle.sh
#
# Output: dist/witness-bundle-YYYYMMDD/
#   WITNESS-LOG.md      — summary report
#   python-tests.log    — pytest output
#   ts-typecheck.log    — TypeScript tsc output
#   source-hashes.txt   — SHA-256 of all Python source files
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUNDLE_DIR="$REPO_ROOT/dist/witness-bundle-$(date +%Y%m%d)"
mkdir -p "$BUNDLE_DIR"

echo "=== ruView Witness Bundle ===" > "$BUNDLE_DIR/WITNESS-LOG.md"
echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$BUNDLE_DIR/WITNESS-LOG.md"
echo "Git commit: $(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null || echo 'unknown')" >> "$BUNDLE_DIR/WITNESS-LOG.md"
echo "Git branch: $(cd "$REPO_ROOT" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')" >> "$BUNDLE_DIR/WITNESS-LOG.md"
echo "" >> "$BUNDLE_DIR/WITNESS-LOG.md"

# ── [1/4] Python tests ─────────────────────────────────────────────────────────
echo "[1/4] Running Python tests..."
cd "$REPO_ROOT/services/signal-adapter"
python -m pytest tests/ -q --tb=short 2>&1 | tee "$BUNDLE_DIR/python-tests.log" || true
cd "$REPO_ROOT"

# ── [2/4] Frontend typecheck ──────────────────────────────────────────────────
echo "[2/4] Running TypeScript typecheck..."
pnpm --filter web-monitor typecheck 2>&1 | tee "$BUNDLE_DIR/ts-typecheck.log" || true

# ── [3/4] Hash source files ───────────────────────────────────────────────────
echo "[3/4] Hashing source files..."
find "$REPO_ROOT/services/signal-adapter" -name "*.py" | sort | while read -r f; do
    sha256sum "$f"
done > "$BUNDLE_DIR/source-hashes.txt"

# Also hash TypeScript source
find "$REPO_ROOT/apps/web-monitor/src" -name "*.ts" -o -name "*.tsx" | sort | while read -r f; do
    sha256sum "$f"
done >> "$BUNDLE_DIR/source-hashes.txt"

# ── [4/4] Summary ─────────────────────────────────────────────────────────────
echo "[4/4] Writing summary..."

PYTHON_PASSED=$(grep -c " passed" "$BUNDLE_DIR/python-tests.log" 2>/dev/null | tr -d ' ' || echo "0")
PYTHON_FAILED=$(grep -c " failed" "$BUNDLE_DIR/python-tests.log" 2>/dev/null | tr -d ' ' || echo "0")
TS_ERRORS=$(grep -c "error TS" "$BUNDLE_DIR/ts-typecheck.log" 2>/dev/null | tr -d ' ' || echo "0")
SOURCE_FILES=$(wc -l < "$BUNDLE_DIR/source-hashes.txt" | tr -d ' ')

{
    echo "## Verification Results"
    echo ""
    echo "| Check | Result |"
    echo "|-------|--------|"
    echo "| Python tests passed | $PYTHON_PASSED |"
    echo "| Python tests failed | $PYTHON_FAILED |"
    echo "| TypeScript errors   | $TS_ERRORS |"
    echo "| Source files hashed | $SOURCE_FILES |"
    echo ""
    echo "## File Manifest"
    echo ""
    echo '```'
    ls -lh "$BUNDLE_DIR/"
    echo '```'
    echo ""
    echo "## Reproduction"
    echo ""
    echo '```bash'
    echo "git checkout $(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null || echo '<commit>')"
    echo "cd infra/witness && ./generate-witness-bundle.sh"
    echo '```'
} >> "$BUNDLE_DIR/WITNESS-LOG.md"

echo ""
echo "Bundle created: $BUNDLE_DIR"
echo "  Python: $PYTHON_PASSED passed, $PYTHON_FAILED failed"
echo "  TypeScript: $TS_ERRORS errors"
echo "  Hashed: $SOURCE_FILES files"

# Exit with failure if tests or typecheck failed
if [ "$PYTHON_FAILED" -gt 0 ] || [ "$TS_ERRORS" -gt 0 ]; then
    echo "[WARN] Witness bundle contains failures — review before certifying."
    exit 1
fi
echo "[OK] Witness bundle clean."
exit 0
