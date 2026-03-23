#!/bin/bash
# RuView 전체 서비스 시작 스크립트
# Usage: bash start_all.sh [--stop]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

stop_services() {
    echo "[ruview] Stopping services..."
    for port in 8001 8002; do
        pid=$(netstat -ano 2>/dev/null | grep ":$port" | grep LISTEN | awk '{print $5}' | head -1)
        if [ -n "$pid" ]; then
            taskkill //PID $pid //F 2>/dev/null
            echo "  Stopped port $port (PID $pid)"
        fi
    done
    # vite
    pid=$(netstat -ano 2>/dev/null | grep ":5280" | grep LISTEN | awk '{print $5}' | head -1)
    if [ -n "$pid" ]; then
        taskkill //PID $pid //F 2>/dev/null
        echo "  Stopped vite (PID $pid)"
    fi
    echo "[ruview] All services stopped"
}

start_services() {
    echo "[ruview] Starting services..."

    # 1. signal-adapter
    cd "$SCRIPT_DIR/services/signal-adapter"
    nohup python -m uvicorn main:app --host 0.0.0.0 --port 8001 > /dev/null 2>&1 &
    echo "  signal-adapter :8001 started (PID $!)"

    # 2. camera-service
    cd "$SCRIPT_DIR/services/camera-service"
    OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0 nohup python -m uvicorn main:app --host 0.0.0.0 --port 8002 > /dev/null 2>&1 &
    echo "  camera-service :8002 started (PID $!)"

    # 3. web-monitor
    cd "$SCRIPT_DIR/apps/web-monitor"
    nohup npx vite --host 0.0.0.0 > /dev/null 2>&1 &
    echo "  web-monitor :5280 started (PID $!)"

    sleep 5

    # Health check
    echo ""
    echo "[ruview] Health check:"
    for svc in "signal-adapter:8001" "camera-service:8002"; do
        name=$(echo $svc | cut -d: -f1)
        port=$(echo $svc | cut -d: -f2)
        status=$(curl -s "http://localhost:$port/health" 2>/dev/null | grep -o '"status":"ok"' | head -1)
        if [ -n "$status" ]; then
            echo "  $name :$port — OK"
        else
            echo "  $name :$port — FAIL"
        fi
    done
    status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5280/" 2>/dev/null)
    if [ "$status" = "200" ]; then
        echo "  web-monitor :5280 — OK"
    else
        echo "  web-monitor :5280 — FAIL"
    fi
    echo ""
    echo "[ruview] Dashboard: http://localhost:5280"
}

if [ "$1" = "--stop" ]; then
    stop_services
else
    stop_services
    sleep 2
    start_services
fi
