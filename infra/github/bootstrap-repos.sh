#!/bin/bash
set -euo pipefail

# RuView MVP - GitHub Repository Bootstrap Script
# Usage: bash infra/github/bootstrap-repos.sh

REPO_NAME="ruview-mvp"
DESCRIPTION="RuView - Open-source CSI-based presence/fall detection service MVP"

echo "=== RuView Repository Bootstrap ==="

# Load environment
if [ -f ".env" ]; then
    source .env
    export GITHUB_TOKEN
else
    echo "ERROR: .env file not found"
    exit 1
fi

# Get GitHub username
OWNER=$(gh api user --jq '.login')
echo "GitHub User: $OWNER"

# Create repository
echo "Creating repository..."
gh repo create "$REPO_NAME" \
    --public \
    --description "$DESCRIPTION" \
    --source . \
    --remote origin \
    --push || echo "Repository may already exist"

# Create develop branch
echo "Creating develop branch..."
git checkout -b develop 2>/dev/null || git checkout develop
git push -u origin develop
git checkout main

# Create labels
echo "Creating labels..."
declare -a LABEL_NAMES=(
    "agent:hardware" "agent:signal" "agent:frontend"
    "agent:observatory" "agent:devops" "agent:qa"
    "priority:critical" "priority:high" "priority:medium" "priority:low"
    "type:feature" "type:bugfix" "type:infra" "type:docs"
    "phase:0-setup" "phase:1-hardware" "phase:2-adapter"
    "phase:3-frontend" "phase:4-observatory" "phase:5-deploy" "phase:6-demo"
)

declare -a LABEL_COLORS=(
    "0E8A16" "1D76DB" "5319E7"
    "D93F0B" "006B75" "BFD4F2"
    "B60205" "D93F0B" "FBCA04" "0E8A16"
    "A2EEEF" "D73A4A" "C5DEF5" "0075CA"
    "6F42C1" "6F42C1" "6F42C1"
    "6F42C1" "6F42C1" "6F42C1" "6F42C1"
)

for i in "${!LABEL_NAMES[@]}"; do
    gh label create "${LABEL_NAMES[$i]}" \
        --repo "$OWNER/$REPO_NAME" \
        --color "${LABEL_COLORS[$i]}" \
        --force 2>/dev/null || true
done

# Create milestones
echo "Creating milestones..."
gh api repos/$OWNER/$REPO_NAME/milestones \
    --method POST \
    --field title="M0 - Setup & Bootstrap" \
    --field description="Repository, CI/CD, development environment setup" \
    2>/dev/null || true

gh api repos/$OWNER/$REPO_NAME/milestones \
    --method POST \
    --field title="M1 - Hardware Integration" \
    --field description="ESP32-S3 CSI data collection working" \
    2>/dev/null || true

gh api repos/$OWNER/$REPO_NAME/milestones \
    --method POST \
    --field title="M2 - Signal Processing" \
    --field description="Python adapter processing CSI events" \
    2>/dev/null || true

gh api repos/$OWNER/$REPO_NAME/milestones \
    --method POST \
    --field title="M3 - 2D Monitor UI" \
    --field description="React dashboard with floor view" \
    2>/dev/null || true

gh api repos/$OWNER/$REPO_NAME/milestones \
    --method POST \
    --field title="M4 - 3D Observatory" \
    --field description="3D visualization integrated" \
    2>/dev/null || true

gh api repos/$OWNER/$REPO_NAME/milestones \
    --method POST \
    --field title="M5 - Production Deploy" \
    --field description="Cloudflare Pages + Tunnel live" \
    2>/dev/null || true

echo "=== Bootstrap Complete ==="
