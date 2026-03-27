#!/bin/bash
# Blue-Green Deployment — ruView signal-adapter + api-gateway
# Usage: ./deploy.sh [blue|green]
#
# Blue environment:  api-gateway :8000, signal-adapter :8001
# Green environment: api-gateway :8010, signal-adapter :8011
#
# Flow:
#   1. Bring up the inactive environment
#   2. Health-check the new environment
#   3. Switch Nginx upstream to the new environment
#   4. Drain and stop the old environment
#   5. Rollback on health-check failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NGINX_CONF="$SCRIPT_DIR/nginx.conf"
COMPOSE_FILE="$REPO_ROOT/docker/docker-compose.yml"

BLUE_API_PORT=8000
BLUE_ADAPTER_PORT=8001
GREEN_API_PORT=8010
GREEN_ADAPTER_PORT=8011

HEALTH_RETRIES=10
HEALTH_INTERVAL=3  # seconds

# ── Colour output ──────────────────────────────────────────────────────────────
GREEN_CLR='\033[0;32m'
RED_CLR='\033[0;31m'
YELLOW_CLR='\033[1;33m'
NC='\033[0m'

log()     { echo -e "${GREEN_CLR}[DEPLOY]${NC} $*"; }
warn()    { echo -e "${YELLOW_CLR}[WARN]${NC}  $*"; }
error()   { echo -e "${RED_CLR}[ERROR]${NC} $*" >&2; }

# ── Detect current active slot ─────────────────────────────────────────────────
detect_active() {
    if grep -q "server localhost:${BLUE_API_PORT};" "$NGINX_CONF" 2>/dev/null && \
       ! grep -q "# server localhost:${BLUE_API_PORT};" "$NGINX_CONF" 2>/dev/null; then
        echo "blue"
    else
        echo "green"
    fi
}

# ── Health check a service ─────────────────────────────────────────────────────
health_check() {
    local port="$1"
    local name="$2"
    local url="http://localhost:${port}/health"

    log "Health-checking $name at $url ..."
    for i in $(seq 1 "$HEALTH_RETRIES"); do
        if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
            log "$name is healthy (attempt $i/$HEALTH_RETRIES)"
            return 0
        fi
        warn "Attempt $i/$HEALTH_RETRIES failed, retrying in ${HEALTH_INTERVAL}s..."
        sleep "$HEALTH_INTERVAL"
    done

    error "$name failed health check after $HEALTH_RETRIES attempts"
    return 1
}

# ── Switch Nginx upstream ──────────────────────────────────────────────────────
switch_nginx() {
    local target_slot="$1"
    local target_api_port target_adapter_port

    if [ "$target_slot" = "blue" ]; then
        target_api_port=$BLUE_API_PORT
        target_adapter_port=$BLUE_ADAPTER_PORT
    else
        target_api_port=$GREEN_API_PORT
        target_adapter_port=$GREEN_ADAPTER_PORT
    fi

    log "Switching Nginx upstream to $target_slot (api:$target_api_port, adapter:$target_adapter_port)..."

    # Update nginx.conf — uncomment target, comment out the other
    if [ "$target_slot" = "blue" ]; then
        sed -i \
            -e "s|^    # server localhost:${BLUE_API_PORT};.*|    server localhost:${BLUE_API_PORT}; # blue (active)|" \
            -e "s|^    server localhost:${GREEN_API_PORT};.*|    # server localhost:${GREEN_API_PORT}; # green (standby)|" \
            "$NGINX_CONF"
    else
        sed -i \
            -e "s|^    server localhost:${BLUE_API_PORT};.*|    # server localhost:${BLUE_API_PORT}; # blue (standby)|" \
            -e "s|^    # server localhost:${GREEN_API_PORT};.*|    server localhost:${GREEN_API_PORT}; # green (active)|" \
            "$NGINX_CONF"
    fi

    # Reload Nginx gracefully
    if command -v nginx &>/dev/null; then
        nginx -t -c "$NGINX_CONF" && nginx -s reload
        log "Nginx reloaded successfully."
    elif command -v docker &>/dev/null && docker ps --filter "name=ruview-nginx" --format '{{.Names}}' | grep -q nginx; then
        docker exec ruview-nginx nginx -s reload
        log "Nginx container reloaded successfully."
    else
        warn "Nginx not found locally — updated nginx.conf only. Reload manually."
    fi
}

# ── Start a deployment slot ────────────────────────────────────────────────────
start_slot() {
    local slot="$1"
    local api_port adapter_port

    if [ "$slot" = "blue" ]; then
        api_port=$BLUE_API_PORT
        adapter_port=$BLUE_ADAPTER_PORT
    else
        api_port=$GREEN_API_PORT
        adapter_port=$GREEN_ADAPTER_PORT
    fi

    log "Starting $slot environment (api:$api_port, adapter:$adapter_port)..."

    docker compose -f "$COMPOSE_FILE" \
        -p "ruview-${slot}" \
        --env-file "$REPO_ROOT/.env" \
        up -d \
        --build \
        -e API_GATEWAY_PORT="$api_port" \
        -e SIGNAL_ADAPTER_PORT="$adapter_port" \
        api-gateway signal-adapter

    log "$slot environment started."
}

# ── Stop a deployment slot ─────────────────────────────────────────────────────
stop_slot() {
    local slot="$1"
    log "Stopping $slot environment..."
    docker compose -f "$COMPOSE_FILE" -p "ruview-${slot}" down --remove-orphans || true
    log "$slot environment stopped."
}

# ── Rollback ───────────────────────────────────────────────────────────────────
rollback() {
    local failed_slot="$1"
    local safe_slot="$2"

    error "Deployment to $failed_slot failed — rolling back to $safe_slot."
    stop_slot "$failed_slot"
    switch_nginx "$safe_slot"
    log "Rollback complete. $safe_slot is active."
    exit 1
}

# ── Main ───────────────────────────────────────────────────────────────────────
main() {
    local requested_target="${1:-}"

    ACTIVE=$(detect_active)
    if [ "$ACTIVE" = "blue" ]; then
        INACTIVE="green"
        NEW_API_PORT=$GREEN_API_PORT
        NEW_ADAPTER_PORT=$GREEN_ADAPTER_PORT
    else
        INACTIVE="blue"
        NEW_API_PORT=$BLUE_API_PORT
        NEW_ADAPTER_PORT=$BLUE_ADAPTER_PORT
    fi

    # Allow explicit target override
    if [ -n "$requested_target" ] && [ "$requested_target" != "$INACTIVE" ]; then
        warn "Requested target '$requested_target' is already active. Re-deploying in-place."
        INACTIVE="$requested_target"
    fi

    log "Current active slot: $ACTIVE"
    log "Deploying to inactive slot: $INACTIVE"

    # 1. Start inactive slot
    start_slot "$INACTIVE" || rollback "$INACTIVE" "$ACTIVE"

    # 2. Health-check new slot
    health_check "$NEW_API_PORT"      "api-gateway[$INACTIVE]"    || rollback "$INACTIVE" "$ACTIVE"
    health_check "$NEW_ADAPTER_PORT"  "signal-adapter[$INACTIVE]" || rollback "$INACTIVE" "$ACTIVE"

    # 3. Switch Nginx
    switch_nginx "$INACTIVE"

    # 4. Wait for in-flight requests to drain (grace period)
    log "Draining in-flight requests from $ACTIVE (10s)..."
    sleep 10

    # 5. Stop old active slot
    stop_slot "$ACTIVE"

    log ""
    log "Blue-green deployment complete."
    log "  Active slot : $INACTIVE"
    log "  api-gateway : http://localhost:$([ "$INACTIVE" = "blue" ] && echo $BLUE_API_PORT || echo $GREEN_API_PORT)/health"
    log "  signal-adapter: http://localhost:$([ "$INACTIVE" = "blue" ] && echo $BLUE_ADAPTER_PORT || echo $GREEN_ADAPTER_PORT)/health"
}

main "$@"
