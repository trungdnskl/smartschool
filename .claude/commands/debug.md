Debug và phục hồi sau lỗi trong classroom system.

Quy trình debug có hệ thống — KHÔNG đoán mò:

## Bước 1: Reproduce (Tái hiện lỗi)
- Reproduce được lỗi không? (nếu không → ghi log chi tiết hơn)
- Lỗi xảy ra khi nào? (startup / camera connect / inference / websocket?)
- Lỗi xảy ra thường xuyên hay đôi khi?

## Bước 2: Isolate (Khoanh vùng)
Trace theo pipeline:
```
Camera → FaceDetector → Recognizer → HeadPose → Emotion → Engagement → WebSocket → Frontend
```

Kiểm tra từng stage:
```bash
# Test camera riêng
python -c "from backend.camera_manager import CameraManager; cm = CameraManager(); print(cm.test_connection())"

# Test face detector
python -c "from backend.face_detector import FaceDetector; ..."

# Test database
python backend/test_crud.py

# Check logs
# Tìm ERROR hoặc EXCEPTION trong stdout
```

## Bước 3: Root Cause Analysis
Tìm nguyên nhân gốc rễ, không chỉ fix symptom:

**Camera issues:**
- Freeze → kiểm tra `rtsp_transport` trong config.yaml (phải là `tcp`)
- Reconnect thất bại → kiểm tra `camera_manager.py` reconnect logic
- Black frame → camera URL sai hoặc stream chưa active

**AI Pipeline issues:**
- Model load fail → chạy `python setup_models.py`  
- Inference chậm → check nếu inference đang chạy trên main thread
- Wrong classification → kiểm tra threshold trong `config.yaml`

**WebSocket issues:**
- Disconnect → kiểm tra CORS settings trong `main.py`
- No updates → kiểm tra background task còn chạy không
- Wrong data format → so sánh với schema trong `AGENTS.md`

**Database issues:**
- Lock → kiểm tra có nhiều writer cùng lúc không
- Missing data → kiểm tra commit() sau write operations
- Schema mismatch → drop và recreate DB (`data/classroom.db`)

## Bước 4: Fix & Verify
1. Fix root cause (không chỉ suppress error)
2. Verify lỗi không còn reproduce
3. Verify không có regression (các test pass)
4. Document fix trong code comment nếu cần

## Common Fixes nhanh

| Triệu chứng | Fix nhanh |
|---|---|
| `Camera connection failed` | Kiểm tra config.yaml camera URL, đảm bảo rtsp_transport=tcp |
| `Model not found` | `python setup_models.py` |
| `head_down không count` | Kiểm tra `classroom_detector.py` state mapping |
| `WebSocket not connecting` | Kiểm tra port 8000 không bị firewall, CORS allow origins |
| `DB locked` | Restart backend, kiểm tra không có process nào giữ DB |
| `ImportError InsightFace` | `pip install insightface onnxruntime` |
