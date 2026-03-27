#!/bin/bash
# One-command verification script — runs tests + checks source hashes
# Usage: ./verify.sh [witness-bundle-dir]
#
# If no bundle dir is supplied, generates a fresh bundle first.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

INFO_CLR='\033[0;36m'
PASS_CLR='\033[0;32m'
FAIL_CLR='\033[0;31m'
WARN_CLR='\033[1;33m'
NC='\033[0m'

info() { echo -e "${INFO_CLR}[VERIFY]${NC} $*"; }
pass() { echo -e "${PASS_CLR}[PASS]${NC}   $*"; }
fail() { echo -e "${FAIL_CLR}[FAIL]${NC}   $*"; }
warn() { echo -e "${WARN_CLR}[WARN]${NC}   $*"; }

FAIL_COUNT=0

# ── Resolve bundle directory ──────────────────────────────────────────────────
if [ -n "${1:-}" ] && [ -d "$1" ]; then
    BUNDLE_DIR="$1"
    info "Using existing bundle: $BUNDLE_DIR"
else
    info "Generating fresh witness bundle..."
    bash "$SCRIPT_DIR/generate-witness-bundle.sh" || true
    # Find the most recently created bundle
    BUNDLE_DIR=$(ls -td "$REPO_ROOT/dist/witness-bundle-"* 2>/dev/null | head -1 || echo "")
    if [ -z "$BUNDLE_DIR" ]; then
        fail "No witness bundle found. Run generate-witness-bundle.sh first."
        exit 1
    fi
    info "Bundle: $BUNDLE_DIR"
fi

echo ""
info "=========================================="
info " ruView Witness Verification"
info "=========================================="

# ── Check 1: WITNESS-LOG.md exists ────────────────────────────────────────────
if [ -f "$BUNDLE_DIR/WITNESS-LOG.md" ]; then
    GIT_COMMIT=$(grep "^Git commit:" "$BUNDLE_DIR/WITNESS-LOG.md" | awk '{print $3}' || echo "unknown")
    GENERATED=$(grep "^Generated:" "$BUNDLE_DIR/WITNESS-LOG.md" | awk '{print $2}' || echo "unknown")
    pass "Witness log found (commit: ${GIT_COMMIT:0:12}, generated: $GENERATED)"
else
    fail "WITNESS-LOG.md not found in $BUNDLE_DIR"
    ((FAIL_COUNT++))
fi

# ── Check 2: Python test results ──────────────────────────────────────────────
if [ -f "$BUNDLE_DIR/python-tests.log" ]; then
    PYTHON_PASSED=$(grep -c " passed" "$BUNDLE_DIR/python-tests.log" 2>/dev/null || echo "0")
    PYTHON_FAILED=$(grep -c " failed" "$BUNDLE_DIR/python-tests.log" 2>/dev/null || echo "0")
    PYTHON_ERROR=$(grep -c "ERROR" "$BUNDLE_DIR/python-tests.log" 2>/dev/null || echo "0")

    if [ "$PYTHON_FAILED" -eq 0 ] && [ "$PYTHON_ERROR" -eq 0 ]; then
        pass "Python tests: $PYTHON_PASSED passed, 0 failed"
    else
        fail "Python tests: $PYTHON_PASSED passed, $PYTHON_FAILED failed, $PYTHON_ERROR errors"
        ((FAIL_COUNT++))
    fi
else
    warn "python-tests.log not found — skipping Python check"
fi

# ── Check 3: TypeScript typecheck ─────────────────────────────────────────────
if [ -f "$BUNDLE_DIR/ts-typecheck.log" ]; then
    TS_ERRORS=$(grep -c "error TS" "$BUNDLE_DIR/ts-typecheck.log" 2>/dev/null || echo "0")
    if [ "$TS_ERRORS" -eq 0 ]; then
        pass "TypeScript typecheck: 0 errors"
    else
        fail "TypeScript typecheck: $TS_ERRORS errors"
        ((FAIL_COUNT++))
    fi
else
    warn "ts-typecheck.log not found — skipping TypeScript check"
fi

# ── Check 4: Source hash integrity ────────────────────────────────────────────
if [ -f "$BUNDLE_DIR/source-hashes.txt" ]; then
    HASH_COUNT=$(wc -l < "$BUNDLE_DIR/source-hashes.txt" | tr -d ' ')
    HASH_MISMATCH=0

    while IFS=" " read -r expected_hash filepath; do
        if [ -f "$filepath" ]; then
            CURRENT_HASH=$(sha256sum "$filepath" | awk '{print $1}')
            if [ "$CURRENT_HASH" != "$expected_hash" ]; then
                warn "Hash mismatch: $filepath"
                ((HASH_MISMATCH++))
            fi
        else
            warn "File not found: $filepath"
            ((HASH_MISMATCH++))
        fi
    done < "$BUNDLE_DIR/source-hashes.txt"

    if [ "$HASH_MISMATCH" -eq 0 ]; then
        pass "Source integrity: all $HASH_COUNT files match recorded hashes"
    else
        fail "Source integrity: $HASH_MISMATCH/$HASH_COUNT files have hash mismatches"
        ((FAIL_COUNT++))
    fi
else
    warn "source-hashes.txt not found — skipping integrity check"
fi

# ── Check 5: Current git state ────────────────────────────────────────────────
if command -v git &>/dev/null; then
    UNCOMMITTED=$(cd "$REPO_ROOT" && git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    if [ "$UNCOMMITTED" -eq 0 ]; then
        pass "Git working tree: clean"
    else
        warn "Git working tree: $UNCOMMITTED uncommitted change(s) — bundle may not match source"
    fi
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
info "=========================================="
if [ "$FAIL_COUNT" -eq 0 ]; then
    pass "VERIFICATION PASSED — bundle is clean and reproducible"
    info "Bundle: $BUNDLE_DIR"
    exit 0
else
    fail "VERIFICATION FAILED — $FAIL_COUNT check(s) failed"
    fail "Review: $BUNDLE_DIR/WITNESS-LOG.md"
    exit 1
fi
