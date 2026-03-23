#!/bin/bash
# RuView Watchdog — 서비스 상태를 감시하고 죽으면 자동 재시작
# Usage: nohup bash watchdog.sh &

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHECK_INTERVAL=30  # 초

echo "[watchdog] Started (interval: ${CHECK_INTERVAL}s)"

while true; do
    # signal-adapter
    if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo "[watchdog] $(date +%H:%M:%S) signal-adapter DOWN — restarting..."
        pid=$(netstat -ano 2>/dev/null | grep ":5005" | awk '{print $5}' | head -1)
        if [ -n "$pid" ]; then taskkill //PID $pid //F 2>/dev/null; fi
        sleep 2
        cd "$SCRIPT_DIR/services/signal-adapter"
        nohup python -m uvicorn main:app --host 0.0.0.0 --port 8001 > /dev/null 2>&1 &
        echo "[watchdog] signal-adapter restarted (PID $!)"
    fi

    # camera-service
    if ! curl -s http://localhost:8002/cam/health > /dev/null 2>&1; then
        echo "[watchdog] $(date +%H:%M:%S) camera-service DOWN — restarting..."
        pid=$(netstat -ano 2>/dev/null | grep ":8002" | grep LISTEN | awk '{print $5}' | head -1)
        if [ -n "$pid" ]; then taskkill //PID $pid //F 2>/dev/null; fi
        sleep 2
        cd "$SCRIPT_DIR/services/camera-service"
        OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0 nohup python -m uvicorn main:app --host 0.0.0.0 --port 8002 > /dev/null 2>&1 &
        echo "[watchdog] camera-service restarted (PID $!)"
    fi

    # web-monitor
    if ! curl -s -o /dev/null http://localhost:5280/ 2>/dev/null; then
        echo "[watchdog] $(date +%H:%M:%S) web-monitor DOWN — restarting..."
        cd "$SCRIPT_DIR/apps/web-monitor"
        nohup npx vite --host 0.0.0.0 > /dev/null 2>&1 &
        echo "[watchdog] web-monitor restarted (PID $!)"
    fi

    sleep $CHECK_INTERVAL
done
