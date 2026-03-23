"""
YOLOv8-pose skeleton detector — runs inference and returns detections with keypoints.
"""
import threading
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

# COCO skeleton pairs for drawing (0-indexed keypoint indices)
# 5=L_shoulder, 6=R_shoulder, 7=L_elbow, 8=R_elbow, 9=L_wrist, 10=R_wrist
# 11=L_hip, 12=R_hip, 13=L_knee, 14=R_knee, 15=L_ankle, 16=R_ankle
COCO_SKELETON_PAIRS = [
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12), (11, 13), (13, 15),
    (12, 14), (14, 16),
]

# Keypoint indices
KP_L_SHOULDER = 5
KP_R_SHOULDER = 6
KP_L_HIP = 11
KP_R_HIP = 12
KP_L_KNEE = 13
KP_R_KNEE = 14
KP_L_ANKLE = 15
KP_R_ANKLE = 16


@dataclass
class Detection:
    class_name: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int
    keypoints: list[list[float]] | None = None

    def to_dict(self):
        d = {
            "class": self.class_name,
            "confidence": round(self.confidence, 3),
            "bbox": [self.x1, self.y1, self.x2, self.y2],
        }
        if self.keypoints is not None:
            d["keypoints"] = self.keypoints
            pose, pose_conf = Detector.classify_pose(self.keypoints)
            d["pose"] = pose
            d["pose_confidence"] = pose_conf
        return d


class Detector:
    def __init__(self, model_name: str = "yolov8n-pose.pt", confidence: float = 0.4):
        self._model_name = model_name
        self._confidence = confidence
        self._model = None
        self._detections: list[Detection] = []
        self._lock = threading.Lock()
        self._person_count = 0
        self._fps = 0.0

    def load(self):
        from ultralytics import YOLO
        print(f"[detector] Loading {self._model_name}...")
        self._model = YOLO(self._model_name)
        print(f"[detector] Model loaded")

    @property
    def detections(self) -> list[Detection]:
        with self._lock:
            return list(self._detections)

    @property
    def person_count(self) -> int:
        with self._lock:
            return self._person_count

    @property
    def fps(self) -> float:
        return self._fps

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if self._model is None:
            return []

        results = self._model(frame, conf=self._confidence, verbose=False)
        dets = []
        persons = 0

        for r in results:
            # Extract keypoints if available (pose model)
            has_keypoints = (
                hasattr(r, "keypoints")
                and r.keypoints is not None
                and r.keypoints.xy is not None
            )

            for i, box in enumerate(r.boxes):
                cls_id = int(box.cls[0])
                cls_name = r.names[cls_id]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                kps = None
                if has_keypoints and cls_name == "person" and i < r.keypoints.xy.shape[0]:
                    # r.keypoints.xy: [N, 17, 2], r.keypoints.conf: [N, 17]
                    xy = r.keypoints.xy[i].cpu().numpy()   # (17, 2)
                    kp_conf = r.keypoints.conf[i].cpu().numpy()  # (17,)
                    kps = [
                        [float(xy[j][0]), float(xy[j][1]), float(kp_conf[j])]
                        for j in range(17)
                    ]

                dets.append(Detection(cls_name, conf, x1, y1, x2, y2, kps))
                if cls_name == "person":
                    persons += 1

        with self._lock:
            self._detections = dets
            self._person_count = persons

        return dets

    def draw_overlay(self, frame: np.ndarray, detections: list[Detection] | None = None) -> np.ndarray:
        """Draw bounding boxes, skeleton lines, and keypoints on frame."""
        dets = detections or self.detections
        out = frame.copy()

        for det in dets:
            color = (0, 255, 0) if det.class_name == "person" else (255, 165, 0)
            cv2.rectangle(out, (det.x1, det.y1), (det.x2, det.y2), color, 2)

            # Draw skeleton and keypoints for persons
            if det.keypoints is not None and det.class_name == "person":
                kps = det.keypoints
                kp_threshold = 0.3

                # Draw skeleton lines
                for (a, b) in COCO_SKELETON_PAIRS:
                    if a < len(kps) and b < len(kps):
                        if kps[a][2] > kp_threshold and kps[b][2] > kp_threshold:
                            pt1 = (int(kps[a][0]), int(kps[a][1]))
                            pt2 = (int(kps[b][0]), int(kps[b][1]))
                            cv2.line(out, pt1, pt2, (0, 255, 255), 2)

                # Draw keypoint circles
                for kp in kps:
                    if kp[2] > kp_threshold:
                        cv2.circle(out, (int(kp[0]), int(kp[1])), 4, (0, 0, 255), -1)

                # Draw pose label
                pose, pose_conf = self.classify_pose(kps)
                pose_label = f"{pose} ({pose_conf:.0%})"
                cv2.putText(out, pose_label, (det.x1, det.y2 + 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

            label = f"{det.class_name} {det.confidence:.0%}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(out, (det.x1, det.y1 - th - 6), (det.x1 + tw, det.y1), color, -1)
            cv2.putText(out, label, (det.x1, det.y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        # Person count overlay
        count_text = f"Persons: {sum(1 for d in dets if d.class_name == 'person')}"
        cv2.putText(out, count_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        return out

    @staticmethod
    def classify_pose(keypoints: list[list[float]]) -> tuple[str, float]:
        """Classify body pose from COCO keypoints.

        Returns (pose_string, confidence) where pose is one of:
        standing, sitting, lying, walking, unknown.
        """
        if keypoints is None or len(keypoints) < 17:
            return ("unknown", 0.0)

        conf_threshold = 0.3

        def _valid(idx: int) -> bool:
            return idx < len(keypoints) and keypoints[idx][2] > conf_threshold

        def _y(idx: int) -> float:
            return keypoints[idx][1]

        def _x(idx: int) -> float:
            return keypoints[idx][0]

        # Need at least shoulders and hips
        has_shoulders = _valid(KP_L_SHOULDER) and _valid(KP_R_SHOULDER)
        has_hips = _valid(KP_L_HIP) and _valid(KP_R_HIP)
        has_knees = _valid(KP_L_KNEE) and _valid(KP_R_KNEE)
        has_ankles = _valid(KP_L_ANKLE) and _valid(KP_R_ANKLE)

        if not has_shoulders or not has_hips:
            return ("unknown", 0.0)

        shoulder_y = (_y(KP_L_SHOULDER) + _y(KP_R_SHOULDER)) / 2.0
        hip_y = (_y(KP_L_HIP) + _y(KP_R_HIP)) / 2.0
        body_height = abs(hip_y - shoulder_y)

        if body_height < 5:
            # Shoulders and hips at same level — likely lying
            return ("lying", 0.7)

        if has_knees:
            knee_y = (_y(KP_L_KNEE) + _y(KP_R_KNEE)) / 2.0

            # Lying: shoulder_y ~ hip_y ~ knee_y (horizontal body)
            y_range = max(shoulder_y, hip_y, knee_y) - min(shoulder_y, hip_y, knee_y)
            if y_range < body_height * 0.5:
                return ("lying", 0.8)

            # Sitting: knees at approximately hip level (knee_y ~ hip_y)
            knee_hip_diff = abs(knee_y - hip_y)
            if knee_hip_diff < body_height * 0.4:
                return ("sitting", 0.75)

            # Walking: significant horizontal leg spread
            if has_ankles:
                ankle_spread = abs(_x(KP_L_ANKLE) - _x(KP_R_ANKLE))
                hip_spread = abs(_x(KP_L_HIP) - _x(KP_R_HIP))
                if hip_spread > 0 and ankle_spread > hip_spread * 1.5:
                    return ("walking", 0.65)

            # Standing: normal vertical alignment (hip below shoulder, knee below hip)
            if hip_y > shoulder_y and knee_y > hip_y:
                return ("standing", 0.8)

        else:
            # No knees visible — infer from shoulder/hip only
            if hip_y > shoulder_y:
                return ("standing", 0.5)

        return ("unknown", 0.3)
