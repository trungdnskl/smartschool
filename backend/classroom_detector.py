"""
Classroom Engagement System - Master Pipeline (Classroom Detector)
Kết hợp tất cả AI modules để phân tích lớp học
"""

import cv2
import numpy as np
import logging
import time
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime

from face_detector import FaceDetector
from person_detector import PersonDetector
from emotion_recognizer import EmotionRecognizer
from head_pose_estimator import HeadPoseEstimator
from attendance_tracker import AttendanceTracker
from engagement_engine import EngagementEngine

logger = logging.getLogger(__name__)


class ClassroomDetector:
    """
    Master pipeline kết hợp:
    1. Face Detection
    2. Emotion Recognition
    3. Head Pose Estimation
    4. Attendance Tracking
    5. Engagement Scoring

    Tối ưu cho CPU: xử lý tuần tự, sử dụng caching.
    """

    def __init__(
        self,
        face_model: str = "opencv_dnn",
        face_confidence: float = 0.35,
        emotion_model: str = "auto",  # "auto" → HuggingFace → FER → rules
        emotion_update_interval: float = 2.0,
        head_pose_enabled: bool = True,
        max_faces: int = 40,
        engagement_weights: Dict[str, float] = None,
        alert_threshold: int = 40,
        confusion_alert_duration: int = 120,
        match_threshold: float = 0.6,
        deep_face_threshold: float = 0.45,  # ISSUE-06: separate threshold for deep engines
        attendance_check_interval: int = 3,
        late_threshold_minutes: int = 10,
    ):
        # Sub-modules
        self.face_detector = FaceDetector(
            model_type=face_model,
            confidence_threshold=face_confidence,
            max_faces=max_faces,
        )

        # YOLOv8 person detector for accurate headcount
        self.person_detector = PersonDetector(
            confidence=0.25,
            model_size="n",  # nano = fastest
            max_persons=50,
        )

        self.emotion_recognizer = EmotionRecognizer(
            model_type=emotion_model,
            update_interval=emotion_update_interval,
        )

        self.head_pose_estimator = HeadPoseEstimator(
            enabled=head_pose_enabled,
        )

        self.attendance_tracker = AttendanceTracker(
            match_threshold=match_threshold,
            deep_face_threshold=deep_face_threshold,
            check_interval=attendance_check_interval,
            late_threshold_minutes=late_threshold_minutes,
        )

        self.engagement_engine = EngagementEngine(
            weights=engagement_weights or {"emotion": 0.35, "attention": 0.45, "behavior": 0.20},
            alert_threshold=alert_threshold,
            confusion_alert_duration=confusion_alert_duration,
        )

        self._initialized = False
        self._processing_lock = threading.Lock()
        self._frame_count = 0
        self._last_process_time = 0
        self._avg_process_time = 0
        self._last_person_count = 0

        # ── Multi-camera fusion ───────────────────────────
        # Mỗi camera lưu partial result riêng, merge trước khi tính engagement
        self._camera_results: Dict[str, Dict[str, Any]] = {}
        self._camera_timestamps: Dict[str, float] = {}
        self._camera_stale_timeout = 5.0  # seconds — bỏ qua cam nếu > 5s không gửi frame

    def initialize(self):
        """Initialize all AI modules."""
        if self._initialized:
            return

        logger.info("[ClassroomDetector] Initializing AI modules...")

        try:
            self.face_detector.initialize()
            logger.info("[ClassroomDetector] ✓ Face Detector")
        except Exception as e:
            logger.error(f"[ClassroomDetector] ✗ Face Detector: {e}")
            raise

        try:
            self.person_detector.initialize()
            logger.info("[ClassroomDetector] ✓ Person Detector (YOLOv8)")
        except Exception as e:
            logger.warning(f"[ClassroomDetector] ✗ Person Detector: {e}")

        try:
            self.emotion_recognizer.initialize()
            logger.info("[ClassroomDetector] ✓ Emotion Recognizer")
        except Exception as e:
            logger.warning(f"[ClassroomDetector] ✗ Emotion Recognizer: {e}")

        try:
            self.head_pose_estimator.initialize()
            logger.info("[ClassroomDetector] ✓ Head Pose Estimator")
        except Exception as e:
            logger.warning(f"[ClassroomDetector] ✗ Head Pose Estimator: {e}")

        try:
            self.attendance_tracker.initialize()
            logger.info("[ClassroomDetector] ✓ Attendance Tracker")
        except Exception as e:
            logger.warning(f"[ClassroomDetector] ✗ Attendance Tracker: {e}")

        self._initialized = True
        logger.info("[ClassroomDetector] All modules initialized ✓")

    def process_frame(
        self,
        camera_id: str,
        camera_name: str,
        frame: np.ndarray,
    ) -> Optional[Dict[str, Any]]:
        """
        Full processing pipeline for a single video frame.

        Steps:
        1. Detect faces
        2. For each face: emotion + head pose + attendance
        3. Calculate engagement scores
        4. Generate alerts
        5. Return classroom snapshot
        """
        if not self._initialized:
            self.initialize()

        # ISSUE-05 fix: Use lock instead of bare boolean for thread safety
        if not self._processing_lock.acquire(blocking=False):
            return None  # Skip if still processing previous frame

        start_time = time.time()

        try:
            # Step 0: Person detection (YOLOv8) for headcount
            persons = []
            # Lazy init: if failed during startup, try again now
            if not self.person_detector._initialized:
                try:
                    self.person_detector.initialize()
                    logger.info("[ClassroomDetector] ✓ Person Detector (YOLOv8) — lazy init")
                except Exception as e:
                    logger.warning(f"[ClassroomDetector] PersonDetector lazy init failed: {e}")

            if self.person_detector._initialized:
                try:
                    persons = self.person_detector.detect(frame)
                    self._last_person_count = len(persons)
                except Exception as e:
                    logger.debug(f"[ClassroomDetector] Person detect error: {e}")

            # Step 1: Detect faces
            faces = self.face_detector.detect_faces(frame)

            if not faces:
                return {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "camera_id": camera_id,
                    "camera_name": camera_name,
                    "total_faces": 0,
                    "total_persons": len(persons),
                    "persons": [{"person_id": p["person_id"], "bbox": p["bbox"], "confidence": p["confidence"]} for p in persons],
                    "avg_engagement": 0,
                    "students": [],
                    "emotion_distribution": {},
                    "learning_state_distribution": {},
                    "attention_distribution": {},
                    "alerts": [],
                    "process_time_ms": 0,
                }

            # Step 2: Process each face
            emotion_results = []
            head_pose_results = []
            active_face_ids = set()

            for face in faces:
                face_id = face["face_id"]
                bbox = face["bbox"]
                active_face_ids.add(face_id)

                # Crop face for emotion recognition
                face_crop = self.face_detector.crop_face(frame, bbox, margin=0.1)

                # 2a. Emotion Recognition
                if face_crop is not None:
                    emotion = self.emotion_recognizer.recognize_emotion(face_crop, face_id)
                    if emotion:
                        # Add student info if known
                        student_name = self.attendance_tracker.get_student_name(face_id)
                        student_id = self.attendance_tracker.get_student_id_for_face(face_id)
                        if student_name:
                            emotion["student_name"] = student_name
                            emotion["student_id"] = student_id
                        emotion_results.append(emotion)

                # 2b. Head Pose Estimation
                head_pose = self.head_pose_estimator.estimate_pose(frame, bbox, face_id)
                if head_pose:
                    head_pose_results.append(head_pose)

                # 2c. Attendance Check (less frequently)
                if face_crop is not None:
                    self.attendance_tracker.check_attendance(face_id, face_crop)

            # ── Multi-camera merge ────────────────────────
            # Lưu partial result của camera này
            partial = {
                "emotion_results": emotion_results,
                "head_pose_results": head_pose_results,
                "faces": faces,
                "persons": persons,
                "active_face_ids": active_face_ids,
            }
            self._camera_results[camera_id] = partial
            self._camera_timestamps[camera_id] = time.time()

            # Merge tất cả camera còn active (< stale_timeout)
            merged = self._merge_camera_results()

            # Step 3: Calculate engagement từ merged data
            snapshot = self.engagement_engine.calculate_engagement(
                merged["emotion_results"],
                merged["head_pose_results"],
                total_faces=merged["total_faces"],
            )

            # Add camera info + person count
            snapshot["camera_id"] = camera_id
            snapshot["camera_name"] = camera_name
            snapshot["total_persons"] = merged["total_persons"]
            snapshot["persons"] = merged["persons_list"]
            snapshot["active_cameras"] = merged["active_cameras"]

            # Fix: ensure attention_distribution counts ALL detected head poses
            if merged["head_pose_results"]:
                att_dist = {}
                for hp in merged["head_pose_results"]:
                    ad = hp.get("attention_direction", "looking_at_teacher")
                    att_dist[ad] = att_dist.get(ad, 0) + 1
                engine_att = snapshot.get("attention_distribution", {})
                if not engine_att:
                    snapshot["attention_distribution"] = att_dist

            # Cleanup stale data
            self.emotion_recognizer.cleanup_stale(merged["all_active_face_ids"])
            self.head_pose_estimator.cleanup_stale(merged["all_active_face_ids"])

            # Performance tracking
            process_time = (time.time() - start_time) * 1000
            self._frame_count += 1
            self._avg_process_time = (
                self._avg_process_time * 0.9 + process_time * 0.1
            )
            snapshot["process_time_ms"] = round(process_time, 1)

            if self._frame_count % 50 == 0:
                logger.info(
                    f"[ClassroomDetector] Frame #{self._frame_count} | "
                    f"Cams: {merged['active_cameras']} | "
                    f"People: {merged['total_persons']} | Faces: {merged['total_faces']} | "
                    f"Engagement: {snapshot.get('avg_engagement', 0):.0f}% | "
                    f"Time: {process_time:.0f}ms (avg: {self._avg_process_time:.0f}ms)"
                )

            return snapshot

        except Exception as e:
            logger.error(f"[ClassroomDetector] Processing error: {e}")
            return None

        finally:
            self._processing_lock.release()

    def _merge_camera_results(self) -> Dict[str, Any]:
        """
        Merge partial results from all active cameras.

        Nguyên lý 1 lớp = 2 camera (trước + sau):
        - Face IDs từ mỗi camera được offset để không trùng
          (cam_front: face 0-99, cam_rear: face 100-199)
        - Person counts KHÔNG cộng dồn (tránh đếm trùng)
          → lấy max(cam_front, cam_rear) làm sĩ số ước tính
        - Emotion/Head pose: gộp tất cả (mỗi cam nhìn các HS khác nhau)
        """
        now = time.time()
        merged_emotions = []
        merged_head_poses = []
        total_faces = 0
        all_persons = []
        all_active_face_ids = set()
        active_cams = 0
        person_counts = []  # per-camera person counts

        for cam_id, partial in self._camera_results.items():
            # Skip stale cameras (no frame in > 5s)
            age = now - self._camera_timestamps.get(cam_id, 0)
            if age > self._camera_stale_timeout:
                continue

            active_cams += 1
            merged_emotions.extend(partial.get("emotion_results", []))
            merged_head_poses.extend(partial.get("head_pose_results", []))
            total_faces += len(partial.get("faces", []))
            all_active_face_ids.update(partial.get("active_face_ids", set()))

            persons = partial.get("persons", [])
            person_counts.append(len(persons))
            all_persons.extend(
                {"person_id": p["person_id"], "bbox": p["bbox"],
                 "confidence": p["confidence"], "camera_id": cam_id}
                for p in persons
            )

        # Sĩ số = max person count across cameras (tránh đếm trùng)
        # Nếu cam trước thấy 30, cam sau thấy 28 → sĩ số ≈ 30
        total_persons = max(person_counts) if person_counts else 0

        return {
            "emotion_results": merged_emotions,
            "head_pose_results": merged_head_poses,
            "total_faces": total_faces,
            "total_persons": total_persons,
            "persons_list": all_persons,
            "all_active_face_ids": all_active_face_ids,
            "active_cameras": active_cams,
        }

    def start_session(self, session_id: int):
        """
        Start a new monitoring session.

        Fix D2: Check _initialized trước khi start — auto-init nếu chưa.
        Fix D1: attendance_tracker.start_session() có thể load embeddings
                từ disk (I/O blocking), nhưng vì được gọi từ async context
                qua run_in_executor (xem sessions.py), nên OK.
        """
        if not self._initialized:
            logger.warning("[ClassroomDetector] Not initialized — auto-initializing...")
            self.initialize()

        self.attendance_tracker.start_session(session_id)
        self.engagement_engine.reset()
        self.face_detector.reset_tracking()
        logger.info(f"[ClassroomDetector] Session {session_id} started")

    def stop_session(self) -> Dict[str, Any]:
        """Stop monitoring session and return summary."""
        summary = self.engagement_engine.get_session_summary()
        attendance = self.attendance_tracker.get_attendance_summary()

        summary.update({
            "total_students": attendance["total"],
            "present_count": attendance["present"],
            "late_count": attendance["late"],
            "absent_count": attendance["absent"],
        })

        self.attendance_tracker.stop_session()
        logger.info("[ClassroomDetector] Session stopped")
        return summary

    def enroll_student(
        self, student_id: str, name: str, face_crop: np.ndarray, class_name: str = ""
    ) -> bool:
        """Enroll a student for attendance tracking."""
        if not self._initialized:
            self.initialize()
        return self.attendance_tracker.enroll_face(student_id, name, face_crop, class_name)

    def get_attendance(self) -> Dict[str, Any]:
        """Get current attendance status."""
        return self.attendance_tracker.get_attendance_summary()

    def get_engagement_timeline(self) -> List[Dict]:
        """Get engagement history for charts."""
        return self.engagement_engine.get_engagement_timeline()

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get processing performance stats."""
        return {
            "total_frames": self._frame_count,
            "avg_process_time_ms": round(self._avg_process_time, 1),
            "tracked_faces": self.face_detector.get_track_count(),
            "face_model": self.face_detector.model_type,
        }
