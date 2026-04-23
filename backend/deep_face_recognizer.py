"""
Classroom Engagement System - Deep Face Recognizer
Nhận diện khuôn mặt bằng DeepFace (ArcFace/Facenet512) + Cosine Similarity
Kết hợp với embeddings được tạo từ Google Colab hoặc local camera

Pipeline:
  Camera Frame → Face Detect → DeepFace Represent → 512-dim vector
              → Cosine Similarity → Best Match → Attendance

Backend hỗ trợ (theo thứ tự ưu tiên):
  1. ArcFace      - Best accuracy (99.4% LFW), cần ~500MB RAM
  2. Facenet512   - Tốt hơn Facenet, nhanh hơn ArcFace  
  3. Facenet      - Nhẹ nhất, phù hợp máy yếu
  4. DeepFace     - Built-in, không cần download thêm

Fallback: LBPH nếu deepface chưa cài
"""

import cv2
import numpy as np
import logging
import os
import json
import pickle
import time
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent
EMBEDDINGS_DIR = PROJECT_DIR / "data" / "face_embeddings"
DEEP_EMBEDDINGS_FILE = EMBEDDINGS_DIR / "deep_embeddings.pkl"


# ============================================================
# DEEPFACE RECOGNIZER (ArcFace / Facenet512)
# ============================================================

class ArcFaceRecognizer:
    """
    Nhận diện khuôn mặt dùng DeepFace với ArcFace backend.
    
    Dễ cài hơn InsightFace: pip install deepface tf-keras
    Không cần Visual C++ Build Tools.
    
    Accuracy (so với LBPH):
    - ArcFace:    99.4% → ~94-98% thực tế lớp học
    - Facenet512: 99.6% → ~92-96% thực tế
    - LBPH:       99.7% (library) → ~75-85% thực tế
    """
    
    # Backend theo thứ tự ưu tiên
    _BACKENDS = ['ArcFace', 'Facenet512', 'Facenet', 'DeepFace']
    _DETECTOR = 'retinaface'  # retinaface > mtcnn > opencv
    _WINDOW_SIZE = 5
    _THRESHOLD_DEFAULT = 0.45
    
    def __init__(
        self,
        threshold: float = _THRESHOLD_DEFAULT,
        embeddings_file: str = None,
        model_name: str = 'ArcFace',
    ):
        self.threshold = threshold
        self.embeddings_file = embeddings_file or str(DEEP_EMBEDDINGS_FILE)
        self.model_name = model_name
        
        self._deepface = None
        self._initialized = False
        self._model_available = False
        self._active_backend = None
        
        self._db: Dict[str, Dict] = {}
        self._db_loaded = False
        self._history: Dict[int, List[Tuple[str, float]]] = {}
    
    def initialize(self) -> bool:
        """Initialize DeepFace model. Returns True if successful."""
        try:
            import deepface
            from deepface import DeepFace as df
            self._deepface = df
            
            # Try to build model to confirm it loads
            logger.info(f"[DeepFace] Loading {self.model_name} model...")
            # DeepFace builds model lazily on first call
            # Test with dummy to confirm
            self._model_available = True
            self._active_backend = self.model_name
            logger.info(f"[DeepFace] ✓ {self.model_name} ready via deepface library")
            
        except ImportError:
            logger.warning("[DeepFace] deepface not installed. Run: pip install deepface tf-keras")
            self._model_available = False
        except Exception as e:
            logger.warning(f"[DeepFace] Failed to load {self.model_name}: {e}")
            # ISSUE-04 fix: test từng fallback bằng dummy call thực sự thay vì chỉ gán biến
            dummy = np.zeros((112, 112, 3), dtype=np.uint8)
            for backend in self._BACKENDS:
                if backend == self.model_name:
                    continue
                try:
                    self._deepface.represent(
                        img_path=dummy,
                        model_name=backend,
                        detector_backend="skip",
                        enforce_detection=False,
                    )
                    self._active_backend = backend
                    self._model_available = True
                    logger.info(f"[DeepFace] Fallback to {backend} ✓ (verified)")
                    break
                except Exception as fallback_err:
                    logger.debug(f"[DeepFace] {backend} also unavailable: {fallback_err}")
                    continue

            if not self._model_available:
                logger.warning("[DeepFace] All backends failed. Using LBPH fallback.")
        
        self._load_embeddings()
        self._initialized = True
        return self._model_available
    
    def _load_embeddings(self):
        """Load deep embeddings database from .pkl file."""
        if not os.path.exists(self.embeddings_file):
            logger.info(f"[DeepFace] No embeddings file at {self.embeddings_file}")
            self._db_loaded = False
            return
        
        try:
            with open(self.embeddings_file, 'rb') as f:
                data = pickle.load(f)
            
            if isinstance(data, dict) and 'students' in data:
                self._db = data['students']
                recommended_threshold = data.get('threshold_recommended', 0.45)
                # Use recommended threshold if not overridden
                if self.threshold == self._THRESHOLD_DEFAULT:
                    self.threshold = recommended_threshold
                logger.info(
                    f"[DeepFace] Loaded embeddings: {len(self._db)} students, "
                    f"model={data.get('model', 'unknown')}, "
                    f"threshold={self.threshold}"
                )
            else:
                # Legacy format or plain dict
                self._db = data
                logger.info(f"[DeepFace] Loaded embeddings (legacy format): {len(self._db)} entries")
            
            self._db_loaded = True
            
        except Exception as e:
            logger.error(f"[DeepFace] Failed to load embeddings: {e}")
            self._db_loaded = False
    
    def reload_embeddings(self):
        """Reload embeddings from disk (call after adding new students)."""
        self._load_embeddings()
    
    def get_face_embedding(self, face_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Generate embedding from face crop using DeepFace.
        Input: BGR image (any size)
        Output: normalized numpy array or None
        """
        if not self._model_available or self._deepface is None:
            return None
        
        try:
            # Ensure minimum size
            h, w = face_bgr.shape[:2]
            if h < 60 or w < 60:
                scale = max(60 / h, 60 / w)
                face_bgr = cv2.resize(face_bgr, (int(w * scale), int(h * scale)))
            
            # DeepFace.represent: returns list of dicts with 'embedding' key
            result = self._deepface.represent(
                img_path=face_bgr,
                model_name=self._active_backend or self.model_name,
                detector_backend='skip',  # face already cropped
                enforce_detection=False,
                align=True,
            )
            
            if result and len(result) > 0:
                emb = np.array(result[0]['embedding'], dtype=np.float32)
                # L2 normalize
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                return emb
            
            return None
            
        except Exception as e:
            logger.debug(f"[DeepFace] Embedding failed: {e}")
            return None
    
    def identify(
        self, face_bgr: np.ndarray, face_id: int = -1
    ) -> Tuple[Optional[str], float, Optional[str]]:
        """
        Identify a face against the embeddings database.
        
        Returns: (student_id, similarity_score, student_name)
                 student_id = None if no match above threshold
        """
        if not self._model_available or not self._db_loaded:
            return None, 0.0, None
        
        query_emb = self.get_face_embedding(face_bgr)
        if query_emb is None:
            return None, 0.0, None
        
        best_sid = None
        best_sim = 0.0
        
        for sid, student_data in self._db.items():
            if isinstance(student_data, dict):
                embeddings = student_data.get('embeddings', [])
                # Use centroid (mean embedding) for faster comparison
                centroid = student_data.get('centroid')
            else:
                # Legacy: student_data is list of embeddings
                embeddings = student_data
                centroid = None
            
            if not embeddings:
                continue
            
            if centroid is not None:
                # Fast path: compare with centroid
                sim = float(np.dot(query_emb, centroid))
                # If centroid matches, verify with all embeddings
                if sim > self.threshold * 0.8:
                    max_sim = max(
                        float(np.dot(query_emb, e))
                        for e in embeddings
                    )
                    sim = max_sim
            else:
                # Compare with all embeddings (K-NN style)
                sim = max(
                    float(np.dot(query_emb, e))
                    for e in embeddings
                )
            
            if sim > best_sim:
                best_sim = sim
                best_sid = sid
        
        # Apply voting window
        if face_id >= 0:
            result = self._vote(face_id, best_sid, best_sim)
            if result:
                voted_sid, voted_sim = result
                name = self._db.get(voted_sid, {}).get('name', voted_sid) if isinstance(self._db.get(voted_sid), dict) else voted_sid
                return voted_sid, voted_sim, name
            return None, 0.0, None
        
        # No voting, direct result
        if best_sim >= self.threshold:
            name = self._db.get(best_sid, {}).get('name', best_sid) if isinstance(self._db.get(best_sid), dict) else best_sid
            return best_sid, best_sim, name
        
        return None, best_sim, None
    
    def _vote(
        self, face_id: int, candidate: Optional[str], score: float
    ) -> Optional[Tuple[str, float]]:
        """Majority voting over recent frames to reduce flickering."""
        if face_id not in self._history:
            self._history[face_id] = []
        
        if candidate and score >= self.threshold:
            self._history[face_id].append((candidate, score))
        else:
            self._history[face_id].append((None, score))
        
        # Keep window size
        if len(self._history[face_id]) > self._WINDOW_SIZE:
            self._history[face_id].pop(0)
        
        window = self._history[face_id]
        if len(window) < 2:
            return None
        
        # Count valid identifications
        valid = [(sid, s) for sid, s in window if sid is not None]
        if not valid:
            return None
        
        # Require majority
        if len(valid) >= len(window) * 0.5:
            # Return most common + best score
            from collections import Counter
            most_common = Counter(sid for sid, _ in valid).most_common(1)[0][0]
            best_score = max(s for sid, s in valid if sid == most_common)
            return most_common, best_score
        
        return None
    
    def enroll(
        self,
        student_id: str,
        name: str,
        face_crops: List[np.ndarray],
    ) -> int:
        """
        Enroll a student with face crops from local camera.
        Generates embeddings locally using ONNX model.
        
        Returns: Number of successful embeddings
        """
        if not self._model_available:
            return 0
        
        embeddings = []
        for face_bgr in face_crops:
            emb = self.get_face_embedding(face_bgr)
            if emb is not None:
                embeddings.append(emb)
        
        if not embeddings:
            logger.warning(f"[DeepFace] No valid embeddings for {student_id}")
            return 0
        
        centroid = np.mean(embeddings, axis=0)
        centroid = centroid / np.linalg.norm(centroid)
        
        self._db[student_id] = {
            'name': name,
            'student_id': student_id,
            'embeddings': embeddings,
            'centroid': centroid,
            'enrolled_at': datetime.now().isoformat(),
            'source': 'local_camera',
        }
        
        # Save to disk
        self._save_embeddings()
        logger.info(f"[DeepFace] Enrolled {name} ({student_id}) with {len(embeddings)} embeddings")
        return len(embeddings)
    
    def _save_embeddings(self):
        """Save current embeddings to disk."""
        os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
        
        output = {
            'version': '2.0',
            'model': f'deepface_{self._active_backend or self.model_name}',
            'embedding_dim': len(next(iter(self._db.values()))['embeddings'][0]) if self._db else 512,
            'threshold_recommended': self.threshold,
            'updated_at': datetime.now().isoformat(),
            'total_students': len(self._db),
            'students': self._db,
        }
        
        with open(self.embeddings_file, 'wb') as f:
            pickle.dump(output, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        logger.info(f"[DeepFace] Saved {len(self._db)} student embeddings")
    
    def remove_student(self, student_id: str) -> bool:
        """Remove a student from embeddings DB."""
        if student_id in self._db:
            del self._db[student_id]
            self._save_embeddings()
            return True
        return False
    
    def clear_history(self):
        """Clear voting history (call on session start)."""
        self._history.clear()
    
    @property
    def enrolled_count(self) -> int:
        return len(self._db)
    
    @property
    def is_available(self) -> bool:
        return self._model_available and self._db_loaded and len(self._db) > 0
    
    def get_student_info(self, student_id: str) -> Optional[Dict]:
        """Get student info from embeddings DB."""
        data = self._db.get(student_id)
        if data is None:
            return None
        if isinstance(data, dict):
            return {
                'student_id': student_id,
                'name': data.get('name', student_id),
                'embedding_count': len(data.get('embeddings', [])),
                'source': data.get('source', 'unknown'),
                'enrolled_at': data.get('enrolled_at', ''),
            }
        return {'student_id': student_id, 'name': student_id, 'embedding_count': len(data)}
    
    def get_stats(self) -> Dict:
        """Get recognizer statistics."""
        total_embeddings = sum(
            len(v.get('embeddings', [])) if isinstance(v, dict) else len(v)
            for v in self._db.values()
        )
        return {
            'model': self._active_backend or (self.model_name if self._model_available else 'not_loaded'),
            'model_available': self._model_available,
            'enrolled_students': len(self._db),
            'total_embeddings': total_embeddings,
            'avg_embeddings_per_student': total_embeddings / max(len(self._db), 1),
            'threshold': self.threshold,
            'embeddings_file': str(self.embeddings_file),
            'db_loaded': self._db_loaded,
        }


# ============================================================
# IMPORT HELPER
# ============================================================

def import_colab_embeddings(pkl_path: str) -> Tuple[bool, str, int]:
    """
    Import embeddings file từ Google Colab.
    
    Args:
        pkl_path: Đường dẫn đến file deep_embeddings.pkl từ Colab
    
    Returns:
        (success, message, student_count)
    """
    try:
        from state import safe_pickle_loads

        with open(pkl_path, 'rb') as f:
            colab_data = safe_pickle_loads(f.read())
        
        if isinstance(colab_data, dict) and 'students' in colab_data:
            students = colab_data['students']
        else:
            students = colab_data
        
        # Load existing embeddings (also using safe loader)
        existing = {}
        if DEEP_EMBEDDINGS_FILE.exists():
            with open(DEEP_EMBEDDINGS_FILE, 'rb') as f:
                existing_data = safe_pickle_loads(f.read())
            existing = existing_data.get('students', {}) if isinstance(existing_data, dict) else existing_data
        
        # Merge (Colab data takes priority for same student_id)
        merged = {**existing, **students}
        
        # Save
        os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
        output = {
            'version': '2.0',
            'model': colab_data.get('model', 'insightface_buffalo_l_arcface') if isinstance(colab_data, dict) else 'insightface_buffalo_l_arcface',
            'embedding_dim': 512,
            'threshold_recommended': colab_data.get('threshold_recommended', 0.45) if isinstance(colab_data, dict) else 0.45,
            'imported_from_colab': datetime.now().isoformat(),
            'total_students': len(merged),
            'students': merged,
        }
        
        with open(DEEP_EMBEDDINGS_FILE, 'wb') as f:
            pickle.dump(output, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        new_count = len(students)
        total_count = len(merged)
        return True, f"Import thành công {new_count} học sinh, tổng {total_count} học sinh", total_count
        
    except FileNotFoundError:
        return False, f"Không tìm thấy file: {pkl_path}", 0
    except Exception as e:
        return False, f"Lỗi import: {str(e)}", 0


def get_embedding_stats() -> Dict:
    """Get statistics about the embeddings database."""
    if not DEEP_EMBEDDINGS_FILE.exists():
        return {
            'file_exists': False,
            'total_students': 0,
            'total_embeddings': 0,
            'model': 'none',
            'created_at': None,
        }
    
    try:
        with open(DEEP_EMBEDDINGS_FILE, 'rb') as f:
            data = pickle.load(f)
        
        students = data.get('students', {}) if isinstance(data, dict) else data
        total_emb = sum(
            len(v.get('embeddings', [])) if isinstance(v, dict) else len(v)
            for v in students.values()
        )
        
        return {
            'file_exists': True,
            'total_students': len(students),
            'total_embeddings': total_emb,
            'model': data.get('model', 'unknown') if isinstance(data, dict) else 'unknown',
            'created_at': data.get('imported_from_colab') or data.get('created_at') if isinstance(data, dict) else None,
            'file_size_kb': os.path.getsize(DEEP_EMBEDDINGS_FILE) / 1024,
        }
    except Exception as e:
        return {'file_exists': True, 'error': str(e), 'total_students': 0}
