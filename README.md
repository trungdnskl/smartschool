# 🎓 Classroom Engagement Analysis System (NEHS)
## Hệ thống AI Phân tích Mức độ Tiếp nhận Học tập

> Phân tích mức độ tập trung học sinh **theo thời gian thực** qua camera, sử dụng AI nhận diện khuôn mặt, cảm xúc và hướng đầu.

---

## 📋 Tổng quan

Hệ thống sử dụng **camera lớp học** (IP + USB) kết hợp **AI pipeline** để:

- 🔍 **Phát hiện khuôn mặt** — MediaPipe BlazeFace + OpenCV DNN, tối đa 40 khuôn mặt
- 😊 **Nhận dạng cảm xúc** — HuggingFace Transformers (~93%) → FER (~70%) → Rule-based
- 👀 **Ước tính hướng nhìn** — MediaPipe Face Mesh → Yaw/Pitch/Roll → 4 trạng thái chú ý
- 📋 **Điểm danh tự động** — InsightFace ArcFace (~99%) → DeepFace → LBPH cascade
- 📊 **Tính toán Engagement** — Score 0-100 = 35% Cảm xúc + 45% Chú ý + 20% Hành vi
- ⚠️ **Cảnh báo thông minh** — Duration-based: bối rối >120s, ngủ gật >30s, engagement <40%
- 👥 **Đếm sĩ số chính xác** — YOLOv8 person detection (bổ sung cho face detection)

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────┐
│                    CLASSROOM (1 lớp học)                    │
│                                                             │
│   📷 Camera trước bảng (RTSP)    📷 Camera sau lớp (RTSP)  │
│   📷 Webcam USB (laptop GV)                                │
│         │                              │                    │
└─────────┼──────────────────────────────┼────────────────────┘
          │ Thread 1                     │ Thread 2
          ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI + AI)                     │
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
│  │ CameraManager│   │  Processing  │   │   WebSocket  │    │
│  │ (multi-cam)  │──▶│  Pipeline    │──▶│  Broadcast   │    │
│  └──────────────┘   └──────┬───────┘   └──────┬───────┘    │
│                            │                   │            │
│  ┌─────────────────────────▼───────────────┐   │            │
│  │        ClassroomDetector (Master)       │   │            │
│  │                                         │   │            │
│  │  FaceDetector ──▶ EmotionRecognizer     │   │            │
│  │       │                   │             │   │            │
│  │  PersonDetector  HeadPoseEstimator      │   │            │
│  │       │                   │             │   │            │
│  │  AttendanceTracker   EngagementEngine   │   │            │
│  │                           │             │   │            │
│  │  ┌── Multi-Camera Fusion ─┘             │   │            │
│  │  │ Merge faces + emotions + poses       │   │            │
│  │  │ Sĩ số = max(cam_front, cam_rear)     │   │            │
│  │  └──────────────────────────────────────┘   │            │
│  │                                             │            │
│  └─────────────────────────────────────────────┘            │
│                            │                                │
│                    ┌───────▼───────┐                        │
│                    │  SQLite (WAL) │                        │
│                    │  classroom.db │                        │
│                    └───────────────┘                        │
│                                                             │
│  API: 35+ endpoints    Auth: JWT (optional)                 │
│  Monitoring: Prometheus metrics + health probes             │
│  Privacy: local-only, auto-cleanup 90 ngày                  │
└─────────────────────────────────────────────────────────────┘
          │ WebSocket push ~2s
          ▼
┌─────────────────────────────────────────────────────────────┐
│                 FRONTEND (React + Vite)                      │
│                                                             │
│  Dashboard │ Điểm danh │ Cảm xúc │ Phân tích │ Camera     │
│  Học sinh  │ Giáo viên │ Lớp học  │ Cài đặt   │ Login      │
│                                                             │
│  Dark theme │ Tiếng Việt │ Responsive 1366x768+            │
└─────────────────────────────────────────────────────────────┘
```

---

## 📷 Cấu hình Camera

Hệ thống hỗ trợ **đa camera** — nguyên lý **1 lớp = 2-3 camera**:

| Camera | Vị trí | Mục đích | Mặc định |
|--------|--------|----------|----------|
| `cam_front` | Trước bảng, nhìn xuống HS | Face detection + Emotion + Attendance | RTSP Hikvision |
| `cam_rear` | Sau lớp, nhìn lên bảng | Bổ sung góc nhìn + person count | RTSP (disabled) |
| `cam_usb` | Webcam laptop giáo viên | Test/demo, góc nhìn GV | USB `0` |

### Multi-Camera Fusion
- Mỗi camera chạy **thread riêng**, gửi frame song song
- `ClassroomDetector._merge_camera_results()` **gộp faces + emotions + head poses** từ tất cả camera active
- **Sĩ số** = `max(persons_cam_front, persons_cam_rear)` — tránh đếm trùng
- Camera nào mất kết nối >5s tự động loại khỏi merge

### Loại nguồn video hỗ trợ
```yaml
# Camera IP (RTSP) — Hikvision, Dahua, KBVISION, Tapo, EZVIZ
url: "rtsp://user:pass@192.168.x.x:554/Streaming/Channels/101"

# Webcam USB
url: "0"    # webcam đầu tiên
url: "1"    # webcam thứ 2

# Video file (demo/test)
url: "E:/videos/classroom.mp4"

# HTTP MJPEG (IP Camera App trên điện thoại)
url: "http://192.168.x.x:8080/video"
```

---

## 🧠 AI Pipeline

```
Frame ──▶ FaceDetector ──▶ EmotionRecognizer ──▶ HeadPoseEstimator
  │         (BlazeFace      (HuggingFace        (MediaPipe Mesh
  │          + DNN)          → FER → Rules)      → solvePnP)
  │            │                  │                    │
  │            ▼                  ▼                    ▼
  │       AttendanceTracker  7 cảm xúc →          4 hướng nhìn
  │       (ArcFace → LBPH)  5 trạng thái          + attention score
  │            │                  │                    │
  │            ▼                  ▼                    ▼
  └──▶ PersonDetector      EngagementEngine
       (YOLOv8n)           Score = 0.35×E + 0.45×A + 0.20×B
                                  │
                           Alert System (duration-based)
                           • Bối rối > 120s → cảnh báo cá nhân
                           • Ngủ gật > 30s → cảnh báo
                           • Engagement < 40% → cảnh báo lớp
                           • > 30% chán → gợi ý đổi hoạt động
                           • Hồi phục → thông báo tích cực
```

### Engagement States
| State | Mô tả | Score Impact |
|-------|--------|-------------|
| `attentive` | Tập trung, nhìn bảng/GV | Cao (70-100) |
| `confused` | Bối rối, cần hỗ trợ | Trung bình (40-60) |
| `bored` | Chán nản, mất hứng | Thấp (20-40) |
| `distracted` | Mất tập trung, nhìn chỗ khác | Thấp (10-30) |
| `head_down` | Gục đầu / ngủ gật | Rất thấp (0-20) |

---

## 🚀 Khởi chạy

### Cách 1: One-click (Windows)
```
Nhấp đúp: start_classroom.bat
```

### Cách 2: Thủ công
```bash
# Backend (FastAPI + AI)
python backend/main.py

# Frontend (React + Vite) — terminal khác
cd frontend
npm run dev
```

### URL
| Service | URL |
|---------|-----|
| Dashboard | http://localhost:5173 |
| API Docs (Swagger) | http://localhost:8001/docs |
| Health Check | http://localhost:8001/health |
| Prometheus Metrics | http://localhost:8001/metrics |

---

## 📁 Cấu trúc dự án

```
classroom/
├── start_classroom.bat          # One-click khởi chạy
├── requirements.txt             # Python dependencies
├── SRS_Classroom_Engagement_System.md  # Đặc tả yêu cầu
│
├── backend/
│   ├── main.py                  # FastAPI app + lifespan + WebSocket
│   ├── config.yaml              # Cấu hình (camera, AI, thresholds)
│   ├── config.py                # Config loader (dataclass)
│   ├── state.py                 # Global state (singleton)
│   ├── processing.py            # Frame pipeline + evidence capture
│   │
│   ├── camera_manager.py        # Multi-camera RTSP/USB/HTTP
│   ├── classroom_detector.py    # Master pipeline + multi-cam fusion
│   ├── face_detector.py         # MediaPipe + DNN hybrid detection
│   ├── person_detector.py       # YOLOv8 person counting
│   ├── emotion_recognizer.py    # HuggingFace → FER → rules
│   ├── head_pose_estimator.py   # MediaPipe Face Mesh → Euler angles
│   ├── attendance_tracker.py    # ArcFace → DeepFace → LBPH
│   ├── engagement_engine.py     # Scoring + duration-based alerts
│   ├── database.py              # SQLite CRUD + retention cleanup
│   │
│   ├── api/
│   │   ├── deps.py              # Auth dependencies
│   │   └── routes/
│   │       ├── auth.py          # JWT login/register
│   │       ├── sessions.py      # Session lifecycle
│   │       ├── students.py      # Student CRUD + enrollment
│   │       ├── teachers.py      # Teacher CRUD
│   │       ├── cameras.py       # Camera CRUD + MJPEG stream
│   │       └── system.py        # Health, metrics, stats
│   │
│   ├── core/
│   │   └── logging_config.py    # Structured logging
│   │
│   └── hf_models/
│       └── insightface_recognizer.py  # ArcFace ONNX engine
│
├── frontend/                    # React (Vite) dashboard
│   ├── src/
│   │   ├── components/          # Dashboard, Layout, UI
│   │   ├── stores/              # Zustand state management
│   │   └── services/            # API + WebSocket clients
│   └── vite.config.js
│
└── data/                        # Runtime data (git-ignored)
    ├── classroom.db             # SQLite database
    ├── face_embeddings/         # Student face models
    └── alert_evidence/          # Alert screenshot evidence
```

---

## 🔒 Bảo mật & Quyền riêng tư

- ✅ **Local-only** — mọi xử lý trên máy cục bộ, không gửi dữ liệu ra internet
- ✅ **Không lưu ảnh gốc** — chỉ lưu grayscale samples cho attendance
- ✅ **RTSP password masking** — ẩn mật khẩu camera trong log
- ✅ **Auto-cleanup** — tự động xóa dữ liệu > 90 ngày
- ✅ **CORS + Rate limiting** — chống abuse API
- ✅ **SSRF protection** — validate URL camera
- ✅ **JWT auth** — optional, bật qua `AUTH_ENABLED=true`

---

## ⚙️ Cấu hình (config.yaml)

| Section | Key | Default | Mô tả |
|---------|-----|---------|-------|
| `detection` | `face_confidence` | 0.35 | Ngưỡng tin cậy face detection |
| `detection` | `frame_skip` | 3 | Xử lý mỗi N frame (tăng = nhẹ CPU hơn) |
| `detection` | `max_faces` | 40 | Tối đa khuôn mặt theo dõi |
| `engagement` | `weights` | 0.35/0.45/0.20 | Trọng số Emotion/Attention/Behavior |
| `engagement` | `alert_threshold` | 40 | Ngưỡng cảnh báo engagement thấp (%) |
| `attendance` | `late_threshold_minutes` | 10 | Số phút muộn |
| `attendance` | `check_interval` | 30 | Kiểm tra điểm danh mỗi N giây |
| `privacy` | `data_retention_days` | 90 | Tự xóa dữ liệu sau N ngày |

---

## 📊 Yêu cầu hệ thống

| Thành phần | Yêu cầu tối thiểu |
|-----------|-------------------|
| OS | Windows 10/11 |
| Python | 3.9+ |
| RAM | 4 GB (8 GB khuyến nghị) |
| CPU | Intel i5 / AMD Ryzen 5 trở lên |
| Camera | Webcam USB hoặc Camera IP (RTSP) |
| Mạng | LAN cùng subnet với camera IP |
| Trình duyệt | Chrome/Edge/Firefox (dashboard) |

---

## 📝 License

NEHS — National Education High School Project  
Developed for classroom engagement monitoring and teaching improvement.
