Build tính năng theo plan đã được duyệt, từng bước nhỏ một.

Quy tắc incremental implementation cho classroom project:

1. **Làm từng task một** — KHÔNG implement nhiều thứ cùng lúc
2. **Test sau mỗi task** — Không đợi đến cuối mới test
3. **Commit từng milestone nhỏ** — Mỗi task hoàn thành = 1 commit

**Checklist trước khi bắt đầu implement:**
- [ ] Spec đã được duyệt?
- [ ] Plan đã có?
- [ ] Hiểu rõ file nào cần thay đổi?
- [ ] Biết cách verify task này hoạt động?

**Thứ tự ưu tiên:**
1. Database schema changes (luôn đầu tiên)
2. Backend models & business logic
3. API endpoints
4. AI/ML pipeline changes
5. WebSocket broadcasting
6. Frontend UI updates

**Verification sau mỗi task:**
```bash
# Backend vẫn start
python backend/main.py

# API vẫn trả response
# (dùng browser hoặc curl)

# Test cụ thể
python backend/test_crud.py
```

**Project-specific rules:**
- Sau khi thay đổi AI pipeline → test với webcam hoặc test video
- Sau khi thay đổi DB schema → chạy migration, kiểm tra data cũ còn nguyên
- Sau khi thay đổi WebSocket format → cập nhật app.js handler
- Sau khi thêm config → thêm vào config.yaml VÀ config.py loader

**Red flags — DỪNG LẠI nếu:**
- Backend crash khi start
- Camera disconnect không tự reconnect
- WebSocket ngừng gửi updates
- Inference time tăng đột biến (> 200ms/frame)
