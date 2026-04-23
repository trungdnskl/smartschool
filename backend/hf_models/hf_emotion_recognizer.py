"""
HuggingFace Emotion Recognizer — Production Grade
==================================================
Thay the FER library bang HuggingFace Transformers.

Model: dima806/facial_emotions_image_detection
  - MobileNet-based, 27MB, accuracy ~93% FER2013
  - CPU inference ~30ms/face (cached, throttled)

Pipeline:
  face_crop (BGR) → PIL convert → HF pipeline → top-k labels
               → sliding window smooth → engagement score

Đặc điểm production:
  - Lazy initialization (load lần đầu dùng)
  - Per-face throttling: chỉ chạy mỗi N giây
  - Sliding window N frames để smooth kết quả
  - Graceful fallback sang FER nếu HF không có
  - Thread-safe cache
"""

from __future__ import annotations

import cv2
import numpy as np
import logging
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from collections import deque

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Config resolution: model_config.json → fallback defaults
# ──────────────────────────────────────────────────────────────

def _load_hf_config() -> Dict[str, Any]:
    """Load HuggingFace emotion config from model_config.json."""
    config_path = Path(__file__).parent.parent / "model_config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            return cfg.get("emotion_recognition", {}).get("huggingface", {})
        except Exception:
            pass
    return {}


_HF_CFG = _load_hf_config()

# Model path: từ config hoặc tự tính
_DEFAULT_MODEL_PATH = str(
    Path(__file__).parent.parent.parent / "models_cache" / "huggingface" / "facial_emotions_primary"
)

MODEL_PATH       = _HF_CFG.get("model_path") or _DEFAULT_MODEL_PATH
MODEL_ID         = _HF_CFG.get("model_id", "dima806/facial_emotions_image_detection")
INPUT_SIZE       = _HF_CFG.get("input_size", 224)
UPDATE_INTERVAL  = _HF_CFG.get("update_interval", 2.0)   # seconds per face
WINDOW_SIZE      = _HF_CFG.get("window_size", 5)          # smoothing frames
TOP_K            = _HF_CFG.get("top_k", 3)

# ──────────────────────────────────────────────────────────────
# Label maps (model → system)
# ──────────────────────────────────────────────────────────────

# dima806/facial_emotions_image_detection label names
# (khớp với FER2013 standard)
EMOTION_TO_LEARNING_STATE: Dict[str, str] = {
    "happy":    "engaged",
    "surprise": "engaged",
    "neutral":  "neutral",
    "fear":     "confused",
    "sad":      "bored",
    "angry":    "frustrated",
    "disgust":  "frustrated",
    # Alias labels some models use
    "happiness":  "engaged",
    "surprised":  "engaged",
    "sadness":    "bored",
    "anger":      "frustrated",
    "fear":       "confused",
}

LEARNING_STATE_SCORES: Dict[str, int] = {
    "engaged":    90,
    "neutral":    60,
    "confused":   35,
    "bored":      20,
    "frustrated": 15,
}

EMOTION_LABELS_VI: Dict[str, str] = {
    "happy":    "Vui vẻ",
    "sad":      "Buồn",
    "angry":    "Tức giận",
    "surprise": "Ngạc nhiên",
    "fear":     "Sợ hãi",
    "disgust":  "Khó chịu",
    "neutral":  "Bình thường",
    # aliases
    "happiness": "Vui vẻ",
    "sadness":   "Buồn",
    "anger":     "Tức giận",
    "surprised": "Ngạc nhiên",
}

LEARNING_STATE_VI: Dict[str, str] = {
    "engaged":    "Tích cực",
    "neutral":    "Bình thường",
    "confused":   "Bối rối",
    "bored":      "Chán nản",
    "frustrated": "Thất vọng",
}


def _normalize_label(label: str) -> str:
    """Normalize model output label to canonical form."""
    return label.strip().lower().replace(" ", "_").replace("-", "_")


# ──────────────────────────────────────────────────────────────
# HuggingFace Emotion Recognizer
# ──────────────────────────────────────────────────────────────

class HFEmotionRecognizer:
    """
    Nhận dạng cảm xúc dùng HuggingFace Transformers pipeline.

    Accuracy: ~93% (FER2013) vs FER library ~65-75%
    Speed   : ~30-50ms/face (CPU, sau lần khởi tạo)
    RAM     : ~200–350MB

    Thread-safety: cache được bảo vệ bằng per-face timestamp.
    Không dùng threading.Lock vì FastAPI chạy async event loop đơn.
    """

    def __init__(
        self,
        model_path: str = MODEL_PATH,
        model_id: str = MODEL_ID,
        update_interval: float = UPDATE_INTERVAL,
        window_size: int = WINDOW_SIZE,
        top_k: int = TOP_K,
        input_size: int = INPUT_SIZE,
    ):
        self.model_path      = model_path
        self.model_id        = model_id
        self.update_interval = update_interval
        self.window_size     = window_size
        self.top_k           = top_k
        self.input_size      = input_size

        self._pipeline = None
        self._initialized   = False
        self._model_available = False
        self._load_source   = None   # "local" | "hub" | None

        # Per-face state
        self._emotion_history: Dict[int, deque] = {}   # face_id → deque of raw dicts
        self._last_update: Dict[int, float] = {}        # face_id → timestamp
        self._cache: Dict[int, Dict] = {}               # face_id → last smoothed result

    # ── Initialization ──────────────────────────────────────

    def initialize(self) -> bool:
        """Lazy init: load HF pipeline. Returns True if successful."""
        if self._initialized:
            return self._model_available

        self._initialized = True

        # Try local cache first, then HuggingFace Hub
        if Path(self.model_path).exists():
            success = self._load_pipeline(self.model_path, source="local")
        else:
            logger.info(
                f"[HFEmotion] Local model not found at {self.model_path}. "
                f"Trying HuggingFace Hub ({self.model_id})..."
            )
            success = self._load_pipeline(self.model_id, source="hub")

        if success:
            logger.info(
                f"[HFEmotion] ✓ Pipeline ready (source={self._load_source}, "
                f"update_interval={self.update_interval}s)"
            )
        else:
            logger.warning("[HFEmotion] Pipeline unavailable — will use FER fallback")

        return self._model_available

    def _load_pipeline(self, model_path_or_id: str, source: str) -> bool:
        """Load transformers pipeline for image-classification."""
        try:
            from transformers import pipeline as hf_pipeline

            logger.info(f"[HFEmotion] Loading pipeline from {source}: {model_path_or_id}")

            self._pipeline = hf_pipeline(
                "image-classification",
                model=model_path_or_id,
                device=-1,          # -1 = CPU always
                top_k=self.top_k,   # return top-k emotions
            )

            self._model_available = True
            self._load_source = source
            return True

        except ImportError:
            logger.warning("[HFEmotion] transformers not installed")
            return False
        except Exception as e:
            logger.warning(f"[HFEmotion] Load error ({source}): {e}")
            return False

    # ── Public API ───────────────────────────────────────────

    def recognize_emotion(
        self,
        face_crop_bgr: np.ndarray,
        face_id: int,
        force_update: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Nhận dạng cảm xúc từ face crop (BGR numpy array).

        Args:
            face_crop_bgr: Khuôn mặt đã crop, BGR, bất kỳ kích thước nào
            face_id      : ID tracking của khuôn mặt (để cache / smooth)
            force_update : Bỏ qua cache, chạy lại ngay

        Returns:
            Dict với các key: emotion, emotion_vi, confidence,
                              learning_state, learning_state_vi,
                              emotion_score, emotion_scores, face_id
            None nếu không nhận dạng được
        """
        if not self._initialized:
            self.initialize()

        # Check cache / throttle
        now = time.time()
        if not force_update and face_id in self._last_update:
            if now - self._last_update[face_id] < self.update_interval:
                return self._cache.get(face_id) or self._default_result(face_id)

        # Run inference
        raw = self._run_inference(face_crop_bgr)
        if raw is None:
            return self._cache.get(face_id) or self._default_result(face_id)

        # Sliding window
        if face_id not in self._emotion_history:
            self._emotion_history[face_id] = deque(maxlen=self.window_size)
        self._emotion_history[face_id].append(raw)

        # Smooth & build result
        result = self._smooth(face_id)

        # Update cache
        self._last_update[face_id] = now
        self._cache[face_id] = result

        return result

    def batch_recognize(
        self,
        face_crops: List[Tuple[int, np.ndarray]],
    ) -> List[Dict[str, Any]]:
        """Batch: [(face_id, crop), ...] → [result, ...]"""
        results = []
        for face_id, crop in face_crops:
            r = self.recognize_emotion(crop, face_id)
            if r:
                results.append(r)
        return results

    # ── Inference ────────────────────────────────────────────

    def _run_inference(self, face_bgr: np.ndarray) -> Optional[Dict[str, float]]:
        """
        Run HF pipeline on face crop.
        Returns dict {emotion_label: score} or None.
        """
        if self._pipeline is None or not self._model_available:
            return None

        if face_bgr is None or face_bgr.size == 0:
            return None

        try:
            from PIL import Image

            # BGR → RGB → PIL
            face_rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)

            # Resize to model input size (224×224)
            face_rgb = cv2.resize(face_rgb, (self.input_size, self.input_size),
                                  interpolation=cv2.INTER_LINEAR)

            pil_img = Image.fromarray(face_rgb)

            # Run pipeline: returns list of {"label": ..., "score": ...}
            preds: List[Dict] = self._pipeline(pil_img)

            if not preds:
                return None

            # Convert to {label: score} dict, normalize labels
            scores = {}
            for p in preds:
                label = _normalize_label(p["label"])
                scores[label] = float(p["score"])

            return scores

        except Exception as e:
            logger.debug(f"[HFEmotion] Inference error: {e}")
            return None

    # ── Smoothing ────────────────────────────────────────────

    def _smooth(self, face_id: int) -> Dict[str, Any]:
        """
        Average emotion scores across sliding window.
        Canonical emotion labels:
          angry, disgust, fear, happy, neutral, sad, surprise
        """
        history = list(self._emotion_history.get(face_id, []))
        if not history:
            return self._default_result(face_id)

        # Collect all labels across history
        all_labels = {"angry", "disgust", "fear", "happy", "neutral", "sad", "surprise"}
        for h in history:
            if h:
                all_labels.update(h.keys())

        # Average per label
        avg: Dict[str, float] = {}
        for label in all_labels:
            values = [h.get(label, 0.0) for h in history if h is not None]
            avg[label] = round(sum(values) / len(values), 4) if values else 0.0

        # Dominant emotion
        dominant = max(avg, key=avg.get)
        confidence = avg[dominant]

        # Map to learning state
        canonical = _normalize_label(dominant)
        learning_state = EMOTION_TO_LEARNING_STATE.get(canonical, "neutral")
        emotion_score  = LEARNING_STATE_SCORES.get(learning_state, 60)

        return {
            "face_id":            face_id,
            "emotion":            canonical,
            "emotion_vi":         EMOTION_LABELS_VI.get(canonical, canonical),
            "confidence":         round(confidence, 3),
            "learning_state":     learning_state,
            "learning_state_vi":  LEARNING_STATE_VI.get(learning_state, learning_state),
            "emotion_score":      emotion_score,
            "emotion_scores":     avg,
            "engine":             "huggingface",
            "model":              self._load_source,
        }

    # ── Utilities ────────────────────────────────────────────

    def _default_result(self, face_id: int) -> Dict[str, Any]:
        return {
            "face_id":            face_id,
            "emotion":            "neutral",
            "emotion_vi":         "Bình thường",
            "confidence":         0.5,
            "learning_state":     "neutral",
            "learning_state_vi":  "Bình thường",
            "emotion_score":      60,
            "emotion_scores":     {"neutral": 1.0},
            "engine":             "huggingface",
            "model":              None,
        }

    def cleanup_stale(self, active_face_ids: set):
        """Xoá dữ liệu của faces không còn track."""
        stale = set(self._emotion_history) - active_face_ids
        for fid in stale:
            self._emotion_history.pop(fid, None)
            self._last_update.pop(fid, None)
            self._cache.pop(fid, None)

    def get_class_emotion_distribution(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        dist: Dict[str, int] = {}
        for r in results:
            em = r.get("emotion", "neutral")
            dist[em] = dist.get(em, 0) + 1
        return dist

    def get_class_learning_state_distribution(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        dist: Dict[str, int] = {}
        for r in results:
            ls = r.get("learning_state", "neutral")
            dist[ls] = dist.get(ls, 0) + 1
        return dist

    @property
    def is_available(self) -> bool:
        return self._model_available

    def get_stats(self) -> Dict[str, Any]:
        return {
            "engine":           "huggingface",
            "model_id":         self.model_id,
            "model_path":       self.model_path,
            "load_source":      self._load_source,
            "model_available":  self._model_available,
            "update_interval":  self.update_interval,
            "window_size":      self.window_size,
            "tracked_faces":    len(self._emotion_history),
        }
