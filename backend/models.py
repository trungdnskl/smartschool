"""
Classroom Engagement System - Pydantic Models
Các model dữ liệu cho API responses
"""

from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


# ===== Enums =====

class EmotionType(str, Enum):
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    SURPRISE = "surprise"
    FEAR = "fear"
    DISGUST = "disgust"
    NEUTRAL = "neutral"


class LearningState(str, Enum):
    ENGAGED = "engaged"          # Tham gia tích cực
    NEUTRAL = "neutral"          # Bình thường
    CONFUSED = "confused"        # Bối rối
    BORED = "bored"              # Chán nản
    FRUSTRATED = "frustrated"    # Thất vọng


class AttentionDirection(str, Enum):
    LOOKING_AT_TEACHER = "looking_at_teacher"
    LOOKING_AWAY = "looking_away"
    LOOKING_DOWN = "looking_down"
    HEAD_DOWN = "head_down"


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ===== Data Models =====

class FaceDetection(BaseModel):
    """Kết quả phát hiện khuôn mặt."""
    face_id: int
    bbox: List[int]  # [x1, y1, x2, y2]
    confidence: float
    landmarks: Optional[List[List[float]]] = None


class EmotionResult(BaseModel):
    """Kết quả nhận dạng cảm xúc."""
    face_id: int
    emotion: EmotionType
    confidence: float
    learning_state: LearningState
    emotion_scores: Dict[str, float] = {}


class HeadPoseResult(BaseModel):
    """Kết quả ước tính hướng nhìn."""
    face_id: int
    yaw: float
    pitch: float
    roll: float
    attention_direction: AttentionDirection


class StudentEngagement(BaseModel):
    """Điểm tham gia của từng học sinh."""
    face_id: int
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    emotion: EmotionType = EmotionType.NEUTRAL
    learning_state: LearningState = LearningState.NEUTRAL
    attention_direction: AttentionDirection = AttentionDirection.LOOKING_AT_TEACHER
    engagement_score: float = 50.0
    emotion_score: float = 50.0
    attention_score: float = 50.0
    behavior_score: float = 50.0


class ClassroomSnapshot(BaseModel):
    """Ảnh chụp trạng thái toàn lớp tại một thời điểm."""
    timestamp: str
    total_faces: int = 0
    avg_engagement: float = 0.0
    emotion_distribution: Dict[str, int] = {}
    learning_state_distribution: Dict[str, int] = {}
    attention_distribution: Dict[str, int] = {}
    students: List[StudentEngagement] = []
    active_alerts: List[dict] = []


# ===== Student & Session Models =====

class TeacherProfile(BaseModel):
    """Hồ sơ giáo viên."""
    id: Optional[int] = None
    teacher_id: str
    name: str
    email: str = ""
    phone: str = ""
    subject_specialty: str = ""
    is_active: bool = True
    created_at: Optional[str] = None


class SubjectInfo(BaseModel):
    """Thông tin môn học."""
    id: Optional[int] = None
    subject_id: str
    name: str
    description: str = ""
    grade_level: str = ""


class ClassInfo(BaseModel):
    """Thông tin lớp học."""
    id: Optional[int] = None
    class_id: str
    name: str
    grade: str = ""
    academic_year: str = ""
    room: str = ""
    homeroom_teacher_id: Optional[int] = None
    teacher_name: Optional[str] = None
    student_count: int = 0
    is_active: bool = True
    created_at: Optional[str] = None


class StudentProfile(BaseModel):
    """Hồ sơ học sinh."""
    id: Optional[int] = None
    student_id: str
    name: str
    class_name: str = ""
    class_id: Optional[int] = None
    class_display: Optional[str] = None
    has_consent: bool = False
    parent_phone: str = ""
    notes: str = ""
    enrolled_at: Optional[str] = None


class ParentConsent(BaseModel):
    """Đồng ý của phụ huynh."""
    id: Optional[int] = None
    student_id: str
    parent_name: str
    parent_phone: str = ""
    consent_type: str = "face_recognition"
    is_granted: bool = True
    granted_at: Optional[str] = None
    expires_at: Optional[str] = None
    notes: str = ""


class SessionInfo(BaseModel):
    """Thông tin buổi học."""
    id: Optional[int] = None
    session_name: str = ""
    class_name: str = ""
    subject: str = ""
    teacher_name: str = ""
    class_id: Optional[int] = None
    teacher_id: Optional[int] = None
    subject_id: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_active: bool = False
    total_students: int = 0
    present_count: int = 0


class AttendanceRecord(BaseModel):
    """Bản ghi điểm danh."""
    id: Optional[int] = None
    session_id: int
    student_id: str
    student_name: str = ""
    status: AttendanceStatus = AttendanceStatus.ABSENT
    arrival_time: Optional[str] = None
    leave_time: Optional[str] = None


class AlertMessage(BaseModel):
    """Cảnh báo từ hệ thống."""
    id: Optional[int] = None
    session_id: Optional[int] = None
    timestamp: str
    alert_type: str
    message: str
    severity: AlertSeverity = AlertSeverity.INFO
    is_read: bool = False


class SessionSummary(BaseModel):
    """Tóm tắt sau buổi học."""
    session_id: int
    duration_minutes: float = 0.0
    avg_engagement: float = 0.0
    peak_engagement: float = 0.0
    lowest_engagement: float = 0.0
    peak_time: Optional[str] = None
    low_time: Optional[str] = None
    total_students: int = 0
    present_count: int = 0
    late_count: int = 0
    absent_count: int = 0
    emotion_distribution: Dict[str, float] = {}
    engagement_timeline: List[Dict[str, float]] = []
    alerts_count: int = 0
    recommendations: List[str] = []


# ===== API Request/Response Models =====

class StartSessionRequest(BaseModel):
    """Yêu cầu bắt đầu buổi học."""
    session_name: str = ""
    class_name: str = ""
    subject: str = ""
    teacher_name: str = ""
    class_id: Optional[int] = None
    teacher_id: Optional[int] = None
    subject_id: Optional[int] = None


class EnrollStudentRequest(BaseModel):
    """Yêu cầu đăng ký học sinh."""
    student_id: str
    name: str
    class_name: str = ""
    class_id: Optional[int] = None


class WebSocketMessage(BaseModel):
    """Message gửi qua WebSocket."""
    type: str  # "engagement_update", "alert", "attendance", "session_status"
    data: dict

