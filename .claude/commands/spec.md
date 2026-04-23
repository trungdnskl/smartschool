Khởi động spec workflow cho tính năng/thay đổi mới trong dự án classroom.

Trước khi viết bất kỳ code nào, hãy:

1. **Làm rõ yêu cầu** — Hỏi những câu hỏi cần thiết để hiểu rõ:
   - Tính năng này giải quyết vấn đề gì?
   - Ai sẽ dùng nó? (giáo viên / admin / hệ thống tự động)
   - Acceptance criteria là gì? (làm thế nào để biết đã xong?)
   - Có ảnh hưởng đến camera pipeline / AI models / database không?

2. **Viết spec** (RFC ngắn gọn) với:
   - **Problem**: Vấn đề cần giải quyết
   - **Solution**: Cách tiếp cận
   - **Changes Required**: File nào cần thay đổi (backend/frontend/AI/DB)
   - **Acceptance Criteria**: Điều kiện để feature được coi là hoàn thành
   - **Out of Scope**: Những gì KHÔNG làm trong lần này

3. **Xác nhận với user** trước khi tiến hành implement

4. Sau khi spec được duyệt → chạy `/plan` để breakdown tasks

**Lưu ý cho project classroom:**
- Nếu feature ảnh hưởng đến AI pipeline → document model/performance tradeoffs
- Nếu thay đổi API/WebSocket → cập nhật AGENTS.md (schema section)
- Nếu thêm config mới → luôn thêm vào `config.yaml`, không hard-code
