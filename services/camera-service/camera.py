"""
Camera frame reader — reads JPEG frames from camera_worker's output file.
camera_worker.py runs as a separate process to avoid MSMF/asyncio conflicts.
"""
import os
import threading
import time

import cv2
import numpy as np

FRAME_PATH = os.path.join(os.path.dirname(__file__), ".frame.jpg")


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
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _read_loop(self):
        last_mtime = 0.0
        frame_count = 0
        t0 = time.monotonic()

        while self._running:
            try:
                if not os.path.exists(FRAME_PATH):
                    time.sleep(0.05)
                    continue

                mtime = os.path.getmtime(FRAME_PATH)
                if mtime <= last_mtime:
                    time.sleep(0.01)
                    continue
                last_mtime = mtime

                with open(FRAME_PATH, "rb") as f:
                    data = f.read()

                if len(data) < 100:
                    continue

                frame = cv2.imdecode(
                    np.frombuffer(data, dtype=np.uint8),
                    cv2.IMREAD_COLOR,
                )
                if frame is not None:
                    with self._lock:
                        self._frame = frame
                    frame_count += 1

                elapsed = time.monotonic() - t0
                if elapsed >= 1.0:
                    self._fps_actual = frame_count / elapsed
                    frame_count = 0
                    t0 = time.monotonic()

            except (IOError, OSError):
                time.sleep(0.05)

            time.sleep(0.01)
