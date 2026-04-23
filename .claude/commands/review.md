Review code trước khi merge/commit — Quality gate cho classroom project.

## Checklist Review

### Correctness
- [ ] Logic đúng với spec/yêu cầu đã thảo luận?
- [ ] Edge cases được xử lý? (camera disconnect, no face detected, empty DB)
- [ ] Error handling có graceful fallback không?
- [ ] Không có hardcoded values (IP, credentials, thresholds)?

### Code Quality
- [ ] Function/variable names rõ ràng và nhất quán?
- [ ] Không có code thừa/dead code?
- [ ] Không có magic numbers — thay bằng constants/config?
- [ ] Comments giải thích "tại sao" chứ không phải "cái gì"?

### AI/ML Specific
- [ ] Model inference KHÔNG chạy trên main thread?
- [ ] Có handle model load failure gracefully?
- [ ] Threshold values có trong config.yaml, không hardcode?
- [ ] Embedding operations thread-safe?

### Database
- [ ] Có commit() sau write operations?
- [ ] Có close connection trong finally blocks?
- [ ] Không query N+1 (vòng lặp có query trong đó)?
- [ ] Pydantic validation trước khi ghi vào DB?

### API/WebSocket
- [ ] Response format nhất quán với schema trong AGENTS.md?
- [ ] Có validate input data?
- [ ] Không expose sensitive data (raw embeddings, internal paths)?
- [ ] WebSocket handler có cleanup khi disconnect?

### Frontend
- [ ] WebSocket reconnect khi mất kết nối?
- [ ] UI không crash khi nhận data format lạ?
- [ ] Charts cập nhật đúng khi nhận engagement_update?

### Testing
- [ ] Tính năng mới có test không?
- [ ] Tests run pass?
- [ ] Test cover happy path + error path?

## Red Flags — Yêu cầu sửa NGAY

🚨 **BLOCK** (không được merge):
- Credentials/IP hardcoded trong code
- Inference chạy trên main thread (làm freeze WebSocket)
- Unhandled exception có thể crash server
- SQL injection risk
- Raw embeddings exposed trong API response

⚠️ **WARN** (nên sửa):
- Magic numbers không có config
- Function > 50 lines (cần chia nhỏ)
- Missing error handling cho camera operations
- No logging cho AI pipeline errors
