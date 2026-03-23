"""
Camera capture — direct OpenCV in same process.
Opens camera at import time (before asyncio event loop starts).
MSMF on Windows requires console-attached foreground process.
"""
import os
import threading
import time

# Must be set BEFORE importing cv2
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import cv2
import numpy as np

# Open camera at module load time — before uvicorn's asyncio loop
_global_cap = None
_global_ok = False


def _init_camera(idx=0):
    global _global_cap, _global_ok
    _global_cap = cv2.VideoCapture(idx)
    if _global_cap.isOpened():
        ret, _ = _global_cap.read()
        _global_ok = ret
        print(f"[camera] Device {idx}: {'ready' if ret else 'opened but no frame'}")
    else:
        print(f"[camera] Device {idx}: failed to open")


_init_camera(int(os.getenv("CAMERA_INDEX", "0")))


class CameraCapture:
    def __init__(self, device_index: int = 0, fps: int = 15):
        self._fps = fps
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._fps_actual = 0.0

    @property
    def frame(self) -> np.ndarray | None:
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    @property
    def fps(self) -> float:
        return self._fps_actual

    @property
    def is_running(self) -> bool:
        return self._running and self._frame is not None

    def start(self):
        if self._running:
            return
        if not _global_ok:
            print("[camera] Cannot start — camera not available")
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        if _global_cap:
            _global_cap.release()

    def _capture_loop(self):
        cap = _global_cap
        if cap is None or not cap.isOpened():
            self._running = False
            return

        frame_count = 0
        t0 = time.monotonic()

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            with self._lock:
                self._frame = frame

            frame_count += 1
            elapsed = time.monotonic() - t0
            if elapsed >= 1.0:
                self._fps_actual = frame_count / elapsed
                frame_count = 0
                t0 = time.monotonic()
