"""
core/interfaces.py — Abstract base classes cho AI engines.
Enables Dependency Injection và testability:
  - Swap engines mà không sửa business logic
  - Mock dễ dàng trong unit tests
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ──────────────────────────────────────────────
# Face Detection Interface
# ──────────────────────────────────────────────
class IFaceDetector(ABC):
    """Contract for all face detection backends."""

    @abstractmethod
    def initialize(self) -> bool:
        """Load model weights. Return True on success."""

    @abstractmethod
    def detect_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Return list of {bbox, confidence} dicts."""

    @abstractmethod
    def crop_face(
        self,
        frame: np.ndarray,
        bbox: List[int],
        margin: float = 0.2,
    ) -> Optional[np.ndarray]:
        """Crop and return face region with margin. None if invalid."""


# ──────────────────────────────────────────────
# Face Recognition / Embedding Interface
# ──────────────────────────────────────────────
class IFaceRecognizer(ABC):
    """Contract for face recognition engines (ArcFace, LBPH, etc.)."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """True if model is loaded and ready."""

    @abstractmethod
    def initialize(self) -> bool:
        """Load model. Return True on success."""

    @abstractmethod
    def get_embedding(self, face_crop: np.ndarray) -> Optional[np.ndarray]:
        """Extract face embedding vector. None on failure."""

    @abstractmethod
    def identify(
        self, face_crop: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """
        Identify person from face crop.
        Returns: {student_id, student_name, confidence} or None.
        """

    @abstractmethod
    def enroll(
        self,
        student_id: str,
        name: str,
        face_crop: np.ndarray,
        class_name: str = "",
    ) -> bool:
        """Enroll a new face sample. Return True on success."""

    @abstractmethod
    def delete(self, student_id: str) -> bool:
        """Remove student from recognition model."""

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return engine statistics dict."""


# ──────────────────────────────────────────────
# Attendance Tracker Interface
# ──────────────────────────────────────────────
class IAttendanceTracker(ABC):
    """Contract for attendance tracking logic."""

    @abstractmethod
    def initialize(self) -> None:
        """Load persisted data."""

    @abstractmethod
    def start_session(self, session_id: int) -> None:
        """Start a new attendance session."""

    @abstractmethod
    def stop_session(self) -> Dict[str, Any]:
        """Stop session and return summary dict."""

    @abstractmethod
    def check_attendance(
        self, face_id: int, face_crop: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """Attempt to identify face and mark attendance. Return record or None."""

    @abstractmethod
    def enroll_face(
        self,
        student_id: str,
        name: str,
        face_crop: np.ndarray,
        class_name: str = "",
    ) -> bool:
        """Add face sample for student. Return True on success."""

    @abstractmethod
    def delete_student(self, student_id: str) -> None:
        """Remove student from tracker."""

    @abstractmethod
    def get_attendance_summary(self) -> Dict[str, Any]:
        """Return {total, present, late, absent, records}."""

    @abstractmethod
    def get_enrolled_count(self) -> int:
        """Number of enrolled students."""


# ──────────────────────────────────────────────
# Emotion Recognizer Interface
# ──────────────────────────────────────────────
class IEmotionRecognizer(ABC):
    """Contract for emotion detection engines."""

    @abstractmethod
    def initialize(self) -> bool:
        """Load model. Return True on success."""

    @abstractmethod
    def predict(
        self, face_crop: np.ndarray
    ) -> Optional[Dict[str, float]]:
        """Return {emotion_label: score} dict or None."""
