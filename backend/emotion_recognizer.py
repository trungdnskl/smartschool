"""
Classroom Engagement System - Emotion Recognizer (v2)
=====================================================
Engine priority:
  1. HuggingFace Transformers (dima806/facial_emotions_image_detection)
     - Accuracy ~93%, MobileNet-based, 27MB, ~30-50ms/face CPU
  2. FER library (fallback)
     - Accuracy ~65-75%, nhẹ hơn, cài đơn giản hơn
  3. Rule-based heuristic (last resort)

Giao diện public giữ nguyên để không phá vỡ các module khác.
"""

import cv2
import numpy as np
import logging
import time
from typing import Optional, Dict, Any, List, Tuple
from collections import deque

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Constant maps (shared across engines)
# ──────────────────────────────────────────────────────────────

EMOTION_TO_LEARNING_STATE = {
    "happy":    "engaged",
    "surprise": "engaged",
    "neutral":  "neutral",
    "fear":     "confused",
    "sad":      "bored",
    "angry":    "frustrated",
    "disgust":  "frustrated",
}

LEARNING_STATE_SCORES = {
    "engaged":    90,
    "neutral":    60,
    "confused":   35,
    "bored":      20,
    "frustrated": 15,
}

EMOTION_NAMES_VI = {
    "happy":    "Vui vẻ",
    "sad":      "Buồn",
    "angry":    "Tức giận",
    "surprise": "Ngạc nhiên",
    "fear":     "Sợ hãi",
    "disgust":  "Khó chịu",
    "neutral":  "Bình thường",
}

LEARNING_STATE_NAMES_VI = {
    "engaged":    "Tích cực",
    "neutral":    "Bình thường",
    "confused":   "Bối rối",
    "bored":      "Chán nản",
    "frustrated": "Thất vọng",
}


# ──────────────────────────────────────────────────────────────
# EmotionRecognizer: dual-engine wrapper
# ──────────────────────────────────────────────────────────────

class EmotionRecognizer:
    """
    Nhận dạng cảm xúc khuôn mặt — Dual-Engine.

    Primary  : HuggingFace Transformers (accuracy ~93%)
    Fallback : FER library  (accuracy ~65-75%)
    Last     : Rule-based heuristic

    Giữ nguyên giao diện public để không cần sửa các file khác.
    """

    def __init__(
        self,
        model_type: str = "auto",         # "auto" | "huggingface" | "fer" | "rules"
        update_interval: float = 2.0,
        window_size: int = 5,
    ):
        """
        Args:
            model_type     : "auto" tự chọn engine tốt nhất có sẵn
            update_interval: Seconds giữa 2 lần inference cho 1 face
            window_size    : Số frames để smooth kết quả
        """
        self.model_type      = model_type
        self.update_interval = update_interval
        self.window_size     = window_size

        # Engines
        self._hf_engine  = None   # HFEmotionRecognizer
        self._fer_detector = None  # FER object

        self._active_engine: str = "none"  # which engine is actually running
        self._initialized = False

        # Per-face state (dùng cho FER/rules vì HF engine tự quản lý)
        self._emotion_history: Dict[int, deque] = {}
        self._last_update:     Dict[int, float] = {}
        self._cached_results:  Dict[int, Dict] = {}

    # ── Initialization ──────────────────────────────────────

    def initialize(self):
        """Lazy init: try engines in priority order."""
        if self._initialized:
            return

        self._initialized = True

        target = self.model_type.lower()

        if target in ("auto", "huggingface"):
            if self._try_hf_engine():
                return

        if target in ("auto", "fer"):
            if self._try_fer_engine():
                return

        # Last resort: rule-based
        self._active_engine = "rules"
        logger.warning("[EmotionRecognizer] Using rule-based heuristic (low accuracy)")

    def _try_hf_engine(self) -> bool:
        """Try to initialize HuggingFace engine."""
        try:
            from hf_models.hf_emotion_recognizer import HFEmotionRecognizer

            hf = HFEmotionRecognizer(
                update_interval=self.update_interval,
                window_size=self.window_size,
            )
            ok = hf.initialize()
            if ok:
                self._hf_engine = hf
                self._active_engine = "huggingface"
                logger.info("[EmotionRecognizer] ✓ Primary engine: HuggingFace Transformers (~93% accuracy)")
                return True

        except ImportError:
            logger.info("[EmotionRecognizer] hf_models not found")
        except Exception as e:
            logger.info(f"[EmotionRecognizer] HuggingFace engine unavailable: {e}")

        return False

    def _try_fer_engine(self) -> bool:
        """Try to initialize FER library."""
        try:
            try:
                from fer.fer import FER
            except ImportError:
                from fer import FER

            self._fer_detector = FER(mtcnn=False)
            self._active_engine = "fer"
            logger.info("[EmotionRecognizer] ✓ Fallback engine: FER library (~70% accuracy)")
            return True

        except ImportError:
            logger.info("[EmotionRecognizer] FER library not installed")
        except Exception as e:
            logger.info(f"[EmotionRecognizer] FER unavailable: {e}")

        return False

    # ── Public API (unchanged interface) ─────────────────────

    def recognize_emotion(
        self,
        face_crop: np.ndarray,
        face_id: int,
        force_update: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Nhận dạng cảm xúc từ face crop.

        Args:
            face_crop   : BGR numpy array (khuôn mặt đã crop)
            face_id     : ID tracking của khuôn mặt
            force_update: Bỏ qua cache, chạy lại ngay

        Returns:
            Dict với emotion, emotion_vi, confidence, learning_state, etc.
        """
        if not self._initialized:
            self.initialize()

        # ── HuggingFace (manages its own cache) ──
        if self._active_engine == "huggingface" and self._hf_engine:
            result = self._hf_engine.recognize_emotion(face_crop, face_id, force_update)
            if result:
                return result

        # ── FER or Rules (managed here) ──
        now = time.time()
        if not force_update and face_id in self._last_update:
            if now - self._last_update[face_id] < self.update_interval:
                if face_id in self._cached_results:
                    return self._cached_results[face_id]

        raw = self._detect_emotion_raw(face_crop)
        if raw is None:
            return self._cached_results.get(face_id) or self._default_result(face_id)

        # Sliding window
        if face_id not in self._emotion_history:
            self._emotion_history[face_id] = deque(maxlen=self.window_size)
        self._emotion_history[face_id].append(raw)

        smoothed = self._smooth_emotions(face_id)
        self._last_update[face_id] = now
        self._cached_results[face_id] = smoothed

        return smoothed

    def batch_recognize(
        self, face_crops: List[Tuple[int, np.ndarray]]
    ) -> List[Dict[str, Any]]:
        """[(face_id, crop), ...] → [result, ...]"""
        results = []
        for face_id, crop in face_crops:
            r = self.recognize_emotion(crop, face_id)
            if r:
                results.append(r)
        return results

    # ── Internal inference ───────────────────────────────────

    def _detect_emotion_raw(
        self, face_crop: np.ndarray
    ) -> Optional[Dict[str, float]]:
        """Run active engine, return dict {label: score} or None."""
        if self._active_engine == "fer":
            return self._detect_with_fer(face_crop)
        return self._detect_with_rules(face_crop)

    def _detect_with_fer(
        self, face_crop: np.ndarray
    ) -> Optional[Dict[str, float]]:
        if self._fer_detector is None or face_crop is None:
            return None
        try:
            result = self._fer_detector.detect_emotions(face_crop)
            if result and len(result) > 0:
                return result[0].get("emotions", {})
            return None
        except Exception as e:
            logger.debug(f"[EmotionRecognizer] FER error: {e}")
            return None

    def _detect_with_rules(
        self, face_crop: np.ndarray
    ) -> Optional[Dict[str, float]]:
        """Heuristic fallback — not accurate, better than nothing."""
        if face_crop is None or face_crop.size == 0:
            return None
        try:
            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape
            avg_brightness = float(np.mean(gray))
            std_brightness = float(np.std(gray))
            lower_mean = float(np.mean(gray[2 * h // 3:, :]))
            upper_mean = float(np.mean(gray[: h // 3, :]))

            scores = {
                "happy": 0.10, "sad": 0.10, "angry": 0.10,
                "surprise": 0.10, "fear": 0.10, "disgust": 0.05,
                "neutral": 0.45,
            }
            if std_brightness > 50 and avg_brightness > 120:
                scores["happy"], scores["neutral"] = 0.40, 0.20
            elif avg_brightness < 80:
                scores["sad"], scores["neutral"] = 0.30, 0.30
            if abs(upper_mean - lower_mean) > 30:
                scores["surprise"] = 0.30

            return scores
        except Exception:
            return None

    # ── Smoothing (for FER/rules) ─────────────────────────────

    def _smooth_emotions(self, face_id: int) -> Dict[str, Any]:
        """Sliding window average across emotion history."""
        history = list(self._emotion_history.get(face_id, []))
        if not history:
            return self._default_result(face_id)

        emotion_keys = ["happy", "sad", "angry", "surprise", "fear", "disgust", "neutral"]
        avg_scores: Dict[str, float] = {}

        for key in emotion_keys:
            values = [h.get(key, 0) for h in history if h is not None]
            avg_scores[key] = round(sum(values) / len(values), 3) if values else 0.0

        dominant   = max(avg_scores, key=avg_scores.get)
        confidence = avg_scores[dominant]

        learning_state = EMOTION_TO_LEARNING_STATE.get(dominant, "neutral")
        emotion_score  = LEARNING_STATE_SCORES.get(learning_state, 60)

        return {
            "face_id":           face_id,
            "emotion":           dominant,
            "emotion_vi":        EMOTION_NAMES_VI.get(dominant, dominant),
            "confidence":        round(confidence, 3),
            "learning_state":    learning_state,
            "learning_state_vi": LEARNING_STATE_NAMES_VI.get(learning_state, learning_state),
            "emotion_score":     emotion_score,
            "emotion_scores":    avg_scores,
            "engine":            self._active_engine,
        }

    def _default_result(self, face_id: int) -> Dict[str, Any]:
        return {
            "face_id":           face_id,
            "emotion":           "neutral",
            "emotion_vi":        "Bình thường",
            "confidence":        0.5,
            "learning_state":    "neutral",
            "learning_state_vi": "Bình thường",
            "emotion_score":     60,
            "emotion_scores":    {
                "happy": 0, "sad": 0, "angry": 0,
                "surprise": 0, "fear": 0, "disgust": 0, "neutral": 1.0,
            },
            "engine": "default",
        }

    # ── Utilities ────────────────────────────────────────────

    def cleanup_stale(self, active_face_ids: set):
        """Remove state for untracked faces."""
        if self._hf_engine:
            self._hf_engine.cleanup_stale(active_face_ids)

        stale = set(self._emotion_history) - active_face_ids
        for fid in stale:
            self._emotion_history.pop(fid, None)
            self._last_update.pop(fid, None)
            self._cached_results.pop(fid, None)

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

    def get_stats(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {"active_engine": self._active_engine}
        if self._active_engine == "huggingface" and self._hf_engine:
            stats.update(self._hf_engine.get_stats())
        return stats
