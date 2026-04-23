Ship/deploy classroom system — Checklist trước khi bàn giao hoặc production.

## Pre-Ship Checklist

### System Health
- [ ] Backend start thành công: `python backend/main.py`
- [ ] Health check: `GET http://localhost:8000/health` → 200
- [ ] Camera connects: Xem log "Camera connected" 
- [ ] AI models loaded: Xem log "Models ready"
- [ ] WebSocket active: Frontend nhận engagement_update
- [ ] Database accessible: `GET /api/sessions` → 200

### Configuration
- [ ] `config.yaml` có camera URL chính xác
- [ ] `RECOGNITION_THRESHOLD` đã được tuned
- [ ] Log level phù hợp (không dùng DEBUG trong production)
- [ ] `data/` directory có ghi quyền

### AI Models
- [ ] Models đã được download: `python setup_models.py`
- [ ] `models_cache/` directory tồn tại và có files
- [ ] Test inference: `python test_hf_emotion.py`

### Integration Test
- [ ] `python test_integration.py` → all pass
- [ ] `python backend/test_crud.py` → all pass
- [ ] Mở browser → dashboard load
- [ ] Stats cập nhật real-time

### Documentation
- [ ] README có hướng dẫn cài đặt?
- [ ] `config.yaml` có comments giải thích các options?
- [ ] Known issues được ghi chú?

## Quick Start Commands (để bàn giao)

```bash
# 1. Cài dependencies
pip install -r backend/requirements.txt

# 2. Download AI models
python setup_models.py

# 3. Config camera
# Sửa config.yaml → camera.url

# 4. Chạy system
python backend/main.py

# 5. Mở dashboard
# http://localhost:8000
```

## Rollback Plan

Nếu có vấn đề sau khi ship:
1. Dừng backend: Ctrl+C
2. Kiểm tra `data/classroom.db` còn nguyên vẹn
3. Restore từ backup nếu DB bị corrupt
4. Đọc log để xác định nguyên nhân
