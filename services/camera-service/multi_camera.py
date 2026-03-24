"""
Multi-Camera Framework — manages multiple camera instances (Phase 4-7).

CameraManager class that manages N camera instances.
Currently works with 1 camera, ready for N cameras when hardware is available.

Features:
- Add/remove cameras by device_index
- Get all frames from all cameras simultaneously
- Get merged detections from all cameras
- Duplicate person removal: if two cameras detect a person at similar
  floor position (within 50px), keep the higher-confidence one
"""
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


@dataclass
class CameraInstance:
    """Represents a single camera instance."""
    device_index: int
    name: str
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)  # x, y, z in room coords
    camera_id: str = ""
    cap: cv2.VideoCapture | None = None
    frame: np.ndarray | None = None
    fps: float = 0.0
    is_running: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _thread: threading.Thread | None = None

    def __post_init__(self):
        if not self.camera_id:
            self.camera_id = f"cam-{self.device_index}"

    def start(self, target_fps: int = 15) -> bool:
        """Open camera and start capture thread."""
        if self.is_running:
            return True

        try:
            self.cap = cv2.VideoCapture(self.device_index)
            if not self.cap.isOpened():
                print(f"[multi-camera] Failed to open camera {self.device_index}")
                return False

            ret, _ = self.cap.read()
            if not ret:
                print(f"[multi-camera] Camera {self.device_index} opened but no frame")
                self.cap.release()
                return False

            self.is_running = True
            self._thread = threading.Thread(
                target=self._capture_loop,
                args=(target_fps,),
                daemon=True,
            )
            self._thread.start()
            print(f"[multi-camera] Camera '{self.name}' (index={self.device_index}) started")
            return True
        except Exception as e:
            print(f"[multi-camera] Error starting camera {self.device_index}: {e}")
            return False

    def stop(self):
        """Stop capture thread and release camera."""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self.cap:
            self.cap.release()
            self.cap = None
        self.frame = None
        print(f"[multi-camera] Camera '{self.name}' stopped")

    def get_frame(self) -> np.ndarray | None:
        """Get latest frame (thread-safe copy)."""
        with self._lock:
            return self.frame.copy() if self.frame is not None else None

    def _capture_loop(self, target_fps: int):
        """Background capture loop."""
        frame_count = 0
        t0 = time.monotonic()
        interval = 1.0 / target_fps

        while self.is_running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            with self._lock:
                self.frame = frame

            frame_count += 1
            elapsed = time.monotonic() - t0
            if elapsed >= 1.0:
                self.fps = frame_count / elapsed
                frame_count = 0
                t0 = time.monotonic()

            time.sleep(interval)

    def to_dict(self) -> dict[str, Any]:
        """Serialize camera info to dict."""
        return {
            "camera_id": self.camera_id,
            "device_index": self.device_index,
            "name": self.name,
            "position": list(self.position),
            "is_running": self.is_running,
            "fps": round(self.fps, 1),
            "has_frame": self.frame is not None,
        }


# Duplicate detection removal threshold (pixels in floor coordinates)
DEDUP_DISTANCE_THRESHOLD = 50  # px


class CameraManager:
    """Manages multiple camera instances with detection merging.

    Provides a unified interface for N cameras. Handles:
    - Camera lifecycle (add, remove, start, stop)
    - Frame retrieval from all cameras
    - Detection merging with duplicate person removal
    """

    def __init__(self):
        self._cameras: dict[str, CameraInstance] = {}
        self._lock = threading.Lock()

    @property
    def camera_count(self) -> int:
        return len(self._cameras)

    def add_camera(
        self,
        device_index: int,
        name: str,
        position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> CameraInstance:
        """Add a camera instance.

        Args:
            device_index: OpenCV device index (0, 1, 2, ...).
            name: Human-readable camera name.
            position: Camera position in room coordinates (x, y, z).

        Returns:
            The created CameraInstance.
        """
        camera_id = f"cam-{device_index}"
        with self._lock:
            if camera_id in self._cameras:
                print(f"[multi-camera] Camera {camera_id} already exists, replacing")
                self._cameras[camera_id].stop()

            instance = CameraInstance(
                device_index=device_index,
                name=name,
                position=position,
                camera_id=camera_id,
            )
            self._cameras[camera_id] = instance
            print(f"[multi-camera] Added camera '{name}' (index={device_index})")
            return instance

    def remove_camera(self, device_index: int) -> bool:
        """Remove a camera by device index.

        Args:
            device_index: The OpenCV device index to remove.

        Returns:
            True if camera was found and removed.
        """
        camera_id = f"cam-{device_index}"
        with self._lock:
            if camera_id not in self._cameras:
                return False
            self._cameras[camera_id].stop()
            del self._cameras[camera_id]
            print(f"[multi-camera] Removed camera {camera_id}")
            return True

    def get_camera(self, device_index: int) -> CameraInstance | None:
        """Get a camera instance by device index."""
        camera_id = f"cam-{device_index}"
        return self._cameras.get(camera_id)

    def get_all_frames(self) -> dict[str, np.ndarray | None]:
        """Get latest frames from all cameras.

        Returns:
            Dict of {camera_id: frame} for all registered cameras.
            Frame is None if camera has no frame yet.
        """
        frames = {}
        with self._lock:
            for camera_id, cam in self._cameras.items():
                frames[camera_id] = cam.get_frame()
        return frames

    def get_all_detections(
        self,
        per_camera_detections: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Merge detections from all cameras with duplicate removal.

        Takes per-camera detection lists and merges them, removing
        duplicate person detections when two cameras see the same person
        at a similar floor position (within DEDUP_DISTANCE_THRESHOLD pixels).

        For duplicate pairs, keeps the detection with higher confidence.

        Args:
            per_camera_detections: Dict of {camera_id: [detection_dicts]}.
                Each detection should have:
                    - "floor_pos": {"x": float, "y": float}
                    - "confidence": float
                    - "class_name": str

        Returns:
            Merged list of unique detections.
        """
        # Flatten all detections with camera source tag
        all_dets: list[dict[str, Any]] = []
        for camera_id, dets in per_camera_detections.items():
            for det in dets:
                det_copy = dict(det)
                det_copy["source_camera"] = camera_id
                all_dets.append(det_copy)

        if len(all_dets) <= 1:
            return all_dets

        # Only deduplicate "person" class detections
        persons = [d for d in all_dets if d.get("class_name") == "person"]
        non_persons = [d for d in all_dets if d.get("class_name") != "person"]

        # Mark duplicates (greedy matching by floor position proximity)
        merged_persons = self._deduplicate_persons(persons)

        return merged_persons + non_persons

    def _deduplicate_persons(
        self, persons: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove duplicate person detections across cameras.

        If two detections from different cameras have floor positions
        within DEDUP_DISTANCE_THRESHOLD pixels, they likely represent
        the same person. Keep the one with higher confidence.

        Args:
            persons: List of person detection dicts.

        Returns:
            Deduplicated list.
        """
        if len(persons) <= 1:
            return persons

        # Sort by confidence descending — higher confidence kept first
        sorted_dets = sorted(
            persons,
            key=lambda d: d.get("confidence", 0.0),
            reverse=True,
        )

        kept: list[dict[str, Any]] = []
        suppressed: set[int] = set()

        for i, det_a in enumerate(sorted_dets):
            if i in suppressed:
                continue

            fp_a = det_a.get("floor_pos", {})
            ax = fp_a.get("x", 0.0)
            ay = fp_a.get("y", 0.0)
            cam_a = det_a.get("source_camera", "")

            # Check against remaining detections
            for j in range(i + 1, len(sorted_dets)):
                if j in suppressed:
                    continue

                det_b = sorted_dets[j]
                cam_b = det_b.get("source_camera", "")

                # Only deduplicate across different cameras
                if cam_a == cam_b:
                    continue

                fp_b = det_b.get("floor_pos", {})
                bx = fp_b.get("x", 0.0)
                by = fp_b.get("y", 0.0)

                distance = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                if distance < DEDUP_DISTANCE_THRESHOLD:
                    # Duplicate: suppress the lower-confidence one (det_b)
                    suppressed.add(j)

            kept.append(det_a)

        return kept

    def start_all(self, fps: int = 15) -> dict[str, bool]:
        """Start all registered cameras.

        Returns:
            Dict of {camera_id: success} for each camera.
        """
        results = {}
        with self._lock:
            for camera_id, cam in self._cameras.items():
                results[camera_id] = cam.start(target_fps=fps)
        return results

    def stop_all(self):
        """Stop all cameras."""
        with self._lock:
            for cam in self._cameras.values():
                cam.stop()

    def list_cameras(self) -> list[dict[str, Any]]:
        """List all registered cameras as dicts."""
        with self._lock:
            return [cam.to_dict() for cam in self._cameras.values()]
