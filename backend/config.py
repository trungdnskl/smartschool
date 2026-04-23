"""
Classroom Engagement System - Configuration Loader
Đọc và quản lý cấu hình từ config.yaml
Tối ưu cho CPU-only processing
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict


# Base directory = backend folder
BASE_DIR = Path(__file__).parent
# Project root = parent of backend
PROJECT_DIR = BASE_DIR.parent


@dataclass
class CameraConfig:
    id: str
    name: str
    url: str
    enabled: bool = True


@dataclass
class ClassroomConfig:
    name: str = "Phòng STEM 101"
    capacity: int = 35
    subject: str = "Toán học"
    grade: str = "K-12"


@dataclass
class DetectionConfig:
    face_model: str = "opencv_dnn"
    face_confidence: float = 0.6
    emotion_model: str = "fer"
    emotion_update_interval: float = 2.0
    head_pose_enabled: bool = True
    frame_skip: int = 3
    max_faces: int = 40


@dataclass
class EngagementConfig:
    weights: Dict[str, float] = field(default_factory=lambda: {
        "emotion": 0.35,
        "attention": 0.45,
        "behavior": 0.20,
    })
    alert_threshold: int = 40
    confusion_alert_duration: int = 120
    update_interval: float = 2.0


@dataclass
class AttendanceConfig:
    auto_mark: bool = True
    match_threshold: float = 0.6       # LBPH threshold (0-1 normalized)
    deep_face_threshold: float = 0.45  # ArcFace/InsightFace cosine similarity
    check_interval: int = 30
    late_threshold_minutes: int = 10


@dataclass
class PrivacyConfig:
    store_face_images: bool = False
    data_retention_days: int = 90
    anonymize_reports: bool = True
    require_consent: bool = True
    encrypt_embeddings: bool = True


@dataclass
class DatabaseConfig:
    path: str = "data/classroom.db"


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8001


@dataclass
class AppConfig:
    classroom: ClassroomConfig = field(default_factory=ClassroomConfig)
    cameras: List[CameraConfig] = field(default_factory=list)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    engagement: EngagementConfig = field(default_factory=EngagementConfig)
    attendance: AttendanceConfig = field(default_factory=AttendanceConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    server: ServerConfig = field(default_factory=ServerConfig)


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = str(BASE_DIR / "config.yaml")

    config = AppConfig()

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Parse classroom
        if "classroom" in data:
            config.classroom = ClassroomConfig(**data["classroom"])

        # Parse cameras
        if "cameras" in data:
            config.cameras = [
                CameraConfig(**cam) for cam in data["cameras"]
            ]

        # Parse detection
        if "detection" in data:
            config.detection = DetectionConfig(**data["detection"])

        # Parse engagement
        if "engagement" in data:
            eng_data = data["engagement"]
            config.engagement = EngagementConfig(
                weights=eng_data.get("weights", config.engagement.weights),
                alert_threshold=eng_data.get("alert_threshold", 40),
                confusion_alert_duration=eng_data.get("confusion_alert_duration", 120),
                update_interval=eng_data.get("update_interval", 2.0),
            )

        # Parse attendance
        if "attendance" in data:
            config.attendance = AttendanceConfig(**data["attendance"])

        # Parse privacy
        if "privacy" in data:
            config.privacy = PrivacyConfig(**data["privacy"])

        # Parse database
        if "database" in data:
            config.database = DatabaseConfig(**data["database"])

        # Parse server
        if "server" in data:
            config.server = ServerConfig(**data["server"])

    # Resolve relative paths to absolute
    config.database.path = str(PROJECT_DIR / config.database.path)

    # Ensure directories exist
    os.makedirs(os.path.dirname(config.database.path), exist_ok=True)
    os.makedirs(str(PROJECT_DIR / "data" / "face_embeddings"), exist_ok=True)
    os.makedirs(str(PROJECT_DIR / "data" / "session_exports"), exist_ok=True)

    return config


# Singleton config instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the singleton config instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
