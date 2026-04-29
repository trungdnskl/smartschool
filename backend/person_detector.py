"""
Classroom Engagement System - Person Detector (Enhanced)
YOLOv8-based person detection for accurate student headcount.
Detects full bodies even when faces are not visible (back turned, head down).

Enhancements:
  - Kalman Filter Tracking: Smooth bounding box predictions
  - Cross-camera Fusion: Merge person tracking across cameras
  - Face Validation: Integration point with face detection
  - Performance Stats: FPS tracking, detection counts
"""

import cv2
import numpy as np
import logging
import time
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"


class KalmanBoxTracker:
    """
    Kalman filter for tracking a single bounding box.
    State: [x_center, y_center, width, height, dx, dy, dw, dh]
    """
    _count = 0

    def __init__(self, bbox: List[int]):
        self.kf = cv2.KalmanFilter(8, 4)

        # Transition matrix (constant velocity model)
        self.kf.transitionMatrix = np.eye(8, dtype=np.float32)
        for i in range(4):
            self.kf.transitionMatrix[i, i + 4] = 1.0

        # Measurement matrix
        self.kf.measurementMatrix = np.zeros((4, 8), dtype=np.float32)
        for i in range(4):
            self.kf.measurementMatrix[i, i] = 1.0

        # Noise covariances
        self.kf.processNoiseCov = np.eye(8, dtype=np.float32) * 0.03
        self.kf.measurementNoiseCov = np.eye(4, dtype=np.float32) * 1.0
        self.kf.errorCovPost = np.eye(8, dtype=np.float32)

        # Initialize state
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        w, h = x2 - x1, y2 - y1
        self.kf.statePost = np.array(
            [cx, cy, w, h, 0, 0, 0, 0], dtype=np.float32
        ).reshape(8, 1)

        KalmanBoxTracker._count += 1
        self.id = KalmanBoxTracker._count
        self.hits = 1
        self.age = 0
        self.time_since_update = 0
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.confirmed = False  # Confirmed after min_hits

    def predict(self) -> List[int]:
        """Predict next bounding box."""
        self.kf.predict()
        self.age += 1
        self.time_since_update += 1
        state = self.kf.statePost.flatten()
        cx, cy, w, h = state[0], state[1], state[2], state[3]
        w, h = max(10, w), max(10, h)
        return [int(cx - w/2), int(cy - h/2), int(cx + w/2), int(cy + h/2)]

    def update(self, bbox: List[int]):
        """Update with new measurement."""
        x1, y1, x2, y2 = bbox
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        w, h = x2 - x1, y2 - y1
        measurement = np.array([cx, cy, w, h], dtype=np.float32).reshape(4, 1)
        self.kf.correct(measurement)
        self.hits += 1
        self.time_since_update = 0
        self.last_seen = time.time()
        if self.hits >= 3:
            self.confirmed = True

    def get_bbox(self) -> List[int]:
        """Get current estimated bbox."""
        state = self.kf.statePost.flatten()
        cx, cy, w, h = state[0], state[1], max(10, state[2]), max(10, state[3])
        return [int(cx - w/2), int(cy - h/2), int(cx + w/2), int(cy + h/2)]


class PersonDetector:
    """
    YOLOv8 person detector for classroom headcount.
    Detects class 0 (person) from COCO — works for all angles including
    overhead cameras where faces may not be visible.
    """

    def __init__(
        self,
        confidence: float = 0.20,
        model_size: str = "s",  # n=nano (fastest), s=small, m=medium
        max_persons: int = 50,
        kalman_enabled: bool = True,
        fusion_enabled: bool = True,
    ):
        self.confidence = confidence
        self.model_size = model_size
        self.max_persons = max_persons
        self.kalman_enabled = kalman_enabled
        self.fusion_enabled = fusion_enabled
        self._model = None
        self._initialized = False

        # Tracking
        self._trackers: List[KalmanBoxTracker] = []
        self._iou_thresh = 0.3
        self._max_age = 20          # Frames before removing lost track
        self._min_hits = 2          # Min detections to confirm track (lower = faster)

        # Cross-camera fusion
        self._camera_persons: Dict[str, List[Dict]] = {}
        self._camera_timestamps: Dict[str, float] = {}

        # Performance stats
        self._total_detections = 0
        self._frame_count = 0
        self._fps_start = time.time()
        self._last_fps = 0.0

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
            logger.info(f"[PersonDetector] ✓ YOLOv8{self.model_size} loaded (kalman={self.kalman_enabled})")

        except Exception as e:
            logger.error(f"[PersonDetector] Failed to load YOLOv8: {e}")
            raise

    def detect(self, frame: np.ndarray, camera_id: str = "default") -> List[Dict[str, Any]]:
        """
        Detect persons in frame.
        Returns list of {person_id, bbox, confidence, confirmed}.
        """
        if not self._initialized:
            self.initialize()

        h, w = frame.shape[:2]

        # Run YOLOv8 inference — class 0 = person
        # Use larger imgsz for overhead cameras where persons appear smaller
        results = self._model(
            frame,
            conf=self.confidence,
            classes=[0],  # COCO class 0 = person
            verbose=False,
            imgsz=960,
            iou=0.45,  # NMS IoU threshold — avoid merging adjacent students
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

                    # Filter very tiny detections (but keep small ones for overhead view)
                    if (x2 - x1) < 10 or (y2 - y1) < 10:
                        continue

                    raw_detections.append({
                        "bbox": [x1, y1, x2, y2],
                        "confidence": round(conf, 3),
                    })

                    if len(raw_detections) >= self.max_persons:
                        break

        # Update stats
        self._total_detections += len(raw_detections)
        self._frame_count += 1

        # Track persons across frames
        if self.kalman_enabled:
            tracked = self._kalman_track(raw_detections)
        else:
            tracked = self._simple_track(raw_detections)

        # Store for cross-camera fusion
        if self.fusion_enabled:
            self._camera_persons[camera_id] = tracked
            self._camera_timestamps[camera_id] = time.time()

        return tracked

    def _kalman_track(self, detections: List[Dict]) -> List[Dict]:
        """Kalman filter-based tracking for smooth predictions."""
        # Predict all existing trackers
        for trk in self._trackers:
            trk.predict()

        # Match detections to trackers using IoU
        if self._trackers and detections:
            iou_matrix = np.zeros((len(detections), len(self._trackers)))
            for d, det in enumerate(detections):
                for t, trk in enumerate(self._trackers):
                    iou_matrix[d, t] = self._iou(det["bbox"], trk.get_bbox())

            matched_det, matched_trk, unmatched_det = self._hungarian_match(iou_matrix)

            # Update matched trackers
            for d, t in zip(matched_det, matched_trk):
                self._trackers[t].update(detections[d]["bbox"])

            # Create new trackers for unmatched detections
            for d in unmatched_det:
                self._trackers.append(KalmanBoxTracker(detections[d]["bbox"]))
        elif detections:
            # No existing trackers, create all new
            for det in detections:
                self._trackers.append(KalmanBoxTracker(det["bbox"]))

        # Remove dead trackers
        self._trackers = [
            t for t in self._trackers
            if t.time_since_update <= self._max_age
        ]

        # Build results — include tracks predicted for ≤1 frame
        # This bridges short occlusions (student briefly hidden by another)
        results = []
        for trk in self._trackers:
            if trk.time_since_update > 1:
                continue  # Skip tracks not seen for >1 frame
            results.append({
                "person_id": trk.id,
                "bbox": trk.get_bbox(),
                "confidence": 0.0,
                "confirmed": trk.confirmed,
            })

        # Attach confidence from raw detections to matched tracks
        for det in detections:
            best_trk = None
            best_iou = 0
            for r in results:
                iou_val = self._iou(det["bbox"], r["bbox"])
                if iou_val > best_iou:
                    best_iou = iou_val
                    best_trk = r
            if best_trk and best_iou > 0.3:
                best_trk["confidence"] = det["confidence"]

        return results

    def _hungarian_match(self, iou_matrix: np.ndarray):
        """Simple greedy matching (avoids scipy dependency)."""
        matched_det, matched_trk = [], []
        used_det, used_trk = set(), set()

        # Greedy: pick highest IoU pairs
        while True:
            if iou_matrix.size == 0:
                break
            max_val = iou_matrix.max()
            if max_val < self._iou_thresh:
                break
            d, t = np.unravel_index(iou_matrix.argmax(), iou_matrix.shape)
            matched_det.append(d)
            matched_trk.append(t)
            used_det.add(d)
            used_trk.add(t)
            iou_matrix[d, :] = 0
            iou_matrix[:, t] = 0

        unmatched_det = [d for d in range(iou_matrix.shape[0]) if d not in used_det]
        return matched_det, matched_trk, unmatched_det

    def _simple_track(self, detections: List[Dict]) -> List[Dict]:
        """Simple IoU tracking (fallback without Kalman)."""
        now = time.time()

        # Build from existing tracker IDs for continuity
        existing = {}
        for trk in self._trackers:
            if now - trk.last_seen < 5.0:
                existing[trk.id] = trk

        matched = set()
        results = []

        for det in detections:
            best_iou = 0
            best_trk = None

            for tid, trk in existing.items():
                if tid in matched:
                    continue
                iou_val = self._iou(det["bbox"], trk.get_bbox())
                if iou_val > best_iou and iou_val > self._iou_thresh:
                    best_iou = iou_val
                    best_trk = trk

            if best_trk is not None:
                best_trk.update(det["bbox"])
                matched.add(best_trk.id)
                pid = best_trk.id
            else:
                new_trk = KalmanBoxTracker(det["bbox"])
                self._trackers.append(new_trk)
                pid = new_trk.id

            results.append({
                "person_id": pid,
                "bbox": det["bbox"],
                "confidence": det["confidence"],
                "confirmed": True,
            })

        return results

    def get_fused_count(self) -> int:
        """Get fused person count across all active cameras."""
        if not self.fusion_enabled:
            return self.get_count()

        now = time.time()
        counts = []
        for cam_id, persons in self._camera_persons.items():
            if now - self._camera_timestamps.get(cam_id, 0) < 5.0:
                counts.append(len(persons))

        # Use max across cameras (avoid double-counting)
        return max(counts) if counts else 0

    def validate_with_faces(self, persons: List[Dict], faces: List[Dict]) -> Dict[str, Any]:
        """
        Cross-validate person detections with face detections.
        Returns face_person_ratio and validation stats.
        """
        if not persons:
            return {"face_person_ratio": 0.0, "validated": 0, "unvalidated": 0}

        validated = 0
        for person in persons:
            p_bbox = person["bbox"]
            for face in faces:
                f_bbox = face.get("bbox", [0, 0, 0, 0])
                # Check if face center is inside person bbox
                fx = (f_bbox[0] + f_bbox[2]) / 2
                fy = (f_bbox[1] + f_bbox[3]) / 2
                if p_bbox[0] <= fx <= p_bbox[2] and p_bbox[1] <= fy <= p_bbox[3]:
                    validated += 1
                    break

        total = len(persons)
        return {
            "face_person_ratio": round(validated / total, 2) if total > 0 else 0.0,
            "validated": validated,
            "unvalidated": total - validated,
        }

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
        """Current tracked person count (confirmed only)."""
        now = time.time()
        return len([
            t for t in self._trackers
            if t.confirmed and (now - t.last_seen) < 5.0
        ])

    def get_person_detection_stats(self) -> Dict[str, Any]:
        """Get performance and tracking statistics."""
        now = time.time()
        elapsed = now - self._fps_start
        fps = self._frame_count / elapsed if elapsed > 0 else 0

        active = [t for t in self._trackers if (now - t.last_seen) < 5.0]
        confirmed = [t for t in active if t.confirmed]

        return {
            "total_detections": self._total_detections,
            "active_tracks": len(active),
            "confirmed_tracks": len(confirmed),
            "fps": round(fps, 1),
            "model_size": self.model_size,
            "kalman_enabled": self.kalman_enabled,
            "fusion_enabled": self.fusion_enabled,
        }

    def reset(self):
        self._trackers.clear()
        self._camera_persons.clear()
        self._camera_timestamps.clear()
        self._total_detections = 0
        self._frame_count = 0
        self._fps_start = time.time()
        KalmanBoxTracker._count = 0
