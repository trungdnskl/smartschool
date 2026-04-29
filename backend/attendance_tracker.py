"""
Classroom Engagement System - Attendance Tracker
Điểm danh tự động qua nhận dạng khuôn mặt

Dual-Engine:
  Primary:  ArcFace (InsightFace buffalo_l) - accuracy 94-99%
  Fallback: LBPH Face Recognizer (OpenCV) - accuracy 75-85%

Hỏ trợ 2 nguồn embeddings:
  - Google Colab: data/face_embeddings/deep_embeddings.pkl
  - Camera trực tiếp: chụp tại chỗ qua dashboard
"""

import cv2
import numpy as np
import logging
import os
import json
import time
import base64
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent


class AttendanceTracker:
    """
    Theo dõi điểm danh học sinh qua nhận dạng khuôn mặt.
    
    Dual-Engine (tự động chọn engine tốt nhất):
    1. ArcFace (InsightFace) - nếu có file deep_embeddings.pkl
    2. LBPH (OpenCV) - fallback khi chưa chạy Google Colab
    """

    def __init__(
        self,
        match_threshold: float = 0.6,
        deep_face_threshold: float = 0.45,  # ISSUE-06: configurable deep engine threshold
        check_interval: int = 10,
        late_threshold_minutes: int = 10,
        embeddings_dir: str = None,
        thumbnails_dir: str = None,
        face_size: tuple = (160, 160),
        lbph_radius: int = 2,
        lbph_neighbors: int = 8,
        lbph_grid_x: int = 8,
        lbph_grid_y: int = 8,
    ):
        self.match_threshold = match_threshold
        self.deep_face_threshold = deep_face_threshold
        self.check_interval = check_interval
        self.late_threshold_minutes = late_threshold_minutes
        self.embeddings_dir = embeddings_dir or str(PROJECT_DIR / "data" / "face_embeddings")
        self.thumbnails_dir = thumbnails_dir or str(PROJECT_DIR / "data" / "thumbnails")
        self.face_size = face_size

        # LBPH parameters
        self.lbph_radius = lbph_radius
        self.lbph_neighbors = lbph_neighbors
        self.lbph_grid_x = lbph_grid_x
        self.lbph_grid_y = lbph_grid_y

        self._face_recognizer = None
        self._initialized = False
        self._recognizer_trained = False

        # Enrolled faces: student_id -> {name, samples: [gray_faces], ...}
        self._enrolled_faces: Dict[str, Dict] = {}

        # LBPH label mapping: label_int -> student_id
        self._label_to_student: Dict[int, str] = {}
        self._student_to_label: Dict[str, int] = {}
        self._next_label = 0

        # Current session attendance
        self._attendance: Dict[str, Dict] = {}
        self._last_check: Dict[int, float] = {}
        self._face_to_student: Dict[int, str] = {}

        # Recognition confidence history for each face_id
        self._recognition_history: Dict[int, List[Tuple[str, float]]] = {}

        # P1-4: Smart cooldown — confirmed faces get longer intervals
        self._confirmed_faces: Dict[int, str] = {}  # face_id → student_id (confirmed matches)
        self._confirmed_cooldown: int = 30  # seconds between re-checks for confirmed faces

        # Session info
        self._session_start: Optional[datetime] = None
        self._session_id: Optional[int] = None
        
        # Face recognizer — set by initialize()
        self._deep_recognizer = None
        self._use_deep: bool = False
        self._deep_engine_name: str = "none"

        # ── Teacher tracking ──────────────────────────────
        # Teachers enrolled separately, excluded from student headcount.
        # Key: teacher_id (e.g. "teacher_nguyen"), Value: {name, ...}
        self._teacher_faces: Dict[str, Dict] = {}
        self._teacher_face_ids: set = set()  # face_ids recognized as teacher
        self._teacher_detected: bool = False
        self._teacher_info: Optional[Dict[str, str]] = None  # {id, name}

        # Headcount: from person detection (set externally each frame)
        self._current_total_persons: int = 0

    def initialize(self):
        """
        Initialize face recognition — 3-tier engine cascade:
          1. InsightFace ONNX (buffalo_l ArcFace) — fastest, no TensorFlow
          2. DeepFace (ArcFace/Facenet512) — fallback if InsightFace unavailable
          3. LBPH (OpenCV) — final fallback, always initialized
        """
        if self._initialized:
            return

        os.makedirs(self.embeddings_dir, exist_ok=True)
        os.makedirs(self.thumbnails_dir, exist_ok=True)

        # ===== TIER 1: InsightFace ONNX (preferred) =====
        try:
            from hf_models.insightface_recognizer import InsightFaceRecognizer
            from deep_face_recognizer import DEEP_EMBEDDINGS_FILE

            recognizer = InsightFaceRecognizer(threshold=self.deep_face_threshold)
            ok = recognizer.initialize()

            if ok and DEEP_EMBEDDINGS_FILE.exists():
                self._deep_recognizer = recognizer
                self._use_deep = True
                self._deep_engine_name = "insightface"
                stats = recognizer.get_stats()
                logger.info(
                    f"[Attendance] ✓ InsightFace ONNX ACTIVE — "
                    f"{stats['enrolled_students']} students "
                    f"(~50-120ms/face, no TensorFlow)"
                )
            elif ok:
                # Model OK but no embeddings yet
                self._deep_recognizer = recognizer
                self._deep_engine_name = "insightface"
                logger.info(
                    "[Attendance] InsightFace OK — no embeddings yet "
                    "(enroll students via dashboard)"
                )
            else:
                raise RuntimeError("InsightFace initialized but model not available")

        except (ImportError, Exception) as e:
            logger.info(f"[Attendance] InsightFace unavailable ({e}) — trying DeepFace")

            # ===== TIER 2: DeepFace (ArcFace/Facenet512) =====
            try:
                from deep_face_recognizer import ArcFaceRecognizer, DEEP_EMBEDDINGS_FILE

                recognizer = ArcFaceRecognizer(threshold=self.deep_face_threshold)
                ok = recognizer.initialize()

                if ok and DEEP_EMBEDDINGS_FILE.exists():
                    self._deep_recognizer = recognizer
                    self._use_deep = True
                    self._deep_engine_name = "deepface"
                    stats = recognizer.get_stats()
                    logger.info(
                        f"[Attendance] ✓ DeepFace engine ACTIVE — "
                        f"{stats['enrolled_students']} students, "
                        f"model={stats.get('model', '?')}"
                    )
                elif ok:
                    self._deep_recognizer = recognizer
                    self._deep_engine_name = "deepface"
                    logger.info("[Attendance] DeepFace OK — no embeddings yet")
                else:
                    logger.warning(
                        "[Attendance] DeepFace model not available. "
                        "Install: pip install insightface onnxruntime  (recommended) "
                        "or: pip install deepface tf-keras"
                    )

            except (ImportError, Exception) as e2:
                logger.info(f"[Attendance] DeepFace unavailable ({e2}) — using LBPH only")

        # ===== TIER 3: LBPH — always init as final fallback =====
        try:
            self._face_recognizer = cv2.face.LBPHFaceRecognizer_create(
                radius=self.lbph_radius,
                neighbors=self.lbph_neighbors,
                grid_x=self.lbph_grid_x,
                grid_y=self.lbph_grid_y,
                threshold=200.0,
            )
            logger.info("[Attendance] LBPH fallback initialized")
        except AttributeError:
            logger.warning("[Attendance] OpenCV contrib not available — no LBPH fallback")
            self._face_recognizer = None

        self._load_enrolled_faces()
        self._train_recognizer()

        self._initialized = True
        if self._use_deep:
            engine_label = f"{self._deep_engine_name} (deep learning)"
        else:
            engine_label = "LBPH (OpenCV)"
        logger.info(
            f"[Attendance] Active engine: {engine_label} | "
            f"LBPH students: {len(self._enrolled_faces)}, trained: {self._recognizer_trained}"
        )

    def start_session(self, session_id: int):
        """Start a new attendance tracking session."""
        self._session_id = session_id
        self._session_start = datetime.now()
        self._attendance.clear()
        self._face_to_student.clear()
        self._recognition_history.clear()
        self._confirmed_faces.clear()  # P1-4: Reset smart cooldown
        self._teacher_face_ids.clear()
        self._teacher_detected = False
        self._teacher_info = None
        self._current_total_persons = 0

        # ISSUE-04 fix: Clear deep recognizer voting history to prevent
        # false positives from previous session bleeding into new one
        if self._deep_recognizer:
            try:
                self._deep_recognizer.clear_history()
            except Exception as e:
                logger.debug(f"[Attendance] clear deep history: {e}")

        # P0-2: Sync names between LBPH ↔ ArcFace ↔ disk before session
        self._sync_student_names()

        # Initialize all LBPH-enrolled students as absent (skip teachers)
        for student_id, data in self._enrolled_faces.items():
            # Skip teacher faces — they are not students
            if data.get("is_teacher") or data.get("class_name") == "__teacher__":
                self._teacher_faces[student_id] = {
                    "name": data["name"],
                    "enrolled_at": data.get("enrolled_at", ""),
                }
                continue
            self._attendance[student_id] = {
                "student_id": student_id,
                "student_name": data["name"],
                "class_name": data.get("class_name", ""),
                "status": "absent",
                "arrival_time": None,
                "face_id": None,
                "match_score": 0,
                "match_engine": None,       # P2-5: Which engine matched
                "match_confidence": 0,      # P2-5: Match confidence score
                "has_photo": self._has_thumbnail(student_id),
            }

        # ISSUE-02 fix: Merge students from deep embeddings DB that are NOT
        # in LBPH enrolled_faces (e.g. imported from Colab pkl).
        # Without this, students only in deep DB would not appear in
        # attendance summary → incorrect absent/present totals.
        if self._deep_recognizer and hasattr(self._deep_recognizer, '_db'):
            for student_id, data in self._deep_recognizer._db.items():
                if student_id not in self._attendance:
                    name = data.get('name', student_id) if isinstance(data, dict) else student_id
                    self._attendance[student_id] = {
                        "student_id": student_id,
                        "student_name": name,
                        "class_name": "",
                        "status": "absent",
                        "arrival_time": None,
                        "face_id": None,
                        "match_score": 0,
                        "match_engine": None,       # P2-5
                        "match_confidence": 0,       # P2-5
                        "has_photo": self._has_thumbnail(student_id),
                        "engine": "arcface",
                    }

        total = len(self._attendance)
        lbph_count = len(self._enrolled_faces)
        deep_only = total - lbph_count
        logger.info(
            f"[Attendance] Session {session_id} started | "
            f"total={total} (LBPH={lbph_count}, deep-only={deep_only})"
        )

    def stop_session(self):
        """Stop current session."""
        self._session_id = None
        self._session_start = None
        self._recognition_history.clear()
        self._confirmed_faces.clear()  # P1-4: Reset smart cooldown
        self._teacher_face_ids.clear()
        self._teacher_detected = False
        self._teacher_info = None

        # ISSUE-04 fix: Also clear deep recognizer voting history on stop
        if self._deep_recognizer:
            try:
                self._deep_recognizer.clear_history()
            except Exception as e:
                logger.debug(f"[Attendance] clear deep history on stop: {e}")

        logger.info("[Attendance] Session stopped")

    def enroll_face(
        self,
        student_id: str,
        name: str,
        face_crop: np.ndarray,
        class_name: str = "",
    ) -> bool:
        """
        Enroll a student's face for attendance tracking.
        Supports multi-sample: call multiple times for the same student_id
        to add more face samples (different angles, lighting).
        """
        if not self._initialized:
            self.initialize()

        if face_crop is None or face_crop.size == 0:
            logger.warning(f"[Attendance] Empty face crop for {student_id}")
            return False

        try:
            # Preprocess face
            gray = self._preprocess_face(face_crop)
            if gray is None:
                return False

            # Generate augmented samples
            augmented = self._augment_face(gray)

            # Check if student already enrolled (add more samples)
            if student_id in self._enrolled_faces:
                existing = self._enrolled_faces[student_id]
                max_samples = 50  # Max augmented samples per student
                current_count = len(existing["samples"])
                
                if current_count >= max_samples:
                    logger.info(f"[Attendance] {student_id} already has {current_count} samples (max)")
                else:
                    for aug in augmented:
                        if len(existing["samples"]) < max_samples:
                            existing["samples"].append(aug)
                    logger.info(f"[Attendance] Added {len(augmented)} samples for {name} "
                                f"(total: {len(existing['samples'])})")
            else:
                # New enrollment
                self._enrolled_faces[student_id] = {
                    "name": name,
                    "class_name": class_name,
                    "samples": augmented,
                    "enrolled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

            # Save thumbnail (96x96 color)
            self._save_thumbnail(student_id, face_crop)

            # Save samples to disk
            self._save_samples(student_id, name, class_name)

            # Re-train LBPH recognizer with new data
            self._train_recognizer()

            # Deep engine enrollment (if initialized but perhaps not previously active)
            if self._deep_recognizer:
                try:
                    # Send original color image to deep engine (not grayscale)
                    added = self._deep_recognizer.enroll(student_id, name, [face_crop])
                    if added > 0:
                        self._use_deep = True  # Activate deep engine!
                        self._deep_engine_name = self._deep_engine_name or "insightface"
                        logger.info(
                            f"[Attendance] Deep engine enrolled {added} embedding(s) for {student_id} "
                            f"— deep engine ACTIVE (is_available={self._deep_recognizer.is_available})"
                        )
                except Exception as deep_e:
                    logger.warning(f"[Attendance] Deep engine enroll failed: {deep_e}")

            logger.info(f"[Attendance] Enrolled: {name} ({student_id}) "
                        f"with {len(self._enrolled_faces[student_id]['samples'])} LBPH samples")
            return True

        except Exception as e:
            logger.error(f"[Attendance] Enrollment failed for {student_id}: {e}", exc_info=True)
            return False

    def check_attendance(
        self,
        face_id: int,
        face_crop: np.ndarray,
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a detected face matches any enrolled student.
        
        Dual-Engine:
        - ArcFace (buffalo_l): Primary, high accuracy (94-99%)
        - LBPH: Fallback if InsightFace not available
        """
        if not self._initialized:
            self.initialize()

        # P1-4: Smart cooldown — confirmed faces get much longer intervals
        now = time.time()
        if face_id in self._last_check:
            elapsed = now - self._last_check[face_id]
            # Use longer cooldown for already-confirmed faces
            cooldown = self._confirmed_cooldown if face_id in self._confirmed_faces else self.check_interval
            if elapsed < cooldown:
                if face_id in self._face_to_student:
                    sid = self._face_to_student[face_id]
                    return self._attendance.get(sid)
                return None

        self._last_check[face_id] = now

        if face_crop is None or face_crop.size == 0:
            return None

        # ===== ENGINE SELECTION =====
        if self._use_deep and self._deep_recognizer and self._deep_recognizer.is_available:
            result = self._check_attendance_arcface(face_id, face_crop)
            if result:
                return result
            # Fallback to LBPH if ArcFace didn't match
        if self._enrolled_faces and self._recognizer_trained:
            return self._check_attendance_lbph(face_id, face_crop)
        return None

    def _check_attendance_arcface(
        self, face_id: int, face_crop: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """ArcFace-based attendance check (Primary engine)."""
        try:
            student_id, similarity, name = self._deep_recognizer.identify(face_crop, face_id)
            
            if student_id is None:
                logger.debug(f"[Attendance] ArcFace: face#{face_id} → no match (sim={similarity:.3f})")
                return None
            
            logger.info(f"[Attendance] ✓ ArcFace MATCH: face#{face_id} → {name} ({student_id}) sim={similarity:.3f}")
            
            self._face_to_student[face_id] = student_id

            # ── Teacher check: if recognized person is a teacher, skip student logic ──
            if self.check_if_teacher(face_id, student_id):
                logger.info(f"[Attendance] Teacher detected: {name} (face#{face_id}) — excluded from student headcount")
                return {"student_id": student_id, "student_name": name, "role": "teacher", "status": "teacher"}
            
            # Sync to attendance dict — student may not be in LBPH enrolled_faces
            if student_id not in self._attendance:
                self._attendance[student_id] = {
                    "student_id": student_id,
                    "student_name": name or student_id,
                    "class_name": "",
                    "status": "absent",
                    "arrival_time": None,
                    "face_id": None,
                    "match_score": 0,
                    "has_photo": self._has_thumbnail(student_id),
                    "engine": "arcface",
                }
            
            record = self._attendance[student_id]
            
            if record["status"] == "absent":
                arrival = datetime.now()
                is_late = False
                if self._session_start:
                    diff = (arrival - self._session_start).total_seconds() / 60
                    is_late = diff > self.late_threshold_minutes
                
                record["status"] = "late" if is_late else "present"
                record["arrival_time"] = arrival.strftime("%H:%M:%S")
                record["face_id"] = face_id
                record["match_score"] = round(similarity, 3)
                record["engine"] = "arcface"
                record["match_engine"] = "arcface"          # P2-5
                record["match_confidence"] = round(similarity, 3)  # P2-5
                
                # P1-4: Mark as confirmed → longer cooldown for this face
                self._confirmed_faces[face_id] = student_id
                
                logger.info(
                    f"[Attendance] ✓ {name} ({student_id}) → {record['status']} "
                    f"(ArcFace sim: {similarity:.3f})"
                )
            else:
                # Update confidence even for already-present students
                record["match_confidence"] = round(similarity, 3)  # P2-5
            
            return record

        except Exception as e:
            logger.debug(f"[Attendance] ArcFace check error: {e}")
            return None

    def _check_attendance_lbph(
        self, face_id: int, face_crop: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """LBPH-based attendance check (Fallback engine)."""
        try:
            gray = self._preprocess_face(face_crop)
            if gray is None:
                return None

            label, confidence = self._face_recognizer.predict(gray)
            similarity = max(0, 1.0 - (confidence / 200.0))
            student_id = self._label_to_student.get(label)

            if student_id is None:
                return None

            if face_id not in self._recognition_history:
                self._recognition_history[face_id] = []
            self._recognition_history[face_id].append((student_id, similarity))
            if len(self._recognition_history[face_id]) > 5:
                self._recognition_history[face_id] = self._recognition_history[face_id][-5:]

            final_id, final_score = self._majority_vote(face_id)

            if final_id and final_score >= self.match_threshold:
                self._face_to_student[face_id] = final_id

                # ── Teacher check (LBPH path) ──
                if self.check_if_teacher(face_id, final_id):
                    name = self._enrolled_faces.get(final_id, {}).get("name", final_id)
                    logger.info(f"[Attendance] Teacher detected (LBPH): {name} (face#{face_id})")
                    return {"student_id": final_id, "student_name": name, "role": "teacher", "status": "teacher"}

                if final_id in self._attendance:
                    record = self._attendance[final_id]

                    if record["status"] == "absent":
                        arrival = datetime.now()
                        is_late = False
                        if self._session_start:
                            diff = (arrival - self._session_start).total_seconds() / 60
                            is_late = diff > self.late_threshold_minutes

                        record["status"] = "late" if is_late else "present"
                        record["arrival_time"] = arrival.strftime("%H:%M:%S")
                        record["face_id"] = face_id
                        record["match_score"] = round(final_score, 3)
                        record["engine"] = "lbph"
                        record["match_engine"] = "lbph"            # P2-5
                        record["match_confidence"] = round(final_score, 3)  # P2-5

                        # P1-4: Mark as confirmed → longer cooldown
                        self._confirmed_faces[face_id] = final_id

                        logger.info(
                            f"[Attendance] ✓ {self._enrolled_faces[final_id]['name']} "
                            f"→ {record['status']} (LBPH score: {final_score:.3f})"
                        )

                    return record

            return None

        except Exception as e:
            logger.debug(f"[Attendance] LBPH check error: {e}")
            return None

    def delete_student(self, student_id: str) -> bool:
        """Delete a student and all their data (LBPH + deep engine + files)."""
        try:
            # Remove from enrolled faces (LBPH)
            if student_id in self._enrolled_faces:
                del self._enrolled_faces[student_id]

            # ISSUE-01 fix: Also remove from deep recognizer embeddings DB
            # Without this, deleted students remain as phantom entries in
            # deep_embeddings.pkl and can still be recognized by ArcFace.
            if self._deep_recognizer:
                try:
                    self._deep_recognizer.remove_student(student_id)
                    logger.info(f"[Attendance] Removed {student_id} from deep engine")
                except Exception as deep_e:
                    logger.warning(f"[Attendance] Deep engine remove failed: {deep_e}")

            # Delete embedding files
            samples_dir = os.path.join(self.embeddings_dir, student_id)
            if os.path.exists(samples_dir):
                import shutil
                shutil.rmtree(samples_dir)

            # Delete legacy JSON file
            json_path = os.path.join(self.embeddings_dir, f"{student_id}.json")
            if os.path.exists(json_path):
                os.remove(json_path)

            # Delete thumbnail
            thumb_path = os.path.join(self.thumbnails_dir, f"{student_id}.jpg")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)

            # Re-train LBPH recognizer
            self._train_recognizer()

            logger.info(f"[Attendance] Deleted student: {student_id}")
            return True

        except Exception as e:
            logger.error(f"[Attendance] Delete failed: {e}")
            return False

    def get_thumbnail_base64(self, student_id: str) -> Optional[str]:
        """Get student thumbnail as base64 string."""
        thumb_path = os.path.join(self.thumbnails_dir, f"{student_id}.jpg")
        if os.path.exists(thumb_path):
            with open(thumb_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        return None

    def get_thumbnail_path(self, student_id: str) -> Optional[str]:
        """Get student thumbnail file path."""
        thumb_path = os.path.join(self.thumbnails_dir, f"{student_id}.jpg")
        if os.path.exists(thumb_path):
            return thumb_path
        return None

    def get_enrolled_count(self) -> int:
        """Get number of enrolled students."""
        return len(self._enrolled_faces)

    def get_enrolled_students_info(self) -> List[Dict[str, Any]]:
        """Get info about all enrolled students (LBPH + deep engine)."""
        result = []
        seen = set()

        # LBPH enrolled students
        for student_id, data in self._enrolled_faces.items():
            lbph_count = len(data.get("samples", []))
            deep_count = 0
            if self._deep_recognizer:
                info = self._deep_recognizer.get_student_info(student_id)
                if info:
                    deep_count = info.get("embedding_count", 0)
            result.append({
                "student_id": student_id,
                "name": data["name"],
                "class_name": data.get("class_name", ""),
                "sample_count": lbph_count + deep_count,
                "lbph_samples": lbph_count,
                "deep_embeddings": deep_count,
                "enrolled_at": data.get("enrolled_at", ""),
                "has_photo": self._has_thumbnail(student_id),
            })
            seen.add(student_id)

        # Deep-only students (not in LBPH)
        if self._deep_recognizer and hasattr(self._deep_recognizer, '_db'):
            for student_id, data in self._deep_recognizer._db.items():
                if student_id not in seen:
                    emb_count = len(data.get("embeddings", [])) if isinstance(data, dict) else 0
                    result.append({
                        "student_id": student_id,
                        "name": data.get("name", student_id) if isinstance(data, dict) else student_id,
                        "class_name": data.get("class_name", "") if isinstance(data, dict) else "",
                        "sample_count": emb_count,
                        "lbph_samples": 0,
                        "deep_embeddings": emb_count,
                        "enrolled_at": data.get("enrolled_at", "") if isinstance(data, dict) else "",
                        "has_photo": self._has_thumbnail(student_id),
                    })

        return result

    # =============== PREPROCESSING ===============

    def _preprocess_face(self, face_crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Preprocess face image for recognition.
        Steps: BGR→Gray → Resize → Equalize histogram → Denoise
        """
        try:
            if face_crop is None or face_crop.size == 0:
                return None

            # Convert to grayscale
            if len(face_crop.shape) == 3:
                gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            else:
                gray = face_crop.copy()

            # Resize to standard size (important for LBPH)
            gray = cv2.resize(gray, self.face_size, interpolation=cv2.INTER_AREA)

            # CLAHE (Contrast Limited Adaptive Histogram Equalization)
            # Better than simple equalizeHist for varying lighting
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)

            # Light denoising
            gray = cv2.GaussianBlur(gray, (3, 3), 0)

            return gray

        except Exception as e:
            logger.debug(f"[Attendance] Preprocess error: {e}")
            return None

    def _augment_face(self, gray_face: np.ndarray) -> List[np.ndarray]:
        """
        Generate augmented samples from a single face image.
        This significantly improves recognition accuracy with limited enrollment photos.
        """
        augmented = [gray_face.copy()]

        # 1. Horizontal flip (mirror)
        flipped = cv2.flip(gray_face, 1)
        augmented.append(flipped)

        # 2. Brightness variations
        for alpha in [0.85, 1.15]:  # Darker and brighter
            adjusted = cv2.convertScaleAbs(gray_face, alpha=alpha, beta=0)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            adjusted = clahe.apply(adjusted)
            augmented.append(adjusted)

        # 3. Slight rotation (-5°, +5°)
        h, w = gray_face.shape
        center = (w // 2, h // 2)
        for angle in [-5, 5]:
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(gray_face, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
            augmented.append(rotated)

        return augmented

    # =============== LBPH TRAINING ===============

    def _train_recognizer(self):
        """Train LBPH recognizer with all enrolled samples."""
        if self._face_recognizer is None:
            logger.warning("[Attendance] No LBPH recognizer available!")
            return

        faces = []
        labels = []
        self._label_to_student.clear()
        self._student_to_label.clear()
        self._next_label = 0

        for student_id, data in self._enrolled_faces.items():
            samples = data.get("samples", [])
            if not samples:
                continue

            label = self._next_label
            self._label_to_student[label] = student_id
            self._student_to_label[student_id] = label
            self._next_label += 1

            for sample in samples:
                # Ensure correct size
                if sample.shape != self.face_size:
                    sample = cv2.resize(sample, self.face_size)
                faces.append(sample)
                labels.append(label)

        if not faces:
            self._recognizer_trained = False
            logger.info("[Attendance] No samples to train on")
            return

        faces_array = np.array(faces)
        labels_array = np.array(labels, dtype=np.int32)

        try:
            self._face_recognizer.train(faces_array, labels_array)
            self._recognizer_trained = True
            logger.info(f"[Attendance] LBPH trained: {len(faces)} samples, "
                        f"{self._next_label} students")
        except Exception as e:
            logger.error(f"[Attendance] LBPH training failed: {e}")
            self._recognizer_trained = False

    # =============== MAJORITY VOTING ===============

    def _majority_vote(self, face_id: int) -> Tuple[Optional[str], float]:
        """
        Use majority voting from recognition history to determine final ID.
        This reduces false positives from single-frame noise.
        """
        history = self._recognition_history.get(face_id, [])
        if not history:
            return None, 0.0

        # Count votes per student_id
        votes: Dict[str, List[float]] = {}
        for sid, score in history:
            if sid not in votes:
                votes[sid] = []
            votes[sid].append(score)

        # Find winner by count, then by average score
        best_id = None
        best_count = 0
        best_avg_score = 0.0

        for sid, scores in votes.items():
            count = len(scores)
            avg_score = sum(scores) / len(scores)

            if count > best_count or (count == best_count and avg_score > best_avg_score):
                best_id = sid
                best_count = count
                best_avg_score = avg_score

        return best_id, best_avg_score

    # =============== STORAGE ===============

    def _save_samples(self, student_id: str, name: str, class_name: str = ""):
        """Save face samples to disk as individual images + metadata JSON."""
        student_dir = os.path.join(self.embeddings_dir, student_id)
        os.makedirs(student_dir, exist_ok=True)

        data = self._enrolled_faces.get(student_id)
        if not data:
            return

        # Save metadata
        meta = {
            "student_id": student_id,
            "name": name,
            "class_name": class_name,
            "sample_count": len(data["samples"]),
            "enrolled_at": data.get("enrolled_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        }
        meta_path = os.path.join(student_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # Save each sample as PNG image
        for i, sample in enumerate(data["samples"]):
            img_path = os.path.join(student_dir, f"sample_{i:03d}.png")
            cv2.imwrite(img_path, sample)

    def _save_thumbnail(self, student_id: str, face_crop: np.ndarray):
        """Save a 96x96 JPEG thumbnail for dashboard display."""
        try:
            thumb = cv2.resize(face_crop, (96, 96), interpolation=cv2.INTER_AREA)
            thumb_path = os.path.join(self.thumbnails_dir, f"{student_id}.jpg")
            cv2.imwrite(thumb_path, thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
        except Exception as e:
            logger.debug(f"[Attendance] Thumbnail save error: {e}")

    def _has_thumbnail(self, student_id: str) -> bool:
        """Check if a thumbnail exists."""
        return os.path.exists(os.path.join(self.thumbnails_dir, f"{student_id}.jpg"))

    def _load_enrolled_faces(self):
        """Load all enrolled face samples from disk."""
        if not os.path.exists(self.embeddings_dir):
            return

        loaded_count = 0

        for entry in os.listdir(self.embeddings_dir):
            entry_path = os.path.join(self.embeddings_dir, entry)

            # New format: directory per student
            if os.path.isdir(entry_path):
                meta_path = os.path.join(entry_path, "metadata.json")
                if not os.path.exists(meta_path):
                    continue

                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)

                    student_id = meta["student_id"]
                    samples = []

                    # Load all sample images
                    for img_file in sorted(os.listdir(entry_path)):
                        if img_file.startswith("sample_") and img_file.endswith(".png"):
                            img_path = os.path.join(entry_path, img_file)
                            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                            if img is not None:
                                if img.shape != self.face_size:
                                    img = cv2.resize(img, self.face_size)
                                samples.append(img)

                    if samples:
                        self._enrolled_faces[student_id] = {
                            "name": meta["name"],
                            "class_name": meta.get("class_name", ""),
                            "samples": samples,
                            "enrolled_at": meta.get("enrolled_at", ""),
                        }
                        loaded_count += 1

                except Exception as e:
                    logger.error(f"[Attendance] Failed to load {entry}: {e}")

            # Legacy format: single JSON file
            elif entry.endswith(".json"):
                try:
                    with open(entry_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    student_id = data["student_id"]
                    
                    # BUG-05 fix: Legacy format chỉ có embedding vector, không có ảnh mặt.
                    # Tạo fake_face ngẫu nhiên sẽ làm LBPH nhận diện sai → skip thay vì tạo noise.
                    if "embedding" in data:
                        logger.warning(
                            f"[Attendance] {student_id} ({data.get('name', '')}) — "
                            f"legacy format (chỉ có embedding, không có face image). "
                            f"Yêu cầu re-enrollment qua dashboard để khôi phục nhận diện LBPH."
                        )
                        # Không thêm vào _enrolled_faces — tránh train LBPH với noise data.

                except Exception as e:
                    logger.error(f"[Attendance] Failed to load legacy {entry}: {e}")

        logger.info(f"[Attendance] Loaded {loaded_count} students from disk")

    # =============== P0-2: NAME SYNC ===============

    def _sync_student_names(self):
        """
        P0-2: Synchronize student names between LBPH metadata, ArcFace DB, and disk.
        
        Strategy: ArcFace DB is source of truth for deep-enrolled students.
        If LBPH metadata has a different name, update LBPH + disk to match.
        This prevents the "Le Van Cuong vs Dang Ngoc Trung" bug.
        """
        if not self._deep_recognizer or not hasattr(self._deep_recognizer, '_db'):
            return

        sync_count = 0
        for student_id, deep_data in self._deep_recognizer._db.items():
            if not isinstance(deep_data, dict):
                continue
            deep_name = deep_data.get("name", "")
            if not deep_name:
                continue

            # Check against LBPH enrolled faces
            if student_id in self._enrolled_faces:
                lbph_name = self._enrolled_faces[student_id].get("name", "")
                if lbph_name and lbph_name != deep_name:
                    logger.warning(
                        f"[Attendance] SYNC: {student_id} name mismatch — "
                        f"LBPH='{lbph_name}' vs ArcFace='{deep_name}' → using '{deep_name}'"
                    )
                    self._enrolled_faces[student_id]["name"] = deep_name
                    sync_count += 1

                    # Also update disk metadata.json
                    self._update_metadata_name(student_id, deep_name)

        if sync_count > 0:
            logger.info(f"[Attendance] SYNC: Fixed {sync_count} name mismatch(es)")

    def _update_metadata_name(self, student_id: str, correct_name: str):
        """Update metadata.json on disk with the correct name."""
        meta_path = os.path.join(self.embeddings_dir, student_id, "metadata.json")
        if not os.path.exists(meta_path):
            return
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if meta.get("name") != correct_name:
                old_name = meta.get("name", "")
                meta["name"] = correct_name
                meta["name_synced_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                meta["name_synced_from"] = "arcface_db"
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False, indent=2)
                logger.info(
                    f"[Attendance] SYNC: Updated disk metadata for {student_id}: "
                    f"'{old_name}' → '{correct_name}'"
                )
        except Exception as e:
            logger.warning(f"[Attendance] SYNC: Failed to update metadata for {student_id}: {e}")

    # =============== ATTENDANCE QUERIES ===============

    def update_person_count(self, total_persons: int):
        """Update current total persons detected by YOLO.
        Called each frame by ClassroomDetector.
        """
        self._current_total_persons = total_persons

    def get_attendance_summary(self) -> Dict[str, Any]:
        """Get current attendance summary.

        Returns:
            headcount: total_persons - teacher = estimated students in room
            identified: students recognized by face
            unidentified: headcount - identified
            teacher_detected: whether teacher is recognized
            teacher_name: name of recognized teacher
        """
        present = sum(1 for a in self._attendance.values() if a["status"] == "present")
        late = sum(1 for a in self._attendance.values() if a["status"] == "late")
        absent = sum(1 for a in self._attendance.values() if a["status"] == "absent")
        identified = present + late  # students recognized by face

        # Headcount = persons detected minus teacher (if detected)
        teacher_count = 1 if self._teacher_detected else 0
        headcount = max(0, self._current_total_persons - teacher_count)
        unidentified = max(0, headcount - identified)

        return {
            "total": len(self._attendance),
            "present": present,
            "late": late,
            "absent": absent,
            "identified": identified,
            "records": list(self._attendance.values()),
            # ── New headcount fields ──
            "headcount": headcount,
            "total_persons": self._current_total_persons,
            "unidentified": unidentified,
            "teacher_detected": self._teacher_detected,
            "teacher_name": self._teacher_info["name"] if self._teacher_info else None,
            "teacher_id": self._teacher_info["id"] if self._teacher_info else None,
        }

    def get_student_name(self, face_id: int) -> Optional[str]:
        """Get student name from face_id.
        
        Priority: deep recognizer DB > LBPH enrolled_faces > attendance dict.
        Deep engine name is preferred because it's more likely to be up-to-date
        (e.g., user re-enrolled with corrected name via deep_embeddings.pkl).
        """
        student_id = self._face_to_student.get(face_id)
        if not student_id:
            return None

        # 1. Prefer deep recognizer name (most accurate, may be updated)
        if self._use_deep and self._deep_recognizer:
            info = self._deep_recognizer.get_student_info(student_id)
            if info and info.get("name"):
                return info["name"]

        # 2. Fallback to LBPH enrolled faces
        if student_id in self._enrolled_faces:
            return self._enrolled_faces[student_id]["name"]

        # 3. Check attendance dict (may have been set by ArcFace match)
        if student_id in self._attendance:
            return self._attendance[student_id].get("student_name")

        return None

    def get_student_id_for_face(self, face_id: int) -> Optional[str]:
        """Get student_id from face_id."""
        return self._face_to_student.get(face_id)

    def mark_attendance_manual(self, student_id: str, status: str = "present") -> bool:
        """Manually mark attendance (teacher override)."""
        if student_id in self._attendance:
            record = self._attendance[student_id]
            record["status"] = status
            if status in ("present", "late") and not record["arrival_time"]:
                record["arrival_time"] = datetime.now().strftime("%H:%M:%S")
            record["match_score"] = 1.0  # Manual = 100% confident
            logger.info(f"[Attendance] Manual mark: {student_id} → {status}")
            return True
        return False

    def capture_frame_from_camera(self, camera_url) -> Optional[np.ndarray]:
        """Capture a single frame from camera for enrollment."""
        cap = None
        try:
            # Handle webcam index
            if isinstance(camera_url, str) and camera_url.isdigit():
                camera_url = int(camera_url)

            cap = cv2.VideoCapture(camera_url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not cap.isOpened():
                return None

            # Read a few frames to let camera stabilize
            for _ in range(5):
                cap.read()

            ret, frame = cap.read()

            if ret and frame is not None:
                return frame

        except Exception as e:
            logger.error(f"[Attendance] Camera capture error: {e}")
        finally:
            # ISSUE-07 fix: Always release camera to prevent resource leaks
            if cap is not None:
                cap.release()

        return None

    # =============== TEACHER ENROLLMENT & RECOGNITION ===============

    def enroll_teacher(
        self,
        teacher_id: str,
        name: str,
        face_crop: np.ndarray,
    ) -> bool:
        """Enroll a teacher's face. Uses the same engines as student enrollment
        but stored in _teacher_faces (separate from students).
        teacher_id should be prefixed like 'teacher_xxx' to avoid collision.
        """
        if not self._initialized:
            self.initialize()

        if face_crop is None or face_crop.size == 0:
            logger.warning(f"[Attendance] Empty face crop for teacher {teacher_id}")
            return False

        try:
            # Deep engine enrollment
            if self._deep_recognizer:
                try:
                    added = self._deep_recognizer.enroll(teacher_id, name, [face_crop])
                    if added > 0:
                        self._use_deep = True
                        logger.info(
                            f"[Attendance] Teacher enrolled in deep engine: {name} ({teacher_id})"
                        )
                except Exception as e:
                    logger.warning(f"[Attendance] Teacher deep enroll failed: {e}")

            # LBPH enrollment
            gray = self._preprocess_face(face_crop)
            if gray is not None:
                augmented = self._augment_face(gray)
                self._enrolled_faces[teacher_id] = {
                    "name": name,
                    "class_name": "__teacher__",
                    "samples": augmented,
                    "enrolled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "is_teacher": True,
                }
                self._save_samples(teacher_id, name, "__teacher__")
                self._train_recognizer()

            # Save thumbnail
            self._save_thumbnail(teacher_id, face_crop)

            # Store teacher metadata
            self._teacher_faces[teacher_id] = {
                "name": name,
                "enrolled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            logger.info(f"[Attendance] ✓ Teacher enrolled: {name} ({teacher_id})")
            return True

        except Exception as e:
            logger.error(f"[Attendance] Teacher enrollment failed: {e}", exc_info=True)
            return False

    def is_teacher(self, person_id: str) -> bool:
        """Check if a person_id is a teacher."""
        if person_id in self._teacher_faces:
            return True
        # Also check enrolled faces with __teacher__ class
        info = self._enrolled_faces.get(person_id, {})
        return info.get("is_teacher", False) or info.get("class_name") == "__teacher__"

    def check_if_teacher(self, face_id: int, student_id: str) -> bool:
        """After face recognition identifies someone, check if they are a teacher.
        If so, mark them and return True (so caller can skip student logic).
        """
        if self.is_teacher(student_id):
            self._teacher_face_ids.add(face_id)
            self._teacher_detected = True
            name = self._teacher_faces.get(student_id, {}).get("name") or \
                   self._enrolled_faces.get(student_id, {}).get("name", student_id)
            self._teacher_info = {"id": student_id, "name": name}
            return True
        return False

    def get_teacher_face_ids(self) -> set:
        """Get set of face_ids recognized as teacher (for excluding from student analysis)."""
        return self._teacher_face_ids
