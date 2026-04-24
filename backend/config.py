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


def _override_from_env(config: AppConfig):
    """Override config values from environment variables using APP_SECTION__FIELD pattern."""
    for section_name in ["classroom", "detection", "engagement", "attendance", "privacy", "database", "server"]:
        section = getattr(config, section_name)
        # Handle dataclasses
        if hasattr(section, "__dataclass_fields__"):
            for field_name in section.__dataclass_fields__:
                env_key = f"APP_{section_name.upper()}__{field_name.upper()}"
                env_val = os.getenv(env_key)
                if env_val is not None:
                    # Type conversion
                    field_type = section.__dataclass_fields__[field_name].type
                    try:
                        if field_type == bool:
                            setattr(section, field_name, env_val.lower() in ("true", "1", "yes"))
                        elif field_type == int:
                            setattr(section, field_name, int(env_val))
                        elif field_type == float:
                            setattr(section, field_name, float(env_val))
                        else:
                            setattr(section, field_name, env_val)
                        print(f"[Config] Environment override: {env_key}={getattr(section, field_name)}")
                    except ValueError:
                        print(f"[Config] Failed to convert {env_key}={env_val} to {field_type}")


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file and override with environment variables."""
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

    # Apply environment overrides
    _override_from_env(config)

    # Resolve relative paths to absolute
    if not os.path.isabs(config.database.path):
        config.database.path = str(PROJECT_DIR / config.database.path)

    # Ensure directories exist
    os.makedirs(os.path.dirname(config.database.path), exist_ok=True)
    os.makedirs(str(PROJECT_DIR / "data" / "face_embeddings"), exist_ok=True)
    os.makedirs(str(PROJECT_DIR / "data" / "session_exports"), exist_ok=True)

    return config


# Singleton config instance
_config: Optional[AppConfig] = None
_config_path: Optional[str] = None
_config_mtime: float = 0.0  # Last modification time of config.yaml


def get_config() -> AppConfig:
    """Get the singleton config instance."""
    global _config, _config_path
    if _config is None:
        _config = load_config()
        _config_path = str(BASE_DIR / "config.yaml")
    return _config


# ── Hot-Reload Support ────────────────────────────────────────────────────────
# Cho phép thay đổi runtime parameters mà không cần restart app.
# Chỉ áp dụng cho các threshold/tuning params, KHÔNG thay đổi cấu trúc pipeline.

# Danh sách các field cho phép hot-reload
_HOT_RELOAD_FIELDS = {
    "detection": ["face_confidence", "frame_skip", "emotion_update_interval", "max_faces"],
    "engagement": ["alert_threshold", "confusion_alert_duration", "update_interval"],
    "attendance": ["match_threshold", "deep_face_threshold", "check_interval"],
}


def get_hot_params() -> Dict[str, Dict[str, any]]:
    """Get current hot-reloadable parameters."""
    cfg = get_config()
    result = {}
    for section_name, fields in _HOT_RELOAD_FIELDS.items():
        section = getattr(cfg, section_name)
        result[section_name] = {f: getattr(section, f) for f in fields}
    return result


def update_hot_params(updates: Dict[str, Dict[str, any]]) -> Dict[str, any]:
    """
    Update hot-reloadable parameters at runtime.
    Returns dict of changes applied.

    Example:
        update_hot_params({
            "detection": {"face_confidence": 0.6, "frame_skip": 4},
            "engagement": {"alert_threshold": 35}
        })
    """
    cfg = get_config()
    changes = {}

    for section_name, field_updates in updates.items():
        if section_name not in _HOT_RELOAD_FIELDS:
            continue

        section = getattr(cfg, section_name, None)
        if section is None:
            continue

        allowed = _HOT_RELOAD_FIELDS[section_name]
        for field_name, new_value in field_updates.items():
            if field_name not in allowed:
                continue

            old_value = getattr(section, field_name, None)
            if old_value == new_value:
                continue

            # Type coercion
            field_type = type(old_value)
            try:
                coerced = field_type(new_value)
                setattr(section, field_name, coerced)
                changes[f"{section_name}.{field_name}"] = {
                    "old": old_value,
                    "new": coerced,
                }
            except (ValueError, TypeError) as e:
                changes[f"{section_name}.{field_name}"] = {"error": str(e)}

    return changes


def reload_config_from_file() -> Dict[str, any]:
    """
    Re-read config.yaml and apply hot-reloadable changes.
    Non-hot fields (cameras, server, database) are NOT changed.
    Returns dict of changes applied.
    """
    global _config_mtime
    path = str(BASE_DIR / "config.yaml")

    if not os.path.exists(path):
        return {"error": "config.yaml not found"}

    # Check if file actually changed
    mtime = os.path.getmtime(path)
    if mtime == _config_mtime:
        return {"status": "no_change"}
    _config_mtime = mtime

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    updates = {}
    for section_name, fields in _HOT_RELOAD_FIELDS.items():
        if section_name in data:
            section_data = data[section_name]
            section_updates = {}
            for f in fields:
                if f in section_data:
                    section_updates[f] = section_data[f]
            if section_updates:
                updates[section_name] = section_updates

    if updates:
        return update_hot_params(updates)
    return {"status": "no_hot_changes"}
