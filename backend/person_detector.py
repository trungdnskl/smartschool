"""
Classroom Engagement System - Person Detector
YOLOv8-based person detection for accurate student headcount.
Detects full bodies even when faces are not visible (back turned, head down).
"""

import cv2
import numpy as np
import logging
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"


class PersonDetector:
    """
    YOLOv8 person detector for classroom headcount.
    Detects class 0 (person) from COCO — works for all angles including
    overhead cameras where faces may not be visible.
    """

    def __init__(
        self,
        confidence: float = 0.35,
        model_size: str = "n",  # n=nano (fastest), s=small, m=medium
        max_persons: int = 50,
    ):
        self.confidence = confidence
        self.model_size = model_size
        self.max_persons = max_persons
        self._model = None
        self._initialized = False

        # Tracking
        self._next_id = 1
        self._tracks: Dict[int, Dict] = {}
        self._iou_thresh = 0.3

    def initialize(self):
        """Load YOLOv8 model."""
        if self._initialized:
            return

        try:
            from ultralytics import YOLO

            model_name = f"yolov8{self.model_size}.pt"
            model_path = MODEL_DIR / model_name

            # YOLOv8 auto-downloads if not present
            self._model = YOLO(str(model_path) if model_path.exists() else model_name)
            self._initialized = True
            logger.info(f"[PersonDetector] ✓ YOLOv8{self.model_size} loaded")

        except Exception as e:
            logger.error(f"[PersonDetector] Failed to load YOLOv8: {e}")
            raise

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect persons in frame.
        Returns list of {person_id, bbox, confidence}.
        """
        if not self._initialized:
            self.initialize()

        h, w = frame.shape[:2]

        # Run YOLOv8 inference — class 0 = person
        results = self._model(
            frame,
            conf=self.confidence,
            classes=[0],  # COCO class 0 = person
            verbose=False,
            imgsz=640,
        )

        raw_detections = []
        if results and len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None:
                for i in range(len(boxes)):
                    xyxy = boxes.xyxy[i].cpu().numpy()
                    conf = float(boxes.conf[i].cpu().numpy())

                    x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
                    # Clamp
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)

                    # Filter tiny detections
                    if (x2 - x1) < 15 or (y2 - y1) < 15:
                        continue

                    raw_detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "confidence": round(conf, 3),
                    })

                    if len(raw_detections) >= self.max_persons:
                        break

        # Track persons across frames
        return self._track(raw_detections)

    def _track(self, detections: List[Dict]) -> List[Dict]:
        """Simple IoU tracking for consistent person IDs."""
        now = time.time()

        # Remove stale tracks
        stale = [pid for pid, d in self._tracks.items() if now - d["last_seen"] > 5.0]
        for pid in stale:
            del self._tracks[pid]

        matched = set()
        results = []

        for det in detections:
            best_iou = 0
            best_id = None

            for pid, track in self._tracks.items():
                if pid in matched:
                    continue
                iou = self._iou(det["bbox"], track["bbox"])
                if iou > best_iou and iou > self._iou_thresh:
                    best_iou = iou
                    best_id = pid

            if best_id is not None:
                self._tracks[best_id]["bbox"] = det["bbox"]
                self._tracks[best_id]["last_seen"] = now
                matched.add(best_id)
                pid = best_id
            else:
                pid = self._next_id
                self._next_id += 1
                self._tracks[pid] = {
                    "bbox": det["bbox"],
                    "last_seen": now,
                    "first_seen": now,
                }

            results.append({
                "person_id": pid,
                "bbox": det["bbox"],
                "confidence": det["confidence"],
            })

        return results

    @staticmethod
    def _iou(b1, b2) -> float:
        x1 = max(b1[0], b2[0]); y1 = max(b1[1], b2[1])
        x2 = min(b1[2], b2[2]); y2 = min(b1[3], b2[3])
        inter = max(0, x2-x1) * max(0, y2-y1)
        a1 = (b1[2]-b1[0]) * (b1[3]-b1[1])
        a2 = (b2[2]-b2[0]) * (b2[3]-b2[1])
        union = a1 + a2 - inter
        return inter / union if union > 0 else 0

    def get_count(self) -> int:
        """Current tracked person count."""
        return len(self._tracks)

    def reset(self):
        self._tracks.clear()
        self._next_id = 1
