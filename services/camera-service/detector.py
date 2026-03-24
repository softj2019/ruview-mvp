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
    track_id: int | None = None

    def to_dict(self):
        d = {
            "class": self.class_name,
            "confidence": round(self.confidence, 3),
            "bbox": [self.x1, self.y1, self.x2, self.y2],
        }
        if self.track_id is not None:
            d["track_id"] = self.track_id
        if self.keypoints is not None:
            d["keypoints"] = self.keypoints
            pose, pose_conf = Detector.classify_pose(self.keypoints)
            d["pose"] = pose
            d["pose_confidence"] = pose_conf
        return d


def _compute_iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    """Compute Intersection over Union between two (x1, y1, x2, y2) boxes."""
    xa = max(box_a[0], box_b[0])
    ya = max(box_a[1], box_b[1])
    xb = min(box_a[2], box_b[2])
    yb = min(box_a[3], box_b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    if inter == 0:
        return 0.0
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _compute_appearance(frame: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray | None:
    """Compute HSV color histogram feature vector for a person crop.

    Args:
        frame: Full BGR frame.
        bbox: (x1, y1, x2, y2) bounding box.

    Returns:
        Normalized histogram as 1-D float32 array, or None if crop is invalid.
    """
    x1, y1, x2, y2 = bbox
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return None
    crop = frame[y1:y2, x1:x2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist.flatten().astype(np.float32)


class SimpleTracker:
    """Lightweight ByteTrack-style multi-object tracker using IoU matching
    and optional color-histogram re-identification."""

    def __init__(self, iou_threshold: float = 0.3, max_age: int = 10,
                 reid_threshold: float = 0.6):
        self._next_id = 1
        self._iou_threshold = iou_threshold
        self._max_age = max_age
        self._reid_threshold = reid_threshold
        # Active tracks: list of dicts with keys:
        #   id, bbox (x1,y1,x2,y2), age, hits, last_seen (frames since update),
        #   appearance (np.ndarray | None)
        self._tracks: list[dict] = []
        # Recently lost tracks kept for re-id (up to 30 frames)
        self._lost_tracks: list[dict] = []

    def update(self, detections: list[Detection],
               frame: np.ndarray | None = None) -> list[Detection]:
        """Match detections to existing tracks and assign track_ids.

        Args:
            detections: Current frame detections (person-only will be tracked).
            frame: BGR frame for appearance feature extraction (optional).

        Returns:
            The same detection list with track_id fields populated.
        """
        person_dets = [d for d in detections if d.class_name == "person"]
        non_person_dets = [d for d in detections if d.class_name != "person"]

        # Compute appearance features for current detections
        det_features: list[np.ndarray | None] = []
        for d in person_dets:
            if frame is not None:
                feat = _compute_appearance(frame, (d.x1, d.y1, d.x2, d.y2))
            else:
                feat = None
            det_features.append(feat)

        # Build IoU cost matrix: tracks x detections
        matched_det = set()
        matched_trk = set()

        if self._tracks and person_dets:
            iou_matrix = np.zeros((len(self._tracks), len(person_dets)), dtype=np.float32)
            for t_idx, trk in enumerate(self._tracks):
                for d_idx, det in enumerate(person_dets):
                    iou_matrix[t_idx, d_idx] = _compute_iou(
                        trk["bbox"], (det.x1, det.y1, det.x2, det.y2)
                    )

            # Greedy matching by highest IoU
            while True:
                if iou_matrix.size == 0:
                    break
                best = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                t_idx, d_idx = int(best[0]), int(best[1])
                if iou_matrix[t_idx, d_idx] < self._iou_threshold:
                    break
                # Match found
                matched_trk.add(t_idx)
                matched_det.add(d_idx)
                det = person_dets[d_idx]
                trk = self._tracks[t_idx]
                det.track_id = trk["id"]
                trk["bbox"] = (det.x1, det.y1, det.x2, det.y2)
                trk["hits"] += 1
                trk["last_seen"] = 0
                if det_features[d_idx] is not None:
                    trk["appearance"] = det_features[d_idx]
                # Zero out row and column to prevent re-matching
                iou_matrix[t_idx, :] = 0
                iou_matrix[:, d_idx] = 0

        # Unmatched detections: try re-id against lost tracks, else new track
        for d_idx, det in enumerate(person_dets):
            if d_idx in matched_det:
                continue

            feat = det_features[d_idx]
            reid_match = None

            # Attempt re-identification via color histogram
            if feat is not None and self._lost_tracks:
                best_corr = -1.0
                best_lost_idx = -1
                for l_idx, lost in enumerate(self._lost_tracks):
                    lost_feat = lost.get("appearance")
                    if lost_feat is None:
                        continue
                    corr = cv2.compareHist(
                        feat.reshape(-1, 1), lost_feat.reshape(-1, 1),
                        cv2.HISTCMP_CORREL,
                    )
                    if corr > best_corr:
                        best_corr = corr
                        best_lost_idx = l_idx
                if best_corr > self._reid_threshold and best_lost_idx >= 0:
                    reid_match = self._lost_tracks.pop(best_lost_idx)

            if reid_match is not None:
                # Re-identified: reuse old track id
                det.track_id = reid_match["id"]
                new_track = {
                    "id": reid_match["id"],
                    "bbox": (det.x1, det.y1, det.x2, det.y2),
                    "age": reid_match["age"],
                    "hits": reid_match["hits"] + 1,
                    "last_seen": 0,
                    "appearance": feat,
                }
                self._tracks.append(new_track)
            else:
                # Brand-new track
                det.track_id = self._next_id
                new_track = {
                    "id": self._next_id,
                    "bbox": (det.x1, det.y1, det.x2, det.y2),
                    "age": 0,
                    "hits": 1,
                    "last_seen": 0,
                    "appearance": feat,
                }
                self._tracks.append(new_track)
                self._next_id += 1

        # Unmatched tracks: increment last_seen
        surviving = []
        for t_idx, trk in enumerate(self._tracks):
            if t_idx in matched_trk or trk["last_seen"] == 0:
                trk["age"] += 1
                surviving.append(trk)
            else:
                trk["last_seen"] += 1
                if trk["last_seen"] >= self._max_age:
                    # Move to lost tracks for potential re-id
                    self._lost_tracks.append(trk)
                else:
                    trk["age"] += 1
                    surviving.append(trk)

        self._tracks = surviving

        # Prune old lost tracks (keep for up to 30 extra frames)
        self._lost_tracks = [
            lt for lt in self._lost_tracks if lt["last_seen"] < self._max_age + 30
        ]
        for lt in self._lost_tracks:
            lt["last_seen"] += 1

        # Return all detections (persons now have track_id set)
        return person_dets + non_person_dets


class Detector:
    def __init__(self, model_name: str = "yolov8n-pose.pt", confidence: float = 0.4):
        self._model_name = model_name
        self._confidence = confidence
        self._model = None
        self._detections: list[Detection] = []
        self._lock = threading.Lock()
        self._person_count = 0
        self._fps = 0.0
        self._tracker = SimpleTracker()

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

        # Multi-object tracking: assign persistent track IDs
        dets = self._tracker.update(dets, frame)

        with self._lock:
            self._detections = dets
            self._person_count = persons

        return dets

    def blur_faces(self, frame: np.ndarray, detections: list[Detection] | None = None) -> np.ndarray:
        """Blur face regions based on nose/eye keypoints for privacy protection."""
        dets = detections or self.detections
        out = frame.copy()
        h, w = out.shape[:2]

        for det in dets:
            if det.keypoints is None or det.class_name != "person":
                continue

            kps = det.keypoints
            kp_threshold = 0.3

            # Keypoint indices: 0=nose, 1=left_eye, 2=right_eye
            face_kp_indices = [0, 1, 2]
            valid_pts = []
            for idx in face_kp_indices:
                if idx < len(kps) and kps[idx][2] > kp_threshold:
                    valid_pts.append((kps[idx][0], kps[idx][1]))

            if len(valid_pts) < 2:
                continue

            xs = [p[0] for p in valid_pts]
            ys = [p[1] for p in valid_pts]
            cx = (min(xs) + max(xs)) / 2.0
            cy = (min(ys) + max(ys)) / 2.0
            half_w = (max(xs) - min(xs)) / 2.0
            half_h = (max(ys) - min(ys)) / 2.0

            # Expand by 50%
            half_w = max(half_w, 10) * 1.5
            half_h = max(half_h, 10) * 1.5

            x1 = max(0, int(cx - half_w))
            y1 = max(0, int(cy - half_h))
            x2 = min(w, int(cx + half_w))
            y2 = min(h, int(cy + half_h))

            if x2 > x1 and y2 > y1:
                face_region = out[y1:y2, x1:x2]
                # Kernel size must be odd
                kw = max(15, (x2 - x1) // 2 | 1)
                kh = max(15, (y2 - y1) // 2 | 1)
                blurred = cv2.GaussianBlur(face_region, (kw, kh), 30)
                out[y1:y2, x1:x2] = blurred

        return out

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
