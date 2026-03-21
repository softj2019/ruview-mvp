"""
Camera-to-floor coordinate calibration.

Maps camera pixel coordinates to the floor plan coordinate system (800x500).
Uses a 4-point perspective transform (homography).

The camera looks from the Node 3,4 area toward Node 1,2 area
(bottom-to-top in floor plan, vertically centered).

Calibration points are stored in calibration.json.
"""
import json
import os
from dataclasses import dataclass

import cv2
import numpy as np

CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "calibration.json")

# Default calibration: camera corners → floor plan corners
# Camera view: bottom of frame = near (N3,N4 side), top = far (N1,N2 side)
DEFAULT_CALIBRATION = {
    "camera_points": [
        [0, 0],       # top-left of camera = floor top-left
        [640, 0],     # top-right of camera = floor top-right
        [640, 480],   # bottom-right = floor bottom-right
        [0, 480],     # bottom-left = floor bottom-left
    ],
    "floor_points": [
        [80, 80],     # floor top-left (zone boundary)
        [720, 80],    # floor top-right
        [720, 420],   # floor bottom-right
        [80, 420],    # floor bottom-left
    ],
    "camera_resolution": [640, 480],
    "floor_size": [800, 500],
}


@dataclass
class FloorPosition:
    x: float
    y: float

    def to_dict(self):
        return {"x": round(self.x, 1), "y": round(self.y, 1)}


class Calibrator:
    def __init__(self):
        self._homography: np.ndarray | None = None
        self._config = dict(DEFAULT_CALIBRATION)
        self._load()

    def _load(self):
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE, "r") as f:
                    self._config = json.load(f)
            except Exception:
                pass
        self._compute_homography()

    def _compute_homography(self):
        cam_pts = np.float32(self._config["camera_points"])
        floor_pts = np.float32(self._config["floor_points"])
        self._homography, _ = cv2.findHomography(cam_pts, floor_pts)

    def save(self):
        with open(CALIBRATION_FILE, "w") as f:
            json.dump(self._config, f, indent=2)

    @property
    def config(self) -> dict:
        return dict(self._config)

    def update(self, camera_points: list, floor_points: list):
        """Update calibration with new point pairs."""
        self._config["camera_points"] = camera_points
        self._config["floor_points"] = floor_points
        self._compute_homography()
        self.save()

    def camera_to_floor(self, cx: int, cy: int) -> FloorPosition:
        """Convert camera pixel coordinate to floor plan coordinate."""
        if self._homography is None:
            return FloorPosition(0, 0)
        pt = np.float32([[cx, cy]]).reshape(-1, 1, 2)
        mapped = cv2.perspectiveTransform(pt, self._homography)
        fx, fy = mapped[0][0]
        return FloorPosition(float(fx), float(fy))

    def bbox_to_floor(self, x1: int, y1: int, x2: int, y2: int) -> FloorPosition:
        """Convert bounding box center-bottom to floor position."""
        cx = (x1 + x2) // 2
        cy = y2  # feet position
        return self.camera_to_floor(cx, cy)
