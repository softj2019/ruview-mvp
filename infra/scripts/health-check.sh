#!/bin/bash
# Quick health check for all ruView services

set -euo pipefail

RETRIES=${HEALTH_RETRIES:-1}
TIMEOUT=${HEALTH_TIMEOUT:-5}

services=(
    "signal-adapter|http://localhost:8001/health"
    "api-gateway|http://localhost:8000/health"
)

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

overall_ok=true

for entry in "${services[@]}"; do
    name="${entry%%|*}"
    url="${entry##*|}"

    ok=false
    for i in $(seq 1 $RETRIES); do
        if curl -sf --max-time "$TIMEOUT" "$url" > /dev/null 2>&1; then
            log "OK  $name  ($url)"
            ok=true
            break
        fi
        [ "$RETRIES" -gt 1 ] && log "WARN $name attempt $i/$RETRIES failed"
    done

    if ! $ok; then
        log "FAIL $name  ($url)"
        overall_ok=false
    fi
done

if $overall_ok; then
    log "All services healthy"
    exit 0
else
    log "One or more services are unhealthy"
    exit 1
fi
