Phân tích và chia nhỏ task thành các bước thực hiện cụ thể.

Dựa trên spec đã được duyệt (hoặc yêu cầu hiện tại), hãy tạo implementation plan:

1. **Phân tích dependencies** — Xác định thứ tự thực hiện:
   - Backend trước hay frontend trước?
   - Có cần thay đổi DB schema không? (DB changes luôn phải đi đầu)
   - AI model changes có ảnh hưởng đến pipeline không?

2. **Tạo task list** (checklist dạng `[ ]`) với:
   - Task nhỏ nhất có thể test được (<1 giờ mỗi task)
   - Ghi rõ file cần thay đổi
   - Ghi rõ cách verify từng task

3. **Estimate** (rough):
   - Nhỏ (S): < 30 phút
   - Vừa (M): 30 phút - 2 giờ
   - Lớn (L): > 2 giờ → cần chia nhỏ hơn

4. **Risk assessment**:
   - Task nào có thể break camera pipeline?
   - Task nào ảnh hưởng đến WebSocket clients?
   - Task nào cần test với camera thật?

**Template output:**
```
## Plan: [Feature Name]

### Tasks
- [ ] [BACKEND] Thêm endpoint POST /api/xxx (M) — backend/main.py
- [ ] [DB] Tạo bảng xxx trong database.py (S) — backend/database.py  
- [ ] [AI] Tích hợp model xxx vào pipeline (L) — backend/xxx.py
- [ ] [FRONTEND] Cập nhật dashboard để hiển thị (M) — app.js
- [ ] [TEST] Viết test cho endpoint mới (S) — test_integration.py

### Verification steps
1. python backend/main.py → không có lỗi
2. curl GET /api/xxx → 200 OK
3. WebSocket vẫn nhận updates
```
