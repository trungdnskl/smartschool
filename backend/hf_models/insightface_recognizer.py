"""
InsightFace ArcFace Recognizer - ONNX Runtime Direct
=====================================================
Thay the insightface library bang direct ONNX Runtime inference.
Khong can Visual C++ Build Tools tren Windows.

Model: buffalo_l (ArcFace R100) - tai tu insightface CDN duoi dang ONNX
  - det_10g.onnx     : Face detection (RetinaFace)
  - w600k_r50.onnx   : Face recognition (ArcFace R50)

Pipeline:
  face_crop (BGR) -> ONNX detection -> align -> ONNX recognition
             -> 512-dim embedding -> cosine similarity

Dai the insightface_recognizer.py cac tinh nang chinh:
  - Compatible interface voi ArcFaceRecognizer trong deep_face_recognizer.py
  - Majority voting window
  - Embeddings DB tuong thich
  - Graceful fallback
"""

from __future__ import annotations

import cv2
import numpy as np
import logging
import os
import pickle
import time
import json
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from collections import Counter, deque

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
def _load_config() -> Dict[str, Any]:
    config_path = Path(__file__).parent.parent.parent / "model_config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            return cfg.get("face_recognition", {}).get("insightface", {})
        except Exception:
            pass
    return {}


_CFG = _load_config()
THRESHOLD   = float(_CFG.get("threshold", 0.35))
VOTE_WINDOW = 3

# Model cache directory
MODELS_CACHE = Path(__file__).parent.parent.parent / "models_cache" / "insightface"
MODELS_CACHE.mkdir(parents=True, exist_ok=True)

# Embeddings database (same pkl format as deep_face_recognizer.py)
EMBEDDINGS_DIR  = Path(__file__).parent.parent.parent / "data" / "face_embeddings"
EMBEDDINGS_FILE = EMBEDDINGS_DIR / "deep_embeddings.pkl"

# buffalo_l ONNX model URLs from insightface project
ONNX_MODELS = {
    "det_10g": {
        "url": "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
        "filename": "det_10g.onnx",
        "description": "RetinaFace face detection",
    },
    "w600k_r50": {
        "filename": "w600k_r50.onnx",
        "description": "ArcFace R50 recognition (512-dim)",
    },
}

# Alternative: use directly downloadable ONNX files
ONNX_DET_URL  = "https://huggingface.co/datasets/MattyAB/insightface-buffalo-l/resolve/main/det_10g.onnx"
ONNX_REC_URL  = "https://huggingface.co/datasets/MattyAB/insightface-buffalo-l/resolve/main/w600k_r50.onnx"


# ------------------------------------------------------------------
# ONNX Model Manager
# ------------------------------------------------------------------

class _ONNXInferenceSession:
    """Thin wrapper around onnxruntime.InferenceSession."""

    def __init__(self, model_path: str):
        import onnxruntime as ort
        providers = ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_names  = [inp.name for inp in self.session.get_inputs()]
        self.output_names = [out.name for out in self.session.get_outputs()]

    def run(self, *inputs) -> List[np.ndarray]:
        feed = {name: inp for name, inp in zip(self.input_names, inputs)}
        return self.session.run(None, feed)


def _download_onnx_model(url: str, dest: Path, name: str) -> bool:
    """Download an ONNX model file from URL."""
    if dest.exists():
        return True
    logger.info(f"[InsightFace] Downloading {name} from {url}...")
    try:
        urllib.request.urlretrieve(url, str(dest))
        logger.info(f"[InsightFace] Downloaded {name} ({dest.stat().st_size/1e6:.1f} MB)")
        return True
    except Exception as e:
        logger.warning(f"[InsightFace] Download failed for {name}: {e}")
        return False


# ------------------------------------------------------------------
# Face Alignment (ArcFace standard 112x112)
# ------------------------------------------------------------------

ARCFACE_DST = np.array([
    [38.2946, 51.6963],
    [73.5318, 51.5014],
    [56.0252, 71.7366],
    [41.5493, 92.3655],
    [70.7299, 92.2041],
], dtype=np.float32)


def _align_face(img_bgr: np.ndarray, landmark: np.ndarray) -> np.ndarray:
    """Align face to ArcFace standard 112x112 using 5-point landmark."""
    from skimage import transform as trans
    tform = trans.SimilarityTransform()
    tform.estimate(landmark, ARCFACE_DST)
    M = tform.params[0:2, :]
    aligned = cv2.warpAffine(img_bgr, M, (112, 112), borderValue=0.0)
    return aligned


def _align_face_simple(img_bgr: np.ndarray) -> np.ndarray:
    """Simple resize to 112x112 without landmark alignment (fallback)."""
    return cv2.resize(img_bgr, (112, 112), interpolation=cv2.INTER_LINEAR)


# ------------------------------------------------------------------
# InsightFace ONNX Direct Recognizer
# ------------------------------------------------------------------

class InsightFaceRecognizer:
    """
    Nhan dien khuon mat dung ArcFace R50 ONNX (khong can insightface library).

    Chay tren Windows khong can Visual C++ Build Tools.
    Chi can: onnxruntime (da cai)

    Interface tuong thich voi ArcFaceRecognizer trong deep_face_recognizer.py.
    """

    def __init__(
        self,
        threshold: float = THRESHOLD,
        embeddings_file: str = None,
        model_dir: str = None,
    ):
        self.threshold       = threshold
        self.embeddings_file = embeddings_file or str(EMBEDDINGS_FILE)
        self.model_dir       = Path(model_dir or MODELS_CACHE)

        self._det_session    = None   # Detection ONNX session
        self._rec_session    = None   # Recognition ONNX session

        self._initialized    = False
        self._model_available = False
        self._has_detection  = False   # if det model available
        self._has_skimage    = False   # for face alignment

        # Embeddings DB
        self._db: Dict[str, Dict] = {}
        self._db_loaded = False

        # Voting window
        self._history: Dict[int, deque] = {}

    # -- Initialization ---------------------------------------------------

    def initialize(self) -> bool:
        """Initialize ONNX models. Returns True if recognition model loaded."""
        if self._initialized:
            return self._model_available
        self._initialized = True

        # Check skimage for face alignment
        try:
            from skimage import transform  # noqa
            self._has_skimage = True
        except ImportError:
            logger.info("[InsightFace] skimage not available — using simple resize (slight accuracy drop)")

        # Try to load recognition model (required)
        rec_path = self.model_dir / "w600k_r50.onnx"
        if not rec_path.exists():
            ok = _download_onnx_model(ONNX_REC_URL, rec_path, "w600k_r50.onnx")
            if not ok:
                logger.warning("[InsightFace] Cannot download recognition model — fallback to DeepFace")
                self._model_available = False
                self._load_embeddings()
                return False

        try:
            self._rec_session = _ONNXInferenceSession(str(rec_path))
            self._model_available = True
            logger.info("[InsightFace] ArcFace R50 ONNX loaded (direct ONNX, no C++ required)")
        except Exception as e:
            logger.warning(f"[InsightFace] Failed to load recognition model: {e}")
            self._model_available = False
            self._load_embeddings()
            return False

        # Try to load detection model (optional — improves accuracy with alignment)
        det_path = self.model_dir / "det_10g.onnx"
        if not det_path.exists():
            ok = _download_onnx_model(ONNX_DET_URL, det_path, "det_10g.onnx")
        if det_path.exists():
            try:
                self._det_session = _ONNXInferenceSession(str(det_path))
                self._has_detection = True
                logger.info("[InsightFace] RetinaFace detection ONNX loaded")
            except Exception as e:
                logger.info(f"[InsightFace] Detection model skipped: {e} (using OpenCV DNN)")

        self._load_embeddings()
        return True

    # -- Embeddings DB ----------------------------------------------------

    def _load_embeddings(self):
        """Load embeddings pkl — same format as deep_face_recognizer.py."""
        if not Path(self.embeddings_file).exists():
            logger.info(f"[InsightFace] No embeddings at {self.embeddings_file}")
            self._db_loaded = False
            return
        try:
            with open(self.embeddings_file, "rb") as f:
                data = pickle.load(f)
            if isinstance(data, dict) and "students" in data:
                self._db = data["students"]
                rec = data.get("threshold_recommended", THRESHOLD)
                if self.threshold == THRESHOLD:
                    self.threshold = rec
            else:
                self._db = data
            logger.info(f"[InsightFace] Loaded {len(self._db)} students")
            self._db_loaded = True
        except Exception as e:
            logger.error(f"[InsightFace] Load embeddings failed: {e}")
            self._db_loaded = False

    def reload_embeddings(self):
        self._load_embeddings()

    def _save_embeddings(self):
        EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "version":               "2.0",
            "model":                 "insightface_onnx_arcface_r50",
            "embedding_dim":         512,
            "threshold_recommended": self.threshold,
            "updated_at":            datetime.now().isoformat(),
            "total_students":        len(self._db),
            "students":              self._db,
        }
        with open(self.embeddings_file, "wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info(f"[InsightFace] Saved {len(self._db)} students")

    # -- Embedding extraction ---------------------------------------------

    def get_face_embedding(self, face_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Generate 512-dim ArcFace embedding from face crop (BGR).
        Input : any size BGR numpy array
        Output: L2-normalized float32 array or None

        ISSUE-03 fix: Uses landmark-based alignment when detection model
        is available (improves accuracy ~3-5%). Falls back to simple resize.
        """
        if not self._model_available or self._rec_session is None:
            return None
        if face_bgr is None or face_bgr.size == 0:
            return None

        try:
            # Try landmark-based alignment for better accuracy
            face_112 = self._get_aligned_face(face_bgr)

            # BGR -> RGB, normalize to [-1, 1]
            face_rgb = cv2.cvtColor(face_112, cv2.COLOR_BGR2RGB).astype(np.float32)
            face_rgb = (face_rgb - 127.5) / 127.5

            # NCHW format
            inp = np.expand_dims(face_rgb.transpose(2, 0, 1), axis=0)

            # ONNX inference
            outputs = self._rec_session.run(inp)
            emb = np.array(outputs[0][0], dtype=np.float32)

            # L2 normalize
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            return emb

        except Exception as e:
            logger.debug(f"[InsightFace] Embedding error: {e}")
            return None

    def _get_aligned_face(self, face_bgr: np.ndarray) -> np.ndarray:
        """
        Align face using 5-point landmarks from detection model.
        Falls back to simple resize if detection model or skimage unavailable.
        """
        if self._has_detection and self._det_session and self._has_skimage:
            try:
                landmarks = self._detect_landmarks(face_bgr)
                if landmarks is not None:
                    return _align_face(face_bgr, landmarks)
            except Exception as e:
                logger.debug(f"[InsightFace] Landmark alignment failed, using resize: {e}")

        return _align_face_simple(face_bgr)

    def _detect_landmarks(self, face_bgr: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect 5-point facial landmarks using RetinaFace det_10g ONNX model.
        Returns 5x2 landmark array or None if detection fails.
        """
        if self._det_session is None:
            return None

        try:
            h, w = face_bgr.shape[:2]
            # Prepare input for det_10g: resize to standard detection size
            det_size = 640
            scale = min(det_size / h, det_size / w)
            new_h, new_w = int(h * scale), int(w * scale)
            resized = cv2.resize(face_bgr, (new_w, new_h))

            # Pad to det_size x det_size
            padded = np.zeros((det_size, det_size, 3), dtype=np.uint8)
            padded[:new_h, :new_w, :] = resized

            # Normalize and transpose to NCHW
            inp = padded.astype(np.float32)
            inp = (inp - 127.5) / 128.0
            inp = np.expand_dims(inp.transpose(2, 0, 1), axis=0)

            outputs = self._det_session.run(inp)

            # det_10g outputs: [scores, bboxes, landmarks]
            # landmarks shape: (N, 10) -> reshape to (N, 5, 2)
            if len(outputs) >= 3:
                scores = outputs[0]
                landmarks_raw = outputs[2]

                if scores.size > 0:
                    # Find best detection
                    best_idx = np.argmax(scores.flatten())
                    if scores.flatten()[best_idx] > 0.5:
                        lm = landmarks_raw.reshape(-1, 5, 2)[best_idx]
                        # Scale landmarks back to original face crop coordinates
                        lm[:, 0] = lm[:, 0] / scale
                        lm[:, 1] = lm[:, 1] / scale
                        return lm.astype(np.float32)

        except Exception as e:
            logger.debug(f"[InsightFace] Landmark detection error: {e}")

        return None

    # -- Identification ---------------------------------------------------

    def identify(
        self,
        face_bgr: np.ndarray,
        face_id: int = -1,
    ) -> Tuple[Optional[str], float, Optional[str]]:
        """
        Identify face against DB.
        Returns: (student_id, similarity, student_name) or (None, 0.0, None)
        """
        if not self._model_available or not self._db_loaded:
            logger.debug(f"[InsightFace] identify skip: model={self._model_available}, db={self._db_loaded}, db_size={len(self._db)}")
            # Try with just model + db size
            if not self._model_available or len(self._db) == 0:
                return None, 0.0, None

        query = self.get_face_embedding(face_bgr)
        if query is None:
            logger.debug("[InsightFace] identify: embedding extraction failed")
            return None, 0.0, None

        best_sid, best_sim = None, -1.0

        for sid, data in self._db.items():
            embeddings = data.get("embeddings", []) if isinstance(data, dict) else data
            centroid   = data.get("centroid") if isinstance(data, dict) else None

            if not embeddings:
                continue

            if centroid is not None:
                sim_c = float(np.dot(query, centroid))
                sim = max(float(np.dot(query, e)) for e in embeddings) \
                      if sim_c > self.threshold * 0.8 else sim_c
            else:
                sim = max(float(np.dot(query, e)) for e in embeddings)

            if sim > best_sim:
                best_sim, best_sid = sim, sid

        # Log every attempt for debugging
        if best_sid:
            name = self._get_name(best_sid)
            status = "MATCH" if best_sim >= self.threshold else "BELOW_THRESHOLD"
            logger.debug(f"[InsightFace] {status}: {name} ({best_sid}) sim={best_sim:.3f} threshold={self.threshold}")

        if best_sim < self.threshold:
            best_sid = None

        # Majority voting
        if face_id >= 0:
            voted = self._vote(face_id, best_sid, best_sim)
            if voted:
                vsid, vsim = voted
                return vsid, vsim, self._get_name(vsid)
            return None, 0.0, None

        # No voting
        if best_sid:
            return best_sid, best_sim, self._get_name(best_sid)
        return None, best_sim, None

    def _get_name(self, sid: str) -> Optional[str]:
        d = self._db.get(sid)
        return d.get("name", sid) if isinstance(d, dict) else sid

    def _vote(
        self, face_id: int, candidate: Optional[str], score: float
    ) -> Optional[Tuple[str, float]]:
        if face_id not in self._history:
            self._history[face_id] = deque(maxlen=VOTE_WINDOW)
        entry = (candidate, score) if (candidate and score >= self.threshold) else (None, score)
        self._history[face_id].append(entry)
        window = list(self._history[face_id])
        # Only need 1 valid vote to start recognizing (was 50%)
        valid = [(s, sc) for s, sc in window if s is not None]
        if not valid:
            return None
        top = Counter(s for s, _ in valid).most_common(1)[0][0]
        best = max(sc for s, sc in valid if s == top)
        return top, best

    # -- Enrollment -------------------------------------------------------

    def enroll(
        self, student_id: str, name: str, face_crops: List[np.ndarray]
    ) -> int:
        """Enroll student from local face crops."""
        if not self._model_available:
            return 0
        embeddings = [e for e in (self.get_face_embedding(c) for c in face_crops) if e is not None]
        if not embeddings:
            return 0

        if student_id in self._db and isinstance(self._db[student_id], dict):
            # Append to existing embeddings
            existing = self._db[student_id].get("embeddings", [])
            existing.extend(embeddings)
            # Recalculate centroid with all embeddings
            all_embs = existing
            centroid = np.mean(all_embs, axis=0)
            centroid /= np.linalg.norm(centroid)
            self._db[student_id]["embeddings"] = all_embs
            self._db[student_id]["centroid"] = centroid
            self._db[student_id]["name"] = name  # update name if changed
            logger.info(f"[InsightFace] Added {len(embeddings)} embeddings for {name} (total: {len(all_embs)})")
        else:
            # New enrollment
            centroid = np.mean(embeddings, axis=0)
            centroid /= np.linalg.norm(centroid)
            self._db[student_id] = {
                "name": name, "student_id": student_id,
                "embeddings": embeddings, "centroid": centroid,
                "enrolled_at": datetime.now().isoformat(),
                "source": "insightface_onnx_direct",
            }
            logger.info(f"[InsightFace] Enrolled {name} ({student_id}), {len(embeddings)} embeddings")

        # CRITICAL: mark DB as loaded so is_available returns True
        self._db_loaded = True
        self._save_embeddings()
        return len(embeddings)

    def remove_student(self, student_id: str) -> bool:
        if student_id in self._db:
            del self._db[student_id]
            self._save_embeddings()
            return True
        return False

    def clear_history(self):
        self._history.clear()

    @property
    def enrolled_count(self) -> int:
        return len(self._db)

    @property
    def is_available(self) -> bool:
        return self._model_available and len(self._db) > 0

    def get_student_info(self, student_id: str) -> Optional[Dict]:
        d = self._db.get(student_id)
        if d is None:
            return None
        if isinstance(d, dict):
            return {
                "student_id": student_id,
                "name": d.get("name", student_id),
                "embedding_count": len(d.get("embeddings", [])),
                "source": d.get("source", "unknown"),
                "enrolled_at": d.get("enrolled_at", ""),
            }
        return {"student_id": student_id, "name": student_id, "embedding_count": len(d)}

    def get_stats(self) -> Dict[str, Any]:
        total = sum(
            len(v.get("embeddings", [])) if isinstance(v, dict) else len(v)
            for v in self._db.values()
        )
        return {
            "engine":            "insightface_onnx_direct",
            "model":             "ArcFace_R50_ONNX",
            "model_available":   self._model_available,
            "has_detection":     self._has_detection,
            "enrolled_students": len(self._db),
            "total_embeddings":  total,
            "avg_embeddings":    total / max(len(self._db), 1),
            "threshold":         self.threshold,
            "embeddings_file":   self.embeddings_file,
            "db_loaded":         self._db_loaded,
            "providers":         ["CPUExecutionProvider"],
        }
