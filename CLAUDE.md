# Classroom Engagement System (NEHS)

Hệ thống AI giám sát và phân tích mức độ tập trung của học sinh trong lớp học theo thời gian thực.

## Project Structure

```
classroom/
├── backend/                  # Python FastAPI backend
│   ├── main.py               # Entry point, FastAPI app + WebSocket
│   ├── database.py           # SQLite ORM & all DB operations
│   ├── config.py / config.yaml # Cấu hình hệ thống
│   ├── camera_manager.py     # RTSP/camera capture (RTSP-over-TCP)
│   ├── face_detector.py      # Phát hiện khuôn mặt (MediaPipe/YOLO)
│   ├── deep_face_recognizer.py # Nhận diện học sinh (ArcFace/DeepFace)
│   ├── head_pose_estimator.py  # Ước lượng hướng đầu (gục đầu/nhìn lên)
│   ├── emotion_recognizer.py   # Phân tích cảm xúc (HuggingFace)
│   ├── classroom_detector.py   # Pipeline tổng hợp engagement
│   ├── engagement_engine.py    # Tính toán điểm tập trung
│   ├── attendance_tracker.py   # Điểm danh tự động
│   └── models.py               # Pydantic schemas / SQLAlchemy models
├── index.html               # Frontend dashboard (Vanilla HTML/JS)
├── app.js                   # Frontend logic + WebSocket client
├── styles.css               # Frontend styling
└── data/                    # SQLite DB, face embeddings, logs
```

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, uvicorn, WebSocket
- **AI/CV**: InsightFace (ArcFace), MediaPipe, OpenCV, HuggingFace Transformers
- **Database**: SQLite (via SQLAlchemy) — production path: `data/classroom.db`
- **Frontend**: Vanilla HTML + CSS + JavaScript (no framework)
- **Camera**: RTSP over TCP (`rtsp_transport=tcp`)

## Skills by Phase (addyosmani/agent-skills)

**Define:** Khi có tính năng mới → `spec-driven-development` trước
**Plan:** Phân tích task → `planning-and-task-breakdown`
**Build:**
  - Backend feature → `incremental-implementation` + `test-driven-development`
  - API/WebSocket endpoint → `api-and-interface-design`
  - Frontend dashboard → `frontend-ui-engineering`
  - AI model/pipeline → `source-driven-development` (đọc paper/docs trước)
**Verify:**
  - Bug hoặc lỗi camera/model → `debugging-and-error-recovery`
  - Test UI → `browser-testing-with-devtools`
**Review:**
  - Code quality → `code-review-and-quality`
  - Tối ưu inference → `performance-optimization`
  - Security → `security-and-hardening`
**Ship:**
  - Deploy → `shipping-and-launch`
  - Docs → `documentation-and-adrs`

## Intent → Skill Mapping

| Người dùng nói gì | Skill cần dùng |
|---|---|
| Thêm feature mới (ví dụ: xuất báo cáo) | `spec-driven-development` → `incremental-implementation` |
| Có bug / camera bị đứng | `debugging-and-error-recovery` |
| Review code trước khi merge | `code-review-and-quality` |
| Tối ưu tốc độ xử lý frame | `performance-optimization` |
| Thiết kế API endpoint mới | `api-and-interface-design` |
| Cập nhật UI dashboard | `frontend-ui-engineering` |
| Tích hợp model mới từ HuggingFace | `source-driven-development` |
| Viết test | `test-driven-development` |
| Giảm độ phức tạp code | `code-simplification` |

## Commands

```bash
# Chạy backend
cd backend && python main.py

# Hoặc dùng uvicorn
uvicorn backend.main:app --reload --port 8000

# Chạy test
cd backend && python test_crud.py
python test_integration.py
python test_hf_emotion.py

# Setup models
python setup_models.py
```

## Key Architecture Decisions

### Camera (ADR-001)
- Dùng `rtsp_transport=tcp` để tránh packet loss với RTSP
- Reconnect tự động khi mất kết nối > 5 giây
- File: `backend/camera_manager.py`

### Face Recognition (ADR-002)
- ArcFace (InsightFace) cho embedding generation → độ chính xác cao
- Fallback sang DeepFace nếu InsightFace không available
- Embeddings lưu trong SQLite dạng BLOB (numpy array serialized)
- File: `backend/deep_face_recognizer.py`

### Engagement Scoring (ADR-003)
- Head pose (hướng đầu) = trọng số 40%
- Emotion (cảm xúc) = trọng số 30%
- Attention (mắt/diện yếu) = trọng số 30%
- Trạng thái: `attentive` | `distracted` | `head_down` | `unknown`
- File: `backend/engagement_engine.py`

### WebSocket Broadcasting (ADR-004)
- Backend push stats mỗi 1 giây qua `/ws/classroom`
- Message format: JSON với `type: "engagement_update"` 
- Frontend nhận và update biểu đồ real-time
- File: `backend/main.py`, `app.js`

## Boundaries

- **Always**: Dùng RTSP-over-TCP, không dùng UDP
- **Always**: Validate Pydantic schema trước khi ghi DB
- **Always**: Log lỗi camera/model ra stderr, không crash toàn bộ server
- **Never**: Hard-code IP camera hay credentials trong code (dùng `config.yaml`)
- **Never**: Chạy model inference trên main thread (dùng `asyncio.run_in_executor`)
- **Never**: Return raw embedding bytes trong API response

## Common Issues & Solutions

| Issue | Root Cause | Fix |
|---|---|---|
| Camera freeze sau vài phút | UDP packet loss | Đảm bảo `rtsp_transport: tcp` trong config.yaml |
| `head_down` không hiện trong stats | State não được map đúng | Kiểm tra `engagement_engine.py` → `classify_state()` |
| Model load chậm lần đầu | HuggingFace download | Chạy `setup_models.py` trước, dùng `models_cache/` |
| WebSocket disconnect | CORS hoặc timeout | Kiểm tra `allow_origins` trong FastAPI CORS middleware |
| Face không nhận ra | Embedding threshold quá cao | Điều chỉnh `RECOGNITION_THRESHOLD` trong `config.yaml` |
