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


import cv2
import numpy as np
import logging
import time
import threading
import concurrent.futures
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
    Master pipeline optimized for real-time responsiveness.
    Uses a background worker pool for heavy AI analysis (Emotion, Recognition).
    """

    def __init__(
        self,
        face_model: str = "opencv_dnn",
        face_confidence: float = 0.35,
        emotion_model: str = "auto",
        emotion_update_interval: float = 2.0,
        head_pose_enabled: bool = True,
        max_faces: int = 40,
        engagement_weights: Dict[str, float] = None,
        alert_threshold: int = 40,
        confusion_alert_duration: int = 120,
        match_threshold: float = 0.6,
        deep_face_threshold: float = 0.45,
        attendance_check_interval: int = 3,
        late_threshold_minutes: int = 10,
    ):
        # Sub-modules
        self.face_detector = FaceDetector(
            model_type=face_model,
            confidence_threshold=face_confidence,
            max_faces=max_faces,
        )

        self.person_detector = PersonDetector(
            confidence=0.25,
            model_size="n",
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
        
        # --- Async Analysis State ---
        # Cache for heavy analysis results (persisted across frames using FaceID)
        self._face_analysis_cache: Dict[int, Dict[str, Any]] = {}
        # Track active background tasks to avoid redundant processing
        self._active_tasks: Dict[int, concurrent.futures.Future] = {}
        # Thread pool for heavy AI workers (Emotion, Recognition)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="AIWorker")

        # --- Multi-camera fusion ---
        self._camera_results: Dict[str, Dict[str, Any]] = {}
        self._camera_timestamps: Dict[str, float] = {}
        self._camera_stale_timeout = 5.0

    def initialize(self):
        """Initialize all AI modules."""
        if self._initialized:
            return

        logger.info("[ClassroomDetector] Initializing AI modules (Master Mode)...")

        self.face_detector.initialize()
        try:
            self.person_detector.initialize()
        except Exception as e:
            logger.warning(f"Person detector init failed: {e}")
            
        self.emotion_recognizer.initialize()
        self.head_pose_estimator.initialize()
        self.attendance_tracker.initialize()

        self._initialized = True
        logger.info("[ClassroomDetector] All modules initialized ✓")

    def _analyze_face_async(self, face_id: int, face_crop: np.ndarray):
        """Background worker function for heavy face analysis."""
        try:
            # 1. Emotion Recognition (Heavy)
            emotion = self.emotion_recognizer.recognize_emotion(face_crop, face_id)
            
            # 2. Attendance/Recognition Matching (Heavy)
            self.attendance_tracker.check_attendance(face_id, face_crop)
            
            # 3. Pull latest student info
            student_name = self.attendance_tracker.get_student_name(face_id)
            student_id = self.attendance_tracker.get_student_id_for_face(face_id)
            
            return {
                "emotion": emotion,
                "student_name": student_name,
                "student_id": student_id,
                "last_update": time.time()
            }
        except Exception as e:
            logger.error(f"[AIWorker] Async analysis failed for face {face_id}: {e}")
            return None

    def process_frame(
        self,
        camera_id: str,
        camera_name: str,
        frame: np.ndarray,
    ) -> Optional[Dict[str, Any]]:
        """
        Responsive frame processing pipeline.
        
        1. Fast Detection (Faces + Persons)
        2. Fast Analysis (Head Pose)
        3. Async Heavy Analysis (Emotion + Identity)
        4. Calculation based on Cached/Recent results
        """
        if not self._initialized:
            self.initialize()

        if not self._processing_lock.acquire(blocking=False):
            return None

        start_time = time.time()

        try:
            # ── 1. Fast Detection ───────────────────────────
            # Person detection (YOLOv8)
            persons = []
            if self.person_detector._initialized:
                persons = self.person_detector.detect(frame)

            # Face detection (MediaPipe/DNN)
            faces = self.face_detector.detect_faces(frame)

            if not faces:
                return self._generate_empty_snapshot(camera_id, camera_name, persons)

            # ── 2. Analysis Dispatch ────────────────────────
            emotion_results = []
            head_pose_results = []
            active_face_ids = set()

            for face in faces:
                face_id = face["face_id"]
                bbox = face["bbox"]
                active_face_ids.add(face_id)

                # 2a. Fast: Head Pose Estimation
                head_pose = self.head_pose_estimator.estimate_pose(frame, bbox, face_id)
                if head_pose:
                    head_pose_results.append(head_pose)

                # 2b. Check Async Heavy Tasks (Emotion/Recognition)
                # If a background task is done, update cache
                if face_id in self._active_tasks:
                    future = self._active_tasks[face_id]
                    if future.done():
                        res = future.result()
                        if res:
                            self._face_analysis_cache[face_id] = res
                        del self._active_tasks[face_id]

                # Dispatch new task if enough time passed and not currently running
                last_upd = self._face_analysis_cache.get(face_id, {}).get("last_update", 0)
                should_update = (time.time() - last_upd) > self.emotion_recognizer.update_interval
                
                if should_update and face_id not in self._active_tasks:
                    face_crop = self.face_detector.crop_face(frame, bbox, margin=0.1)
                    if face_crop is not None:
                        self._active_tasks[face_id] = self._executor.submit(
                            self._analyze_face_async, face_id, face_crop
                        )

                # Use cached data for current frame analysis
                cached = self._face_analysis_cache.get(face_id)
                if cached and cached.get("emotion"):
                    emo_res = dict(cached["emotion"])
                    # Inject student identity if found
                    if cached.get("student_name"):
                        emo_res["student_name"] = cached["student_name"]
                        emo_res["student_id"] = cached["student_id"]
                    emotion_results.append(emo_res)

            # ── 3. Multi-camera Merge ───────────────────────
            partial = {
                "emotion_results": emotion_results,
                "head_pose_results": head_pose_results,
                "faces": faces,
                "persons": persons,
                "active_face_ids": active_face_ids,
            }
            self._camera_results[camera_id] = partial
            self._camera_timestamps[camera_id] = time.time()

            merged = self._merge_camera_results()

            # ── 4. Engagement Calculation ───────────────────
            snapshot = self.engagement_engine.calculate_engagement(
                merged["emotion_results"],
                merged["head_pose_results"],
                total_faces=merged["total_faces"],
            )

            # Enrich snapshot
            snapshot.update({
                "camera_id": camera_id,
                "camera_name": camera_name,
                "total_persons": merged["total_persons"],
                "persons": merged["persons_list"],
                "active_cameras": merged["active_cameras"],
            })

            # Cleanup stale caches
            self._cleanup_stale_cache(merged["all_active_face_ids"])

            # Stats
            process_time = (time.time() - start_time) * 1000
            self._frame_count += 1
            self._avg_process_time = self._avg_process_time * 0.9 + process_time * 0.1
            snapshot["process_time_ms"] = round(process_time, 1)

            return snapshot

        except Exception as e:
            logger.error(f"[ClassroomDetector] Pipeline error: {e}", exc_info=True)
            return None
        finally:
            self._processing_lock.release()

    def _generate_empty_snapshot(self, camera_id, camera_name, persons):
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "camera_id": camera_id,
            "camera_name": camera_name,
            "total_faces": 0,
            "total_persons": len(persons),
            "persons": [{"person_id": p["person_id"], "bbox": p["bbox"]} for p in persons],
            "avg_engagement": 0,
            "students": [],
            "emotion_distribution": {},
            "learning_state_distribution": {},
            "attention_distribution": {},
            "alerts": [],
            "process_time_ms": 0,
        }

    def _cleanup_stale_cache(self, active_face_ids):
        """Removes data for faces that haven't been seen for a while."""
        stale_ids = [fid for fid in self._face_analysis_cache if fid not in active_face_ids]
        # Keep recent stale for a few seconds in case of occlusion
        for fid in stale_ids:
            if time.time() - self._face_analysis_cache[fid].get("last_update", 0) > 10.0:
                del self._face_analysis_cache[fid]
                if fid in self._active_tasks:
                    del self._active_tasks[fid]

    def _merge_camera_results(self) -> Dict[str, Any]:
        """Merge results from all active cameras."""
        now = time.time()
        merged_emotions = []
        merged_head_poses = []
        total_faces = 0
        all_persons = []
        all_active_face_ids = set()
        active_cams = 0
        person_counts = []

        for cam_id, partial in self._camera_results.items():
            if now - self._camera_timestamps.get(cam_id, 0) > self._camera_stale_timeout:
                continue

            active_cams += 1
            merged_emotions.extend(partial.get("emotion_results", []))
            merged_head_poses.extend(partial.get("head_pose_results", []))
            total_faces += len(partial.get("faces", []))
            all_active_face_ids.update(partial.get("active_face_ids", set()))

            persons = partial.get("persons", [])
            person_counts.append(len(persons))
            all_persons.extend(persons)

        return {
            "emotion_results": merged_emotions,
            "head_pose_results": merged_head_poses,
            "total_faces": total_faces,
            "total_persons": max(person_counts) if person_counts else 0,
            "persons_list": all_persons,
            "all_active_face_ids": all_active_face_ids,
            "active_cameras": active_cams,
        }

    def start_session(self, session_id: int):
        if not self._initialized:
            self.initialize()
        self.attendance_tracker.start_session(session_id)
        self.engagement_engine.reset()
        self.face_detector.reset_tracking()
        self._face_analysis_cache.clear()
        self._active_tasks.clear()
        logger.info(f"[ClassroomDetector] Session {session_id} started (Cache cleared)")

    def stop_session(self) -> Dict[str, Any]:
        summary = self.engagement_engine.get_session_summary()
        attendance = self.attendance_tracker.get_attendance_summary()
        summary.update({
            "total_students": attendance["total"],
            "present_count": attendance["present"],
            "late_count": attendance["late"],
            "absent_count": attendance["absent"],
        })
        self.attendance_tracker.stop_session()
        return summary

    def enroll_student(self, student_id: str, name: str, face_crop: np.ndarray, class_name: str = "") -> bool:
        if not self._initialized:
            self.initialize()
        return self.attendance_tracker.enroll_face(student_id, name, face_crop, class_name)

    def get_attendance(self) -> Dict[str, Any]:
        return self.attendance_tracker.get_attendance_summary()

    def get_engagement_timeline(self) -> List[Dict]:
        return self.engagement_engine.get_engagement_timeline()

    def get_performance_stats(self) -> Dict[str, Any]:
        return {
            "total_frames": self._frame_count,
            "avg_process_time_ms": round(self._avg_process_time, 1),
            "tracked_faces": self.face_detector.get_track_count(),
            "active_ai_tasks": len(self._active_tasks),
        }
