"""
Camera Service — MJPEG stream + YOLO detection + floor calibration.

Endpoints:
  GET  /cam/health         Health check
  GET  /cam/stream         MJPEG video stream (with overlay)
  GET  /cam/snapshot       Single JPEG frame
  WS   /cam/detections     Real-time detection results (JSON)
  GET  /cam/calibration    Get current calibration
  PUT  /cam/calibration    Update calibration points
  POST /cam/calibration/snapshot  Get snapshot for calibration UI
"""
import os
# Must be set before any OpenCV import
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import asyncio
import json
import threading
import time

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response

from camera import CameraCapture
from detector import Detector
from calibration import Calibrator

# ---- Config ----

CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))
CAMERA_FPS = int(os.getenv("CAMERA_FPS", "15"))
DETECT_SKIP = int(os.getenv("DETECT_SKIP", "2"))  # run detection every N frames
SIGNAL_ADAPTER_URL = os.getenv("SIGNAL_ADAPTER_URL", "http://localhost:8001")

# ---- Globals ----

camera = CameraCapture(device_index=CAMERA_INDEX, fps=CAMERA_FPS)
detector = Detector()
calibrator = Calibrator()

# Detection loop state
_detect_frame_count = 0
_detect_thread: threading.Thread | None = None
_detect_running = False

# Connected detection WS clients
_ws_clients: list[WebSocket] = []


def _detection_loop():
    """Background thread: periodically runs YOLO on latest frame."""
    global _detect_frame_count
    _det_count = 0
    _det_t0 = time.monotonic()
    while _detect_running:
        frame = camera.frame
        if frame is None:
            time.sleep(0.05)
            continue

        _detect_frame_count += 1
        if _detect_frame_count % DETECT_SKIP != 0:
            time.sleep(0.01)
            continue

        dets = detector.detect(frame)
        _det_count += 1
        elapsed = time.monotonic() - _det_t0
        if elapsed >= 1.0:
            detector._fps = _det_count / elapsed
            _det_count = 0
            _det_t0 = time.monotonic()

        # Build detection payload with floor positions
        det_list = []
        for d in dets:
            entry = d.to_dict()
            floor_pos = calibrator.bbox_to_floor(d.x1, d.y1, d.x2, d.y2)
            entry["floor_pos"] = floor_pos.to_dict()
            det_list.append(entry)

        person_count = sum(1 for d in dets if d.class_name == "person")

        payload = {
            "detections": det_list,
            "person_count": person_count,
            "timestamp": time.time(),
        }

        # Send to signal-adapter for fusion
        _send_to_adapter(payload)

        # Broadcast to WS clients
        _broadcast_detections(payload)

        time.sleep(0.01)


def _send_to_adapter(payload: dict):
    """Send detection results to signal-adapter for CSI fusion."""
    import urllib.request
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{SIGNAL_ADAPTER_URL}/api/camera/detections",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=1)
    except Exception:
        pass  # Non-critical: adapter may not have this endpoint yet


def _broadcast_detections(payload: dict):
    """Broadcast detections to connected WebSocket clients."""
    if not _ws_clients:
        return
    msg = json.dumps(payload)
    dead = []
    for ws in _ws_clients:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(msg), _loop)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


_loop: asyncio.AbstractEventLoop | None = None

# ---- FastAPI App ----

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _detect_running, _detect_thread, _loop
    _loop = asyncio.get_running_loop()

    # Camera was opened at import time (before asyncio loop)
    camera.start()
    print(f"[camera-service] Camera capture thread started")

    # Load YOLO model (after camera is stable)
    detector.load()

    # Start detection thread
    _detect_running = True
    _detect_thread = threading.Thread(target=_detection_loop, daemon=True)
    _detect_thread.start()
    print(f"[camera-service] Detection loop started (skip={DETECT_SKIP})")

    yield

    # Cleanup
    _detect_running = False
    if _detect_thread:
        _detect_thread.join(timeout=3)
    camera.stop()
    print("[camera-service] Stopped")


app = FastAPI(title="RuView Camera Service", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Endpoints ----

@app.get("/cam/health")
async def health():
    return {
        "status": "ok",
        "service": "camera-service",
        "camera_running": camera.is_running,
        "camera_fps": round(camera.fps, 1),
        "detector_fps": round(detector.fps, 1),
        "person_count": detector.person_count,
        "ws_clients": len(_ws_clients),
    }


def _generate_mjpeg():
    """Generator yielding MJPEG frames with detection overlay."""
    while True:
        frame = camera.frame
        if frame is None:
            time.sleep(0.05)
            continue

        # Draw overlay
        overlay_frame = detector.draw_overlay(frame)

        # Encode to JPEG
        _, jpeg = cv2.imencode(".jpg", overlay_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + jpeg.tobytes()
            + b"\r\n"
        )
        time.sleep(1.0 / CAMERA_FPS)


@app.get("/cam/stream")
async def stream():
    return StreamingResponse(
        _generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/cam/snapshot")
async def snapshot():
    frame = camera.frame
    if frame is None:
        return Response(status_code=503, content="Camera not ready")
    overlay_frame = detector.draw_overlay(frame)
    _, jpeg = cv2.imencode(".jpg", overlay_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(content=jpeg.tobytes(), media_type="image/jpeg")


@app.get("/cam/snapshot/raw")
async def snapshot_raw():
    """Raw snapshot without overlay (for calibration UI)."""
    frame = camera.frame
    if frame is None:
        return Response(status_code=503, content="Camera not ready")
    _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return Response(content=jpeg.tobytes(), media_type="image/jpeg")


@app.websocket("/cam/detections")
async def ws_detections(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


# ---- Calibration Endpoints ----

@app.get("/cam/calibration")
async def get_calibration():
    return calibrator.config


@app.put("/cam/calibration")
async def update_calibration(body: dict):
    camera_points = body.get("camera_points")
    floor_points = body.get("floor_points")
    if not camera_points or not floor_points:
        return {"error": "camera_points and floor_points required"}
    if len(camera_points) != 4 or len(floor_points) != 4:
        return {"error": "exactly 4 point pairs required"}
    calibrator.update(camera_points, floor_points)
    return {"status": "updated", "config": calibrator.config}


@app.post("/cam/calibration/test")
async def test_calibration(body: dict):
    """Test mapping a camera point to floor coordinates."""
    cx = body.get("cx", 320)
    cy = body.get("cy", 240)
    floor_pos = calibrator.camera_to_floor(cx, cy)
    return {"camera": {"x": cx, "y": cy}, "floor": floor_pos.to_dict()}
