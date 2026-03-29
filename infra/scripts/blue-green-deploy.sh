#!/bin/bash
# Blue-Green deployment for ruView services
# Usage: ./blue-green-deploy.sh [blue|green]

set -euo pipefail

TARGET=${1:-blue}
INACTIVE=$([ "$TARGET" = "blue" ] && echo "green" || echo "blue")

BLUE_PORT_API=8000
GREEN_PORT_API=8010
BLUE_PORT_ADAPTER=8001
GREEN_PORT_ADAPTER=8011

# Port selection based on target
if [ "$TARGET" = "blue" ]; then
    PORT_API=$BLUE_PORT_API
    PORT_ADAPTER=$BLUE_PORT_ADAPTER
    INACTIVE_PORT_API=$GREEN_PORT_API
    INACTIVE_PORT_ADAPTER=$GREEN_PORT_ADAPTER
else
    PORT_API=$GREEN_PORT_API
    PORT_ADAPTER=$GREEN_PORT_ADAPTER
    INACTIVE_PORT_API=$BLUE_PORT_API
    INACTIVE_PORT_ADAPTER=$BLUE_PORT_ADAPTER
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker/docker-compose.yml"
NGINX_CONF_DIR="$REPO_ROOT/infra/nginx"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

health_check() {
    local service_name=$1
    local url=$2
    local retries=5
    local wait=3

    log "Health check: $service_name ($url)"
    for i in $(seq 1 $retries); do
        if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
            log "$service_name is healthy (attempt $i/$retries)"
            return 0
        fi
        log "Attempt $i/$retries failed. Retrying in ${wait}s..."
        sleep $wait
    done
    log "ERROR: $service_name health check failed after $retries attempts"
    return 1
}

log "Starting Blue-Green deployment: $INACTIVE -> $TARGET"
log "  api-gateway  : port $PORT_API"
log "  signal-adapter: port $PORT_ADAPTER"

# 1. Start target environment containers
log "Bringing up $TARGET environment..."
PORT_API=$PORT_API PORT_ADAPTER=$PORT_ADAPTER \
    docker compose -f "$COMPOSE_FILE" \
    -p "ruview-${TARGET}" \
    up -d --build --scale api-gateway=1 --scale signal-adapter=1

# 2. Health checks (retry 5 times)
health_check "api-gateway[$TARGET]"    "http://localhost:${PORT_API}/health"
health_check "signal-adapter[$TARGET]" "http://localhost:${PORT_ADAPTER}/health"

# 3. Nginx upstream switch via symlink
UPSTREAM_LINK="$NGINX_CONF_DIR/active-upstream.conf"
TARGET_CONF="$NGINX_CONF_DIR/upstream-${TARGET}.conf"

if [ -f "$TARGET_CONF" ]; then
    log "Switching nginx upstream to $TARGET..."
    ln -sfn "$TARGET_CONF" "$UPSTREAM_LINK"
    if command -v nginx &> /dev/null; then
        nginx -t && nginx -s reload
        log "nginx reloaded successfully"
    else
        log "WARN: nginx not found locally — manual reload required"
    fi
else
    log "WARN: $TARGET_CONF not found — skipping nginx switch"
fi

# 4. Graceful stop of inactive environment
log "Gracefully stopping $INACTIVE environment..."
docker compose -f "$COMPOSE_FILE" \
    -p "ruview-${INACTIVE}" \
    stop --timeout 30 2>/dev/null || log "WARN: $INACTIVE environment was not running"

log "Deployed to $TARGET successfully"
log "  Active:   $TARGET  (api:$PORT_API  adapter:$PORT_ADAPTER)"
log "  Inactive: $INACTIVE (api:$INACTIVE_PORT_API  adapter:$INACTIVE_PORT_ADAPTER)"
