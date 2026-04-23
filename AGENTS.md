# AGENTS.md — Classroom Engagement System (NEHS)

File này hướng dẫn các AI coding agents (Antigravity, Claude Code, Cursor, Copilot...) 
khi làm việc trong repository này.

---

## Project Overview

**Hệ thống AI giám sát lớp học (NEHS)** — phân tích mức độ tập trung học sinh qua camera, 
nhận diện khuôn mặt, cảm xúc và hướng đầu theo thời gian thực.

**Stack chính:**
- Backend: Python FastAPI + WebSocket + SQLite
- AI Pipeline: InsightFace + MediaPipe + HuggingFace Transformers
- Frontend: Vanilla HTML/CSS/JS dashboard

---

## Skill-Driven Development Rules

### Core Rules (BẮT BUỘC)
1. Nếu task khớp với một skill, PHẢI kích hoạt skill đó TRƯỚC
2. Skills nằm trong `skills/<skill-name>/SKILL.md`
3. Không bao giờ implement trực tiếp nếu có skill phù hợp
4. Luôn follow đúng skill instructions — không áp dụng một phần

### Lifecycle — Intent → Skill Mapping

| User Intent | Skill phải dùng |
|---|---|
| Tính năng mới / feature mới | `spec-driven-development` → `incremental-implementation` |
| Lập kế hoạch / phân tích task | `planning-and-task-breakdown` |
| Bug / lỗi / hành vi bất ngờ | `debugging-and-error-recovery` |
| Code review | `code-review-and-quality` |
| Refactor / đơn giản hóa code | `code-simplification` |
| Thiết kế API / WebSocket endpoint | `api-and-interface-design` |
| UI dashboard / frontend | `frontend-ui-engineering` |
| Viết test | `test-driven-development` |
| Deploy / xuất bản | `shipping-and-launch` |
| Tối ưu hiệu năng | `performance-optimization` |
| Security audit | `security-and-hardening` |
| Tích hợp model mới (HuggingFace/InsightFace) | `source-driven-development` |

### Phase Lifecycle

```
DEFINE → PLAN → BUILD → VERIFY → REVIEW → SHIP
```

- **DEFINE** → `spec-driven-development`: Làm rõ yêu cầu, viết spec TRƯỚC khi code
- **PLAN** → `planning-and-task-breakdown`: Chia nhỏ task, estimate
- **BUILD** → `incremental-implementation` + `test-driven-development`
- **VERIFY** → `debugging-and-error-recovery`: Reproduce bug, trace root cause
- **REVIEW** → `code-review-and-quality`: Kiểm tra trước khi merge
- **SHIP** → `shipping-and-launch`: Deploy checklist

---

## Anti-Rationalization (Những suy nghĩ SAI — phải bỏ qua)

❌ "Task này quá nhỏ, không cần skill"  
❌ "Tôi có thể implement nhanh luôn"  
❌ "Để tôi gather context trước đã"  
❌ "Chỉ fix một dòng thôi, không cần spec"  

✅ **Hành vi đúng**: Luôn kiểm tra skill phù hợp TRƯỚC, dù task nhỏ đến đâu.

---

## Project-Specific Context

### Quan trọng nhất khi làm việc với project này:

#### 1. Camera / RTSP
- File: `backend/camera_manager.py`
- Luôn dùng `rtsp_transport=tcp` — KHÔNG dùng UDP
- Khi debug camera: kiểm tra `config.yaml` → `camera.rtsp_transport`

#### 2. AI Pipeline thứ tự
```
Frame → FaceDetector → DeepFaceRecognizer → HeadPoseEstimator → EmotionRecognizer → EngagementEngine
```
- Mỗi stage độc lập, có thể fail gracefully
- Inference KHÔNG được chạy trên main thread → dùng `asyncio.run_in_executor`

#### 3. Engagement States
```python
# Các trạng thái hợp lệ:
"attentive"   # Học sinh tập trung
"distracted"  # Mất tập trung (nhìn ngang)
"head_down"   # Gục đầu (buồn ngủ/cúi)
"unknown"     # Không xác định được
```

#### 4. Database
- Engine: SQLite tại `data/classroom.db`
- ORM: SQLAlchemy
- **Không được** return raw embedding bytes trong API response
- Luôn validate bằng Pydantic schema trước khi ghi DB

#### 5. WebSocket 
- Endpoint: `/ws/classroom`
- Push mỗi ~1 giây
- Message format:
```json
{
  "type": "engagement_update",
  "data": {
    "total_students": 30,
    "attentive": 20,
    "distracted": 7,
    "head_down": 3,
    "timestamp": "2026-04-14T09:30:00"
  }
}
```

#### 6. Config
- File: `backend/config.yaml`
- KHÔNG hard-code IP camera hay credentials trong code
- Đọc qua `backend/config.py`

---

## File Structure Quick Reference

```
backend/
├── main.py              # FastAPI app, WebSocket, startup
├── database.py          # SQLite CRUD, SQLAlchemy models
├── config.py            # Config loader
├── config.yaml          # Config values (camera URL, thresholds...)
├── camera_manager.py    # RTSP capture, reconnect logic
├── face_detector.py     # MediaPipe/YOLO face detection
├── deep_face_recognizer.py  # ArcFace embeddings, matching
├── head_pose_estimator.py   # Head direction (MediaPipe landmarks)
├── emotion_recognizer.py    # HuggingFace emotion model
├── classroom_detector.py    # Orchestration pipeline
├── engagement_engine.py     # Scoring + state classification
├── attendance_tracker.py    # Auto attendance from recognition
└── models.py            # Pydantic / SQLAlchemy schemas

Frontend:
├── index.html    # Dashboard UI
├── app.js        # WebSocket client, chart updates
└── styles.css    # Styling
```

---

## Commands

```bash
# Chạy system
python backend/main.py

# Chạy test
python backend/test_crud.py
python test_integration.py  
python test_hf_emotion.py

# Setup AI models (lần đầu)
python setup_models.py
```

---

## Verification Requirements

Trước khi kết thúc bất kỳ task nào, PHẢI verify:

1. **Backend starts**: `python backend/main.py` không có exception
2. **API responds**: `GET /health` hoặc `GET /api/sessions` trả 200
3. **WebSocket connects**: Frontend nhận được `engagement_update` events  
4. **No regression**: Các test hiện tại vẫn pass
5. **"Seems right" KHÔNG đủ** — phải có runtime evidence (log/response)

---

## Skill Execution Pattern

```
1. User request → Identify intent
2. Map to skill (bảng trên)
3. Read SKILL.md → Follow workflow
4. Implement → Verify evidence
5. Report kết quả + evidence cho user
```
