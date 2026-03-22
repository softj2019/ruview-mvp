#!/bin/bash
# Start camera service: uvicorn in background, camera worker in foreground
cd "$(dirname "$0")"

export OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0

# Start uvicorn in background (reads frames from file)
python -m uvicorn main:app --host 0.0.0.0 --port 8002 &
UVICORN_PID=$!
echo "Uvicorn started (PID=$UVICORN_PID)"

# Run camera worker in foreground (needs stdin for MSMF)
echo "Starting camera worker..."
python camera_worker.py

# Cleanup
kill $UVICORN_PID 2>/dev/null
