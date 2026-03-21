"""
Camera capture thread — reads frames from a USB camera into a shared buffer.
"""
import threading
import time
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class CameraConfig:
    device_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 15
    backend: int = cv2.CAP_DSHOW  # Windows DirectShow


class CameraCapture:
    def __init__(self, config: CameraConfig | None = None):
        self.config = config or CameraConfig()
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._cap: cv2.VideoCapture | None = None
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
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self._cap:
            self._cap.release()
            self._cap = None

    def _capture_loop(self):
        cfg = self.config
        self._cap = cv2.VideoCapture(cfg.device_index, cfg.backend)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
        self._cap.set(cv2.CAP_PROP_FPS, cfg.fps)

        if not self._cap.isOpened():
            print(f"[camera] Failed to open device {cfg.device_index}")
            self._running = False
            return

        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[camera] Opened device {cfg.device_index}: {w}x{h}")

        frame_count = 0
        t0 = time.monotonic()

        while self._running:
            ret, frame = self._cap.read()
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

        self._cap.release()
        self._cap = None
