"""
Classroom Engagement System - Face Detector
Hybrid: MediaPipe BlazeFace (primary) + OpenCV DNN (fallback)
Multi-scale tiled detection for overhead classroom cameras.
"""

import cv2
import numpy as np
import logging
import os
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
MODEL_DIR = BASE_DIR / "models"


class FaceDetector:
    """
    Hybrid face detector optimized for classroom cameras:
    - MediaPipe BlazeFace: better at angles, side faces, small faces
    - OpenCV DNN SSD: fallback if MediaPipe unavailable
    - 3x3 tiled detection: catches small faces in wide-angle 1080p streams
    """

    def __init__(
        self,
        model_type: str = "opencv_dnn",
        confidence_threshold: float = 0.35,
        max_faces: int = 40,
    ):
        self.model_type = model_type
        self.confidence_threshold = confidence_threshold
        self.max_faces = max_faces

        self._mp_detector = None
        self._dnn_detector = None
        self._haar_detector = None
        self._initialized = False
        self._use_mediapipe = False

        # Face tracking state
        self._next_face_id = 1
        self._tracked_faces: Dict[int, Dict] = {}
        self._iou_threshold = 0.3

    def initialize(self):
        """Initialize face detection — try MediaPipe first, then OpenCV DNN."""
        if self._initialized:
            return

        os.makedirs(str(MODEL_DIR), exist_ok=True)

        # Try MediaPipe BlazeFace (best for classroom overhead cameras)
        mp_model = MODEL_DIR / "blaze_face_short_range.tflite"
        if mp_model.exists():
            try:
                self._init_mediapipe(str(mp_model))
                self._use_mediapipe = True
                logger.info("[FaceDetector] ✓ MediaPipe BlazeFace loaded (primary)")
            except Exception as e:
                logger.warning(f"[FaceDetector] MediaPipe init failed: {e}")

        # Always init OpenCV DNN as fallback / supplement
        if self.model_type == "opencv_dnn":
            self._init_opencv_dnn()
        elif self.model_type == "haar":
            self._init_haar_cascade()
        else:
            self._init_opencv_dnn()

        self._initialized = True
        mode = "MediaPipe+DNN" if self._use_mediapipe else self.model_type
        logger.info(f"[FaceDetector] Initialized with {mode}")

    def _init_mediapipe(self, model_path: str):
        """Initialize MediaPipe Face Detector (Tasks API)."""
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python import BaseOptions

        options = vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            min_detection_confidence=self.confidence_threshold,
            running_mode=vision.RunningMode.IMAGE,
        )
        self._mp_detector = vision.FaceDetector.create_from_options(options)

    def _init_opencv_dnn(self):
        """Initialize OpenCV DNN face detector (Caffe model)."""
        prototxt_path = str(MODEL_DIR / "deploy.prototxt")
        caffemodel_path = str(MODEL_DIR / "res10_300x300_ssd_iter_140000.caffemodel")

        if not os.path.exists(prototxt_path) or not os.path.exists(caffemodel_path):
            logger.warning("[FaceDetector] DNN model files not found, downloading...")
            self._download_dnn_model(prototxt_path, caffemodel_path)

        if os.path.exists(prototxt_path) and os.path.exists(caffemodel_path):
            self._dnn_detector = cv2.dnn.readNetFromCaffe(prototxt_path, caffemodel_path)
            self._dnn_detector.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self._dnn_detector.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            logger.info("[FaceDetector] OpenCV DNN model loaded")
        else:
            logger.warning("[FaceDetector] Falling back to Haar cascade")
            self._init_haar_cascade()
            self.model_type = "haar"

    def _download_dnn_model(self, prototxt_path: str, caffemodel_path: str):
        """Download OpenCV face detector DNN model files."""
        import urllib.request
        prototxt_url = (
            "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
        )
        caffemodel_url = (
            "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/"
            "res10_300x300_ssd_iter_140000.caffemodel"
        )
        try:
            logger.info("[FaceDetector] Downloading deploy.prototxt...")
            urllib.request.urlretrieve(prototxt_url, prototxt_path)
            logger.info("[FaceDetector] Downloading caffemodel (10MB)...")
            urllib.request.urlretrieve(caffemodel_url, caffemodel_path)
            logger.info("[FaceDetector] Model files downloaded successfully")
        except Exception as e:
            logger.error(f"[FaceDetector] Download failed: {e}")

    def _init_haar_cascade(self):
        """Initialize Haar cascade face detector (built into OpenCV)."""
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._haar_detector = cv2.CascadeClassifier(cascade_path)
        logger.info("[FaceDetector] Haar cascade loaded")

    # ─────────────────────────────────────────────────
    # Detection methods
    # ─────────────────────────────────────────────────

    def detect_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect faces using multi-scale tiled approach.
        For large frames (>800px), splits into 3x3 tiles for small faces.
        """
        if not self._initialized:
            self.initialize()

        if self._use_mediapipe:
            raw = self._detect_mediapipe_multiscale(frame)
        elif self._dnn_detector is not None:
            raw = self._detect_dnn_multiscale(frame)
        elif self._haar_detector is not None:
            raw = self._detect_haar(frame)
        else:
            raw = []

        return self._track_faces(raw)

    # ── MediaPipe detection ──────────────────────────

    def _detect_mp_single(self, frame: np.ndarray, ox: int = 0, oy: int = 0) -> List[Dict]:
        """Run MediaPipe face detection on a single region."""
        import mediapipe as mp

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        result = self._mp_detector.detect(mp_image)
        h, w = frame.shape[:2]
        faces = []

        for det in result.detections:
            bb = det.bounding_box
            x1 = max(0, bb.origin_x) + ox
            y1 = max(0, bb.origin_y) + oy
            x2 = min(w, bb.origin_x + bb.width) + ox
            y2 = min(h, bb.origin_y + bb.height) + oy

            if (x2 - x1) < 15 or (y2 - y1) < 15:
                continue

            conf = det.categories[0].score if det.categories else 0.5
            faces.append({
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "confidence": round(float(conf), 3),
            })

        return faces

    def _detect_mediapipe_multiscale(self, frame: np.ndarray) -> List[Dict]:
        """MediaPipe + tiled detection for small faces in large frames."""
        h, w = frame.shape[:2]

        # Pass 1: Full frame
        all_faces = self._detect_mp_single(frame)

        # Pass 2: Tiled for small faces (3x3 grid with overlap)
        if w > 640:
            tiles_x = 3 if w > 1200 else 2
            tiles_y = 3 if h > 800 else 2
            overlap = 0.2

            tw = int(w / tiles_x * (1 + overlap))
            th = int(h / tiles_y * (1 + overlap))

            for row in range(tiles_y):
                for col in range(tiles_x):
                    ox = int(col * w / tiles_x)
                    oy = int(row * h / tiles_y)
                    ex = min(ox + tw, w)
                    ey = min(oy + th, h)

                    tile = frame[oy:ey, ox:ex]
                    if tile.shape[0] < 50 or tile.shape[1] < 50:
                        continue
                    tile_faces = self._detect_mp_single(tile, ox, oy)
                    all_faces.extend(tile_faces)

        return self._nms(all_faces, iou_threshold=0.4)

    # ── OpenCV DNN detection ─────────────────────────

    def _detect_dnn_single(self, frame: np.ndarray, ox: int = 0, oy: int = 0) -> List[Dict]:
        """Run DNN detection on a single image region."""
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)),
            1.0, (300, 300),
            (104.0, 177.0, 123.0),
            swapRB=False, crop=False
        )

        self._dnn_detector.setInput(blob)
        detections = self._dnn_detector.forward()

        faces = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence < self.confidence_threshold:
                continue

            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            x1, y1, x2, y2 = box.astype(int)
            x1 += ox; y1 += oy; x2 += ox; y2 += oy

            if (x2 - x1) < 20 or (y2 - y1) < 20:
                continue

            faces.append({
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "confidence": round(float(confidence), 3),
            })

        return faces

    def _detect_dnn_multiscale(self, frame: np.ndarray) -> List[Dict]:
        """DNN + tiled detection for small faces."""
        h, w = frame.shape[:2]
        all_faces = self._detect_dnn_single(frame)

        if w > 640:
            tiles_x = 3 if w > 1200 else 2
            tiles_y = 3 if h > 800 else 2
            overlap = 0.2
            tw = int(w / tiles_x * (1 + overlap))
            th = int(h / tiles_y * (1 + overlap))

            for row in range(tiles_y):
                for col in range(tiles_x):
                    ox = int(col * w / tiles_x)
                    oy = int(row * h / tiles_y)
                    ex = min(ox + tw, w)
                    ey = min(oy + th, h)
                    tile = frame[oy:ey, ox:ex]
                    all_faces.extend(self._detect_dnn_single(tile, ox, oy))

        return self._nms(all_faces, iou_threshold=0.4)

    # ── Haar detection ───────────────────────────────

    def _detect_haar(self, frame: np.ndarray) -> List[Dict]:
        """Detect faces using Haar cascade."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        rects = self._haar_detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5,
            minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE,
        )

        faces = []
        for (x, y, w, h) in rects:
            faces.append({
                "bbox": [int(x), int(y), int(x + w), int(y + h)],
                "confidence": 0.9,
            })
            if len(faces) >= self.max_faces:
                break
        return faces

    # ─────────────────────────────────────────────────
    # NMS + Tracking
    # ─────────────────────────────────────────────────

    def _nms(self, faces: List[Dict], iou_threshold: float = 0.4) -> List[Dict]:
        """Non-maximum suppression to remove duplicate bboxes."""
        if len(faces) <= 1:
            return faces

        faces = sorted(faces, key=lambda f: f["confidence"], reverse=True)
        kept = []
        for face in faces:
            if len(kept) >= self.max_faces:
                break
            is_dup = False
            for k in kept:
                if self._compute_iou(face["bbox"], k["bbox"]) > iou_threshold:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(face)
        return kept

    def _track_faces(self, detections: List[Dict]) -> List[Dict[str, Any]]:
        """IoU-based face tracking across frames — assign consistent IDs."""
        current_time = time.time()

        # Remove stale tracks (>3s)
        stale = [fid for fid, d in self._tracked_faces.items() if current_time - d["last_seen"] > 3.0]
        for fid in stale:
            del self._tracked_faces[fid]

        matched = set()
        results = []

        for det in detections:
            best_iou = 0
            best_id = None

            for fid, track in self._tracked_faces.items():
                if fid in matched:
                    continue
                iou = self._compute_iou(det["bbox"], track["bbox"])
                if iou > best_iou and iou > self._iou_threshold:
                    best_iou = iou
                    best_id = fid

            if best_id is not None:
                self._tracked_faces[best_id]["bbox"] = det["bbox"]
                self._tracked_faces[best_id]["last_seen"] = current_time
                matched.add(best_id)
                face_id = best_id
            else:
                face_id = self._next_face_id
                self._next_face_id += 1
                self._tracked_faces[face_id] = {
                    "bbox": det["bbox"],
                    "last_seen": current_time,
                    "first_seen": current_time,
                }

            results.append({
                "face_id": face_id,
                "bbox": det["bbox"],
                "confidence": det["confidence"],
            })

        return results

    @staticmethod
    def _compute_iou(box1: List[int], box2: List[int]) -> float:
        """Compute IoU between two bounding boxes."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0

    def crop_face(self, frame: np.ndarray, bbox: List[int], margin: float = 0.2) -> Optional[np.ndarray]:
        """Crop face region with margin."""
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        mx = int((x2 - x1) * margin)
        my = int((y2 - y1) * margin)
        x1, y1 = max(0, x1 - mx), max(0, y1 - my)
        x2, y2 = min(w, x2 + mx), min(h, y2 + my)
        crop = frame[y1:y2, x1:x2]
        return crop if crop.size > 0 else None

    def get_track_count(self) -> int:
        return len(self._tracked_faces)

    def reset_tracking(self):
        self._tracked_faces.clear()
        self._next_face_id = 1
