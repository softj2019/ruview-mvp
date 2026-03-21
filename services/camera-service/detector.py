"""
YOLOv8n object detector — runs inference and returns detections.
"""
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Detection:
    class_name: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    def to_dict(self):
        return {
            "class": self.class_name,
            "confidence": round(self.confidence, 3),
            "bbox": [self.x1, self.y1, self.x2, self.y2],
        }


class Detector:
    def __init__(self, model_name: str = "yolov8n.pt", confidence: float = 0.4):
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
            for box in r.boxes:
                cls_id = int(box.cls[0])
                cls_name = r.names[cls_id]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                dets.append(Detection(cls_name, conf, x1, y1, x2, y2))
                if cls_name == "person":
                    persons += 1

        with self._lock:
            self._detections = dets
            self._person_count = persons

        return dets

    def draw_overlay(self, frame: np.ndarray, detections: list[Detection] | None = None) -> np.ndarray:
        """Draw bounding boxes on frame."""
        dets = detections or self.detections
        out = frame.copy()

        for det in dets:
            color = (0, 255, 0) if det.class_name == "person" else (255, 165, 0)
            cv2.rectangle(out, (det.x1, det.y1), (det.x2, det.y2), color, 2)
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
