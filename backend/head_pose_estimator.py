"""
Classroom Engagement System - Head Pose Estimator
Ước tính hướng nhìn và tư thế đầu - CPU Optimized
Sử dụng MediaPipe Face Mesh (tối ưu cho CPU)
"""

import cv2
import numpy as np
import logging
import time
from typing import Optional, Dict, Any, List, Tuple
from collections import deque

logger = logging.getLogger(__name__)

# Tên tiếng Việt cho hướng nhìn
ATTENTION_NAMES_VI = {
    "looking_at_teacher": "Nhìn bảng/GV",
    "looking_away": "Nhìn chỗ khác",
    "looking_down": "Cúi đầu",
    "head_down": "Gục đầu",
}

# Điểm attention cho mỗi hướng nhìn
ATTENTION_SCORES = {
    "looking_at_teacher": 100,
    "looking_away": 30,
    "looking_down": 25,
    "head_down": 5,
}


class HeadPoseEstimator:
    """
    Ước tính tư thế đầu (yaw, pitch, roll) từ khuôn mặt.
    Sử dụng MediaPipe Face Mesh cho 468 landmarks, tối ưu CPU.
    Fallback: dùng OpenCV solvePnP với 6 điểm đặc trưng.
    """

    def __init__(
        self,
        enabled: bool = True,
        window_size: int = 5,
    ):
        self.enabled = enabled
        self.window_size = window_size

        self._face_mesh = None
        self._initialized = False
        self._use_mediapipe = False

        # Sliding window per face_id
        self._pose_history: Dict[int, deque] = {}
        self._cached_results: Dict[int, Dict] = {}

        # 3D model points for solvePnP (generic face model)
        self._model_points = np.array([
            (0.0, 0.0, 0.0),        # Nose tip
            (0.0, -330.0, -65.0),    # Chin
            (-225.0, 170.0, -135.0), # Left eye corner
            (225.0, 170.0, -135.0),  # Right eye corner
            (-150.0, -150.0, -125.0),# Left mouth corner
            (150.0, -150.0, -125.0), # Right mouth corner
        ], dtype=np.float64)

    def initialize(self):
        """Initialize head pose estimation model."""
        if self._initialized or not self.enabled:
            return

        try:
            import mediapipe as mp
            from mediapipe.tasks.python import vision, BaseOptions
            import os
            import urllib.request
            
            # Use robust Tasks API (v0.10.x+)
            model_path = os.path.join("hf_models", "face_landmarker.task")
            if not os.path.exists(model_path):
                logger.info(f"[HeadPose] Downloading FaceLandmarker model to {model_path}...")
                os.makedirs("hf_models", exist_ok=True)
                urllib.request.urlretrieve(
                    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
                    model_path
                )

            base_options = BaseOptions(model_asset_path=model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=True,
                num_faces=1
            )
            self._detector = vision.FaceLandmarker.create_from_options(options)
            self._use_mediapipe = True
            logger.info("[HeadPose] MediaPipe FaceLandmarker loaded (tasks API)")

        except Exception as e:
            logger.warning(f"[HeadPose] MediaPipe init error: {e}, using OpenCV fallback")
            self._use_mediapipe = False

        self._initialized = True
        logger.info(f"[HeadPose] Initialized (ML: {'MediaPipe Tasks' if self._use_mediapipe else 'OpenCV solvePnP'})")

    def estimate_pose(
        self,
        frame: np.ndarray,
        face_bbox: List[int],
        face_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Estimate head pose for a detected face.
        Returns yaw, pitch, roll and attention direction.
        """
        if not self.enabled:
            return self._default_result(face_id)

        if not self._initialized:
            self.initialize()

        x1, y1, x2, y2 = face_bbox
        face_crop = frame[y1:y2, x1:x2]

        if face_crop.size == 0:
            return self._default_result(face_id)

        if self._use_mediapipe:
            pose = self._estimate_mediapipe(frame, face_bbox, face_id)
        else:
            pose = self._estimate_opencv(frame, face_bbox, face_id)

        if pose is None:
            return self._cached_results.get(face_id, self._default_result(face_id))

        # Smooth with sliding window
        if face_id not in self._pose_history:
            self._pose_history[face_id] = deque(maxlen=self.window_size)
        self._pose_history[face_id].append(pose)

        smoothed = self._smooth_pose(face_id)
        self._cached_results[face_id] = smoothed
        return smoothed

    def _estimate_mediapipe(
        self, frame: np.ndarray, bbox: List[int], face_id: int
    ) -> Optional[Dict[str, float]]:
        """Estimate pose using MediaPipe FaceLandmarker."""
        try:
            import mediapipe as mp
            x1, y1, x2, y2 = bbox
            face_img = frame[y1:y2, x1:x2]

            if face_img.size == 0:
                return None

            # Convert to RGB for MediaPipe
            rgb_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_face)
            
            results = self._detector.detect(mp_image)

            if not results.face_landmarks:
                return None

            landmarks = results.face_landmarks[0]
            h, w = face_img.shape[:2]

            # Key landmark indices
            # Nose tip: 1, Chin: 152, Left eye: 33, Right eye: 263
            # Left mouth: 61, Right mouth: 291
            nose = landmarks[1]
            chin = landmarks[152]
            left_eye = landmarks[33]
            right_eye = landmarks[263]
            left_mouth = landmarks[61]
            right_mouth = landmarks[291]

            # Convert to pixel coordinates
            image_points = np.array([
                (nose.x * w, nose.y * h),
                (chin.x * w, chin.y * h),
                (left_eye.x * w, left_eye.y * h),
                (right_eye.x * w, right_eye.y * h),
                (left_mouth.x * w, left_mouth.y * h),
                (right_mouth.x * w, right_mouth.y * h),
            ], dtype=np.float64)

            # Camera matrix approximation
            focal_length = w
            center = (w / 2, h / 2)
            camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1],
            ], dtype=np.float64)

            dist_coeffs = np.zeros((4, 1))

            success, rotation_vec, translation_vec = cv2.solvePnP(
                self._model_points,
                image_points,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )

            if not success:
                return None

            # Convert rotation vector to Euler angles
            rotation_mat, _ = cv2.Rodrigues(rotation_vec)
            angles = self._rotation_matrix_to_euler(rotation_mat)

            yaw = float(angles[1])    # Left-right
            pitch = float(angles[0])  # Up-down
            roll = float(angles[2])   # Tilt

            return {"yaw": yaw, "pitch": pitch, "roll": roll}

        except Exception as e:
            logger.debug(f"[HeadPose] MediaPipe error: {e}")
            return None

    def _estimate_opencv(
        self, frame: np.ndarray, bbox: List[int], face_id: int
    ) -> Optional[Dict[str, float]]:
        """
        Estimate pose using OpenCV Haar + solvePnP.
        Fallback when MediaPipe is not available.
        """
        try:
            x1, y1, x2, y2 = bbox
            face_w = x2 - x1
            face_h = y2 - y1

            # Simple heuristic based on face position in frame
            frame_h, frame_w = frame.shape[:2]
            face_center_x = (x1 + x2) / 2
            face_center_y = (y1 + y2) / 2

            # Estimate yaw from horizontal position
            rel_x = (face_center_x - frame_w / 2) / (frame_w / 2)
            yaw = rel_x * 45  # Approximate: full frame width = ±45 degrees

            # Estimate pitch from face aspect ratio and vertical position
            aspect = face_w / max(face_h, 1)
            rel_y = (face_center_y - frame_h / 2) / (frame_h / 2)
            pitch = rel_y * 30

            # Estimate roll (minimal for sitting students)
            roll = 0.0

            return {"yaw": yaw, "pitch": pitch, "roll": roll}

        except Exception:
            return None

    def _smooth_pose(self, face_id: int) -> Dict[str, Any]:
        """Smooth pose estimation with sliding window."""
        history = self._pose_history.get(face_id, deque())
        if not history:
            return self._default_result(face_id)

        # Average yaw, pitch, roll
        yaws = [h["yaw"] for h in history]
        pitches = [h["pitch"] for h in history]
        rolls = [h["roll"] for h in history]

        avg_yaw = sum(yaws) / len(yaws)
        avg_pitch = sum(pitches) / len(pitches)
        avg_roll = sum(rolls) / len(rolls)

        # Classify attention direction
        direction = self._classify_attention(avg_yaw, avg_pitch, avg_roll)
        attention_score = ATTENTION_SCORES.get(direction, 50)

        return {
            "face_id": face_id,
            "yaw": round(avg_yaw, 1),
            "pitch": round(avg_pitch, 1),
            "roll": round(avg_roll, 1),
            "attention_direction": direction,
            "attention_direction_vi": ATTENTION_NAMES_VI.get(direction, direction),
            "attention_score": attention_score,
        }

    def _classify_attention(self, yaw: float, pitch: float, roll: float) -> str:
        """
        Classify attention direction from Euler angles.
        Thresholds tuned for classroom / webcam setting.

        Pitch convention (from solvePnP):
          - Positive pitch → head tilted DOWN (chin toward chest)
          - Negative pitch → head tilted UP (looking at screen/teacher)

        In a typical webcam scenario the camera is at or above eye level,
        so students looking at the screen normally have pitch ≈ -5 to +10°.
        Only a very large positive pitch (> 40°) indicates head truly
        drooping (sleeping/resting).
        """
        # Gục đầu (head truly drooping — sleeping/resting)
        # Only triggered by LARGE positive pitch (chin toward chest)
        if pitch > 40:
            return "head_down"

        # Cúi đầu (looking down at phone/notebook)
        if pitch > 25:
            return "looking_down"

        # Nhìn chỗ khác (looking away sideways)
        if abs(yaw) > 30:
            return "looking_away"

        # Negative pitch (looking up) or moderate angles → attentive
        return "looking_at_teacher"

    @staticmethod
    def _rotation_matrix_to_euler(rotation_matrix: np.ndarray) -> np.ndarray:
        """Convert rotation matrix to Euler angles (degrees)."""
        sy = np.sqrt(rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2)

        if sy > 1e-6:
            x = np.arctan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
            y = np.arctan2(-rotation_matrix[2, 0], sy)
            z = np.arctan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
        else:
            x = np.arctan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
            y = np.arctan2(-rotation_matrix[2, 0], sy)
            z = 0

        return np.degrees(np.array([x, y, z]))

    def _default_result(self, face_id: int) -> Dict[str, Any]:
        """Default result when estimation fails."""
        return {
            "face_id": face_id,
            "yaw": 0.0,
            "pitch": 0.0,
            "roll": 0.0,
            "attention_direction": "looking_at_teacher",
            "attention_direction_vi": "Nhìn bảng/GV",
            "attention_score": 100,
        }

    def cleanup_stale(self, active_face_ids: set):
        """Remove data for faces no longer tracked."""
        stale_ids = set(self._pose_history.keys()) - active_face_ids
        for fid in stale_ids:
            self._pose_history.pop(fid, None)
            self._cached_results.pop(fid, None)
