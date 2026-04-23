# ĐẶC TẢ YÊU CẦU PHẦN MỀM (SRS)
# HỆ THỐNG PHÂN TÍCH MỨC ĐỘ TIẾP NHẬN HỌC TẬP

**Software Requirements Specification**
**Classroom Engagement Analysis System**

---

| Thông tin | Chi tiết |
|-----------|----------|
| **Tên dự án** | Hệ thống thu thập mức độ tiếp nhận học tập dựa trên phát hiện cảm xúc và hành vi thời gian thực |
| **Phiên bản** | 1.0 |
| **Ngày tạo** | 11/04/2026 |
| **Trạng thái** | Hoàn thành |
| **Phân loại** | Hệ thống AI phân tích video thời gian thực |
| **Đối tượng** | Lớp học STEM bậc K-12 (Tiểu học đến Trung học) |

---

## MỤC LỤC

1. [Giới thiệu](#1-giới-thiệu)
2. [Mô tả tổng quát](#2-mô-tả-tổng-quát)
3. [Yêu cầu chức năng](#3-yêu-cầu-chức-năng)
4. [Yêu cầu phi chức năng](#4-yêu-cầu-phi-chức-năng)
5. [Kiến trúc hệ thống](#5-kiến-trúc-hệ-thống)
6. [Mô hình dữ liệu](#6-mô-hình-dữ-liệu)
7. [Đặc tả API](#7-đặc-tả-api)
8. [Giao diện người dùng](#8-giao-diện-người-dùng)
9. [Ràng buộc thiết kế](#9-ràng-buộc-thiết-kế)
10. [Tiêu chí chấp nhận](#10-tiêu-chí-chấp-nhận)
11. [Phụ lục](#11-phụ-lục)

---

## 1. GIỚI THIỆU

### 1.1 Mục đích

Tài liệu này mô tả đặc tả yêu cầu phần mềm (SRS) cho **Hệ thống Phân tích Mức độ Tiếp nhận Học tập** (Classroom Engagement Analysis System). Hệ thống sử dụng trí tuệ nhân tạo (AI) để phân tích video lớp học theo thời gian thực nhằm đánh giá mức độ tham gia của học sinh thông qua phân tích biểu cảm khuôn mặt, cảm xúc và hành vi.

Tài liệu phục vụ các đối tượng:
- Giáo viên và ban giám hiệu trường STEM K-12
- Đội ngũ phát triển phần mềm
- Đội ngũ kiểm thử (QA)
- Bộ phận đánh giá chất lượng giáo dục

### 1.2 Phạm vi

Hệ thống bao gồm các thành phần chính:

- **Module AI xử lý video**: Phát hiện khuôn mặt, nhận dạng cảm xúc, ước tính hướng nhìn, điểm danh tự động
- **Engine tính toán Engagement**: Đánh giá mức độ tham gia dựa trên trọng số đa tiêu chí
- **Dashboard trực tuyến**: Hiển thị dữ liệu thời gian thực cho giáo viên (giao diện Tiếng Việt)
- **Hệ thống cảnh báo**: Phát hiện và thông báo các tình huống cần can thiệp giảng dạy
- **Quản lý Camera IP**: Cấu hình và giám sát các nguồn video đầu vào
- **Cơ sở dữ liệu**: Lưu trữ lịch sử buổi học, điểm danh và phân tích

### 1.3 Thuật ngữ và từ viết tắt

| Thuật ngữ | Định nghĩa |
|-----------|------------|
| **Engagement** | Mức độ tham gia/tiếp nhận học tập của học sinh |
| **Face Detection** | Phát hiện khuôn mặt trong khung hình video |
| **Emotion Recognition** | Nhận dạng cảm xúc qua biểu cảm khuôn mặt |
| **Head Pose Estimation** | Ước tính hướng nhìn dựa trên vị trí đầu |
| **Attendance Tracking** | Theo dõi điểm danh tự động |
| **RTSP** | Real Time Streaming Protocol - giao thức truyền video thời gian thực |
| **FER** | Facial Emotion Recognition - nhận dạng cảm xúc khuôn mặt |
| **LBPH** | Local Binary Patterns Histograms - thuật toán nhận dạng khuôn mặt |
| **DNN** | Deep Neural Network - mạng nơ-ron sâu |
| **WebSocket** | Giao thức truyền dữ liệu hai chiều thời gian thực |
| **Dashboard** | Bảng điều khiển hiển thị thông tin trực quan |
| **K-12** | Hệ thống giáo dục từ lớp 1 đến lớp 12 |
| **STEM** | Science, Technology, Engineering, Mathematics |
| **CPU-only** | Chạy trên bộ xử lý trung tâm, không yêu cầu GPU |

### 1.4 Tài liệu tham chiếu

| STT | Tài liệu | Mô tả |
|-----|----------|-------|
| 1 | OpenCV Documentation | Thư viện xử lý ảnh và video |
| 2 | MediaPipe Face Mesh | Framework phát hiện 468 điểm khuôn mặt |
| 3 | FER Library | Thư viện nhận dạng cảm xúc |
| 4 | FastAPI Documentation | Framework API Python hiệu suất cao |
| 5 | FERPA Regulations | Luật bảo vệ quyền riêng tư giáo dục (Hoa Kỳ) |
| 6 | UNESCO AI in Education | Hướng dẫn sử dụng AI trong giáo dục |

---

## 2. MÔ TẢ TỔNG QUÁT

### 2.1 Bối cảnh sản phẩm

Trong môi trường giáo dục STEM hiện đại, việc đánh giá mức độ tham gia của học sinh truyền thống (quan sát bằng mắt, khảo sát, hỏi đáp) có nhiều hạn chế:

- **Chủ quan**: Phụ thuộc vào khả năng quan sát của giáo viên
- **Không toàn diện**: Không thể theo dõi tất cả học sinh cùng lúc
- **Thiếu dữ liệu lượng hóa**: Không có chỉ số đo lường cụ thể
- **Phản hồi chậm**: Không phát hiện kịp thời suy giảm tập trung

Hệ thống này giải quyết các vấn đề trên bằng cách sử dụng AI để phân tích video camera lớp học theo thời gian thực, cung cấp dữ liệu khách quan và liên tục về mức độ tham gia của từng học sinh.

### 2.2 Chức năng sản phẩm

```
┌─────────────────────────────────────────────────────────┐
│               HỆ THỐNG ENGAGEMENT                       │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │ Camera   │───▶│ AI       │───▶│ Engagement       │   │
│  │ IP/USB   │    │ Pipeline │    │ Engine           │   │
│  └──────────┘    └──────────┘    └──────────────────┘   │
│                       │                    │             │
│                       ▼                    ▼             │
│               ┌──────────┐        ┌──────────────┐      │
│               │ Điểm     │        │ Dashboard    │      │
│               │ Danh     │        │ (Tiếng Việt) │      │
│               └──────────┘        └──────────────┘      │
│                                          │              │
│                                          ▼              │
│                                   ┌──────────────┐      │
│                                   │ Cảnh báo &   │      │
│                                   │ Gợi ý GD     │      │
│                                   └──────────────┘      │
└─────────────────────────────────────────────────────────┘
```

**Các chức năng chính:**

| # | Chức năng | Mô tả |
|---|-----------|-------|
| F1 | Phát hiện khuôn mặt | Xác định vị trí và theo dõi khuôn mặt học sinh |
| F2 | Nhận dạng cảm xúc | Phân loại 7 cảm xúc cơ bản → 5 trạng thái học tập |
| F3 | Ước tính hướng nhìn | Xác định học sinh nhìn bảng, nhìn chỗ khác, hay cúi đầu |
| F4 | Điểm danh tự động | Nhận dạng khuôn mặt đã đăng ký → điểm danh |
| F5 | Tính toán Engagement | Kết hợp cảm xúc + hướng nhìn + hành vi → điểm engagement |
| F6 | Dashboard thời gian thực | Hiển thị dữ liệu tổng hợp trên bảng điều khiển web |
| F7 | Hệ thống cảnh báo | Phát cảnh báo khi phát hiện vấn đề |
| F8 | Quản lý Camera | Thêm, xóa, test, bật/dừng camera |
| F9 | Quản lý học sinh | Đăng ký, quản lý danh sách, consent phụ huynh |
| F10 | Phân tích sau giờ | Báo cáo, timeline, gợi ý cải thiện |

### 2.3 Đặc điểm người dùng

| Người dùng | Vai trò | Kỹ năng yêu cầu |
|-----------|---------|------------------|
| **Giáo viên** | Sử dụng dashboard để theo dõi engagement, bắt đầu/kết thúc buổi học, xem báo cáo | Sử dụng trình duyệt web cơ bản |
| **Quản trị viên IT** | Cài đặt hệ thống, cấu hình camera, quản lý học sinh | Cài đặt phần mềm, cấu hình mạng LAN cơ bản |
| **Ban giám hiệu** | Xem báo cáo tổng hợp sau giờ học | Đọc hiểu dữ liệu giáo dục |

### 2.4 Ràng buộc tổng quát

| Ràng buộc | Chi tiết |
|-----------|----------|
| **Phần cứng** | Chạy trên CPU-only (không yêu cầu GPU NVIDIA) |
| **Ngôn ngữ** | Giao diện dashboard hoàn toàn bằng Tiếng Việt |
| **Nguồn video** | Camera IP (RTSP), Webcam USB, File video, HTTP Stream |
| **Quyền riêng tư** | Xử lý local-only, không gửi dữ liệu lên cloud |
| **Đạo đức** | Yêu cầu sự đồng ý của phụ huynh/giám hộ |

### 2.5 Giả định và phụ thuộc

- Lớp học được chiếu sáng đầy đủ (ánh sáng tự nhiên hoặc đèn)
- Camera lắp đặt ở vị trí nhìn rõ khuôn mặt học sinh (phía trước bảng)
- Máy tính chạy hệ thống và camera cùng mạng LAN
- Máy tính đáp ứng cấu hình tối thiểu (CPU 4 cores, RAM 8GB)
- Python 3.9+ đã được cài đặt trên máy tính

---

## 3. YÊU CẦU CHỨC NĂNG

### 3.1 FR-01: Phát hiện khuôn mặt (Face Detection)

**Mô tả**: Hệ thống phải phát hiện tất cả khuôn mặt trong khung hình video từ camera.

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| FR-01.1 | Phát hiện đồng thời tối đa 40 khuôn mặt trong 1 khung hình | Cao |
| FR-01.2 | Sử dụng mô hình OpenCV DNN (SSD) tối ưu cho CPU | Cao |
| FR-01.3 | Ngưỡng tin cậy (confidence) mặc định ≥ 60% | Cao |
| FR-01.4 | Duy trì theo dõi (tracking) ID khuôn mặt giữa các frame bằng IoU matching | Cao |
| FR-01.5 | Tự động tải model AI khi lần đầu khởi chạy | Trung bình |
| FR-01.6 | Cắt (crop) vùng khuôn mặt để truyền cho module cảm xúc | Cao |
| FR-01.7 | Xử lý frame skip (mỗi N frames) để tối ưu hiệu năng CPU | Cao |

**Đầu vào**: Khung hình video (numpy array BGR)

**Đầu ra**:
```json
{
  "faces": [
    {
      "face_id": 1,
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.95,
      "face_crop": "<numpy array>"
    }
  ],
  "total_detected": 25
}
```

### 3.2 FR-02: Nhận dạng cảm xúc (Emotion Recognition)

**Mô tả**: Hệ thống phải phân tích cảm xúc từ khuôn mặt được phát hiện.

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| FR-02.1 | Nhận dạng 7 cảm xúc cơ bản: Happy, Sad, Angry, Surprise, Fear, Disgust, Neutral | Cao |
| FR-02.2 | Ánh xạ 7 cảm xúc → 5 trạng thái học tập (Tích cực, Bình thường, Bối rối, Chán nản, Thất vọng) | Cao |
| FR-02.3 | Áp dụng sliding window smoothing (cửa sổ 5 frames) để giảm nhiễu | Trung bình |
| FR-02.4 | Cập nhật cảm xúc mỗi 2 giây (có thể cấu hình) | Trung bình |
| FR-02.5 | Cung cấp fallback rule-based khi model FER không khả dụng | Trung bình |
| FR-02.6 | Trả về tên cảm xúc và trạng thái học tập bằng Tiếng Việt | Cao |

**Bảng ánh xạ cảm xúc → Trạng thái học tập:**

| Cảm xúc (EN) | Cảm xúc (VI) | Trạng thái học tập | Emoji |
|--------------|--------------|--------------------|----|
| Happy | Vui vẻ | Tích cực (Engaged) | 😊 |
| Neutral | Bình thường | Bình thường (Neutral) | 😐 |
| Surprise | Ngạc nhiên | Bối rối (Confused) | 😲 |
| Sad | Buồn | Chán nản (Bored) | 😢 |
| Angry | Tức giận | Thất vọng (Frustrated) | 😠 |
| Fear | Sợ hãi | Bối rối (Confused) | 😨 |
| Disgust | Khó chịu | Thất vọng (Frustrated) | 😖 |

### 3.3 FR-03: Ước tính hướng nhìn (Head Pose Estimation)

**Mô tả**: Hệ thống phải xác định hướng nhìn của học sinh để đánh giá mức độ chú ý.

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| FR-03.1 | Ước tính 3 góc quay đầu: Yaw (xoay ngang), Pitch (ngẩng/cúi), Roll (nghiêng) | Cao |
| FR-03.2 | Phân loại hướng nhìn thành 4 trạng thái: Nhìn bảng/GV, Nhìn chỗ khác, Cúi đầu, Gục đầu | Cao |
| FR-03.3 | Sử dụng MediaPipe Face Mesh (468 landmarks) khi khả dụng | Cao |
| FR-03.4 | Fallback sang OpenCV solvePnP khi MediaPipe không cài đặt | Trung bình |
| FR-03.5 | Ngưỡng phát hiện chú ý: Yaw ≤ 25°, Pitch trong khoảng [-15°, 20°] | Trung bình |

**Bảng ngưỡng hướng nhìn:**

| Trạng thái | Yaw (°) | Pitch (°) | Mô tả |
|-----------|---------|-----------|-------|
| Nhìn bảng/GV | ≤ 25 | -15 đến 20 | Học sinh đang tập trung |
| Nhìn chỗ khác | > 25 | bất kỳ | Mất tập trung, nhìn sang bạn |
| Cúi đầu | bất kỳ | < -30 | Có thể nhìn điện thoại hoặc viết |
| Gục đầu | bất kỳ | < -45 | Có thể ngủ gật |

### 3.4 FR-04: Điểm danh tự động (Attendance Tracking)

**Mô tả**: Hệ thống phải tự động nhận dạng và điểm danh học sinh đã đăng ký.

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| FR-04.1 | Nhận dạng khuôn mặt bằng thuật toán LBPH Histogram | Cao |
| FR-04.2 | Cho phép đăng ký khuôn mặt học sinh qua ảnh upload hoặc camera trực tiếp | Cao |
| FR-04.3 | Lưu embedding dưới dạng histogram JSON (không lưu ảnh gốc) | Cao |
| FR-04.4 | Tự động đánh dấu trạng thái: Có mặt / Muộn / Vắng | Cao |
| FR-04.5 | Ngưỡng muộn mặc định: 10 phút sau khi bắt đầu buổi học | Trung bình |
| FR-04.6 | Kiểm tra điểm danh định kỳ mỗi 30 giây | Trung bình |
| FR-04.7 | Ngưỡng so khớp khuôn mặt mặc định: 0.6 (60% similarity) | Trung bình |
| FR-04.8 | Hỗ trợ mã hóa embedding khi lưu trữ | Thấp |

### 3.5 FR-05: Tính toán Engagement (Engagement Engine)

**Mô tả**: Hệ thống phải kết hợp các chỉ số cảm xúc, hướng nhìn và hành vi để tính điểm engagement tổng hợp.

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| FR-05.1 | Tính điểm Engagement Scale (0-100) cho từng học sinh | Cao |
| FR-05.2 | Tính điểm trung bình lớp học (Class Average Engagement) | Cao |
| FR-05.3 | Áp dụng công thức trọng số: `Score = w1×Emotion + w2×Attention + w3×Behavior` | Cao |
| FR-05.4 | Trọng số mặc định: Emotion=0.35, Attention=0.45, Behavior=0.20 | Cao |
| FR-05.5 | Phát cảnh báo khi engagement TB lớp < 40% | Cao |
| FR-05.6 | Tạo gợi ý giảng dạy dựa trên phân bố cảm xúc và hướng nhìn | Trung bình |
| FR-05.7 | Cập nhật engagement mỗi 2 giây (có thể cấu hình) | Trung bình |

**Công thức tính Engagement Score:**

```
Engagement_Score(i) = w_emotion × EmotionScore(i) 
                    + w_attention × AttentionScore(i) 
                    + w_behavior × BehaviorScore(i)

Trong đó:
  - EmotionScore: 0-100 dựa trên cảm xúc (happy=90, neutral=50, sad=20, ...)
  - AttentionScore: 0-100 dựa trên hướng nhìn (nhìn bảng=100, nhìn khác=30, ...)
  - BehaviorScore: 0-100 dựa trên hành vi (tham gia tích cực=90, thụ động=40, ...)
  - w_emotion = 0.35, w_attention = 0.45, w_behavior = 0.20
```

**Bảng phân loại engagement:**

| Mức | Điểm | Mô tả | Màu sắc |
|-----|-------|-------|---------|
| Xuất sắc | 80-100 | Học sinh rất tích cực, chú ý | 🟢 Xanh lá |
| Tốt | 60-79 | Học sinh tham gia bình thường | 🟡 Vàng xanh |
| Trung bình | 40-59 | Có dấu hiệu mất tập trung | 🟠 Cam |
| Thấp | 20-39 | Mất tập trung đáng kể | 🔴 Đỏ |
| Rất thấp | 0-19 | Không tham gia, cần can thiệp | ⚫ Đỏ đậm |

### 3.6 FR-06: Hệ thống cảnh báo (Alert System)

**Mô tả**: Hệ thống phải phát cảnh báo tự động khi phát hiện tình huống cần can thiệp.

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| FR-06.1 | Cảnh báo khi engagement TB lớp giảm dưới ngưỡng (< 40%) | Cao |
| FR-06.2 | Cảnh báo khi phát hiện học sinh bối rối kéo dài (> 120 giây) | Cao |
| FR-06.3 | Cảnh báo khi > 30% lớp chán nản/thất vọng | Cao |
| FR-06.4 | Cảnh báo khi attention giảm đột ngột (> 3 học sinh nhìn chỗ khác cùng lúc) | Trung bình |
| FR-06.5 | Cảnh báo khi phát hiện ngủ gật (gục đầu > 30 giây) | Trung bình |
| FR-06.6 | Thông báo khi engagement phục hồi sau đợt suy giảm | Thấp |
| FR-06.7 | Hiển thị cảnh báo dạng toast notification trên dashboard | Cao |
| FR-06.8 | Kèm gợi ý can thiệp giảng dạy bằng Tiếng Việt | Trung bình |

**Danh sách loại cảnh báo:**

| Loại | Mức độ | Tin nhắn mẫu | Gợi ý |
|------|--------|-------------|-------|
| LOW_ENGAGEMENT | critical | "⚠ Mức tham gia lớp thấp: 35%" | "Thử thay đổi hoạt động hoặc đặt câu hỏi tương tác" |
| CONFUSION | warning | "🤔 Nhiều HS bối rối (40%)" | "Nên giải thích lại khái niệm vừa đề cập" |
| BOREDOM | warning | "😴 35% HS chán nản" | "Thử hoạt động nhóm hoặc ví dụ thực tế" |
| ATTENTION_DROP | warning | "👀 Nhiều HS mất tập trung" | "Thu hút sự chú ý bằng câu hỏi bất ngờ" |
| SLEEPING | critical | "💤 Phát hiện HS ngủ gật" | "Kiểm tra tình trạng sức khỏe HS" |
| RECOVERY | info | "✅ Engagement đã phục hồi" | — |

### 3.7 FR-07: Dashboard trực tuyến (Web Dashboard)

**Mô tả**: Hệ thống phải cung cấp bảng điều khiển web hiển thị dữ liệu theo thời gian thực.

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| FR-07.1 | Hiển thị gauge chart mức engagement tổng lớp (0-100%) | Cao |
| FR-07.2 | Hiển thị biểu đồ thanh phân bố cảm xúc (6 loại) | Cao |
| FR-07.3 | Hiển thị biểu đồ timeline engagement theo thời gian | Cao |
| FR-07.4 | Hiển thị danh sách cảnh báo gần đây (tối đa 10) | Cao |
| FR-07.5 | Hiển thị phân bố trạng thái học tập (5 loại) | Cao |
| FR-07.6 | Hiển thị phân bố hướng nhìn (4 loại) | Trung bình |
| FR-07.7 | Cập nhật dữ liệu tự động qua WebSocket (không cần reload trang) | Cao |
| FR-07.8 | Hỗ trợ 7 views: Tổng quan, Điểm danh, Cảm xúc, Phân tích, Camera, Học sinh, Cài đặt | Cao |
| FR-07.9 | Giao diện dark theme premium, đều bằng Tiếng Việt | Cao |
| FR-07.10 | Responsive trên màn hình 1366x768 trở lên | Trung bình |

### 3.8 FR-08: Quản lý Camera (Camera Management)

**Mô tả**: Hệ thống phải cho phép quản trị viên cấu hình và giám sát các nguồn video.

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| FR-08.1 | Hỗ trợ 4 loại nguồn video: Camera IP (RTSP), Webcam USB, File Video, HTTP Stream | Cao |
| FR-08.2 | Thêm camera mới từ giao diện web (ID, tên, URL, loại) | Cao |
| FR-08.3 | Xóa camera từ giao diện web (cần xác nhận) | Cao |
| FR-08.4 | Bật/Dừng từng camera riêng lẻ | Cao |
| FR-08.5 | Kiểm tra kết nối camera trước khi thêm (Test Connection) | Cao |
| FR-08.6 | Hiển thị trạng thái camera: Đang chạy / Đã dừng / Lỗi / Mất kết nối | Cao |
| FR-08.7 | Hiển thị thông số: FPS, số frames đã xử lý, thời gian frame cuối | Trung bình |
| FR-08.8 | Cung cấp mẫu URL nhanh cho các hãng: Hikvision, Dahua, KBVISION, Tapo, EZVIZ | Trung bình |
| FR-08.9 | Tự động kết nối lại khi mất tín hiệu camera (tối đa 10 lần) | Trung bình |
| FR-08.10 | Hiển thị badge loại nguồn (Webcam USB / Camera IP / HTTP / File) | Thấp |
| FR-08.11 | Ẩn mật khẩu trong URL RTSP khi hiển thị (masking) | Trung bình |

### 3.9 FR-09: Quản lý buổi học (Session Management)

**Mô tả**: Hệ thống phải quản lý vòng đời buổi học.

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| FR-09.1 | Bắt đầu buổi học mới: nhập môn học, giáo viên, tên lớp | Cao |
| FR-09.2 | Kết thúc buổi học: dừng camera, tạo tóm tắt | Cao |
| FR-09.3 | Tự động bắt đầu camera khi bắt đầu buổi học | Cao |
| FR-09.4 | Bộ đếm thời gian thời lượng buổi học (HH:MM:SS) | Trung bình |
| FR-09.5 | Chỉ cho phép 1 buổi học hoạt động tại 1 thời điểm | Cao |
| FR-09.6 | Lưu lịch sử tất cả buổi học vào cơ sở dữ liệu | Cao |

### 3.10 FR-10: Phân tích sau giờ học (Post-session Analytics)

**Mô tả**: Hệ thống phải cung cấp phân tích tổng hợp sau mỗi buổi học.

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| FR-10.1 | Tóm tắt: engagement TB, đỉnh cao, thấp nhất, thời lượng | Cao |
| FR-10.2 | Biểu đồ engagement theo thời gian cho cả buổi học | Cao |
| FR-10.3 | Thống kê điểm danh: có mặt, muộn, vắng | Cao |
| FR-10.4 | Số lượng cảnh báo phát sinh | Trung bình |
| FR-10.5 | Danh sách gợi ý cải thiện giảng dạy | Trung bình |
| FR-10.6 | Cho phép chọn buổi học cũ để xem lại phân tích | Trung bình |

---

## 4. YÊU CẦU PHI CHỨC NĂNG

### 4.1 NFR-01: Hiệu năng (Performance)

| ID | Yêu cầu | Chỉ tiêu | Ưu tiên |
|----|----------|-----------|---------|
| NFR-01.1 | Thời gian xử lý mỗi frame (face detection + emotion + head pose) | ≤ 200ms trên CPU | Cao |
| NFR-01.2 | Frame skip tối thiểu | Xử lý mỗi 3 frames (có thể cấu hình) | Cao |
| NFR-01.3 | Độ trễ từ camera → dashboard | ≤ 3 giây | Cao |
| NFR-01.4 | Số khuôn mặt đồng thời tối đa | 40 khuôn mặt | Trung bình |
| NFR-01.5 | WebSocket latency | ≤ 500ms | Cao |
| NFR-01.6 | Sử dụng RAM tối đa | ≤ 2GB (không tính OS) | Trung bình |
| NFR-01.7 | Sử dụng CPU trung bình | ≤ 60% (4-core CPU) | Trung bình |

### 4.2 NFR-02: Độ chính xác (Accuracy)

| ID | Yêu cầu | Chỉ tiêu |
|----|----------|-----------|
| NFR-02.1 | Độ chính xác phát hiện khuôn mặt | ≥ 90% (điều kiện chiếu sáng tốt) |
| NFR-02.2 | Độ chính xác nhận dạng cảm xúc | ≥ 65% (7 lớp) |
| NFR-02.3 | Độ chính xác ước tính hướng nhìn | ≥ 80% (4 trạng thái) |
| NFR-02.4 | Độ chính xác điểm danh | ≥ 85% (đã đăng ký khuôn mặt) |
| NFR-02.5 | Tỷ lệ dương tính giả (false positive) cho cảnh báo | ≤ 15% |

### 4.3 NFR-03: Bảo mật và Quyền riêng tư (Security & Privacy)

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| NFR-03.1 | Xử lý dữ liệu hoàn toàn local (không gửi lên cloud/internet) | Cao |
| NFR-03.2 | Không lưu trữ ảnh khuôn mặt gốc (chỉ lưu histogram embedding) | Cao |
| NFR-03.3 | Hỗ trợ mã hóa embedding khi lưu trữ | Trung bình |
| NFR-03.4 | Yêu cầu xác nhận đồng ý (consent) từ phụ huynh/giám hộ | Cao |
| NFR-03.5 | Chính sách lưu trữ dữ liệu: mặc định 90 ngày, sau đó tự xóa | Trung bình |
| NFR-03.6 | Ẩn danh hóa dữ liệu trong báo cáo xuất ra | Trung bình |
| NFR-03.7 | Mật khẩu camera RTSP được ẩn (masking) trên giao diện | Trung bình |

### 4.4 NFR-04: Khả dụng và Tin cậy (Availability & Reliability)

| ID | Yêu cầu | Chỉ tiêu |
|----|----------|-----------|
| NFR-04.1 | Thời gian khởi động hệ thống | ≤ 30 giây (sau lần đầu tải model) |
| NFR-04.2 | Khả năng tự phục hồi kết nối camera | Tự kết nối lại tối đa 10 lần, delay 5s |
| NFR-04.3 | Fallback khi thiếu thư viện | Sử dụng rule-based thay cho ML model |
| NFR-04.4 | Database persistence | SQLite, dữ liệu không mất khi restart |
| NFR-04.5 | WebSocket reconnect | Tự kết nối lại sau 3 giây khi mất kết nối |

### 4.5 NFR-05: Khả năng sử dụng (Usability)

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| NFR-05.1 | Giao diện hoàn toàn bằng Tiếng Việt | Cao |
| NFR-05.2 | Không yêu cầu đào tạo kỹ thuật cho giáo viên | Cao |
| NFR-05.3 | Dark theme premium, dễ đọc trong phòng học tối | Trung bình |
| NFR-05.4 | Thời gian tải trang dashboard | ≤ 3 giây | Trung bình |
| NFR-05.5 | Thao tác bắt đầu/kết thúc buổi học | ≤ 2 click | Cao |

### 4.6 NFR-06: Khả năng mở rộng (Scalability)

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| NFR-06.1 | Hỗ trợ tối đa 4 camera đồng thời | Trung bình |
| NFR-06.2 | Hỗ trợ lớp học 35-40 học sinh | Cao |
| NFR-06.3 | Cấu hình linh hoạt qua file YAML | Trung bình |
| NFR-06.4 | Kiến trúc module hóa, dễ thay đổi model AI | Trung bình |

### 4.7 NFR-07: Khả năng triển khai (Deployability)

| ID | Yêu cầu | Ưu tiên |
|----|----------|---------|
| NFR-07.1 | Cài đặt bằng 1 lệnh: `pip install -r requirements.txt` | Cao |
| NFR-07.2 | Khởi chạy bằng 1 file: `start_classroom.bat` (Windows) | Cao |
| NFR-07.3 | Tự động tải model AI khi lần đầu chạy | Trung bình |
| NFR-07.4 | Không yêu cầu Docker, container, hoặc cloud service | Cao |
| NFR-07.5 | Tương thích: Windows 10/11, Python 3.9+ | Cao |

---

## 5. KIẾN TRÚC HỆ THỐNG

### 5.1 Sơ đồ kiến trúc tổng thể

```
┌───────────────────────────────────────────────────────────────┐
│                      FRONTEND (Browser)                      │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────────┐   │
│  │index.html│  │styles.css│  │ app.js  │  │ WebSocket    │   │
│  │(7 views)│  │(dark UI) │  │(logic)  │  │ Client       │   │
│  └─────────┘  └──────────┘  └─────────┘  └──────┬───────┘   │
└──────────────────────────────────────────────────┼───────────┘
                                                   │ ws://
┌──────────────────────────────────────────────────┼───────────┐
│                   BACKEND (FastAPI)               │           │
│  ┌────────────────────────┐   ┌──────────────────┼────────┐  │
│  │    REST API Layer      │   │  WebSocket Server │        │  │
│  │  /api/sessions/*       │   │  /ws              │        │  │
│  │  /api/cameras/*        │   │                   │        │  │
│  │  /api/students/*       │   └───────────────────┘        │  │
│  │  /api/engagement/*     │                                │  │
│  │  /api/attendance/*     │                                │  │
│  └────────────────────────┘                                │  │
│                                                            │  │
│  ┌──────────────────── AI PIPELINE ────────────────────┐   │  │
│  │                                                      │   │  │
│  │  Camera ─→ Face ─→ Emotion ─→ Head ─→ Attendance    │   │  │
│  │  Manager   Detector  Recognizer  Pose   Tracker     │   │  │
│  │                        │          │         │        │   │  │
│  │                        └──────────┴─────────┘        │   │  │
│  │                               │                      │   │  │
│  │                        ┌──────▼──────┐               │   │  │
│  │                        │ Engagement  │               │   │  │
│  │                        │ Engine      │               │   │  │
│  │                        └─────────────┘               │   │  │
│  └──────────────────────────────────────────────────────┘   │  │
│                                                            │  │
│  ┌────────────────┐   ┌──────────────┐                     │  │
│  │  config.yaml   │   │  SQLite DB   │                     │  │
│  │  config.py     │   │  database.py │                     │  │
│  └────────────────┘   └──────────────┘                     │  │
└────────────────────────────────────────────────────────────┘  │
                                                               │
┌──────────────────────────────────────────────────────────────┘
│               HARDWARE LAYER
│  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  │Camera IP │  │Webcam USB│  │File Video│
│  │(RTSP)    │  │(DirectX) │  │(.mp4)    │
│  └──────────┘  └──────────┘  └──────────┘
└──────────────────────────────────────────
```

### 5.2 Danh sách module

| Module | File | Kích thước | Chức năng |
|--------|------|-----------|-----------|
| Configuration | `config.py` + `config.yaml` | 4.6KB + 3.5KB | Tải cấu hình hệ thống |
| Data Models | `models.py` | 5KB | Định nghĩa Pydantic models |
| Database | `database.py` | 18KB | CRUD SQLite với aiosqlite |
| Camera Manager | `camera_manager.py` | 9.3KB | Quản lý RTSP/USB/File streams |
| Face Detector | `face_detector.py` | 10KB | OpenCV DNN face detection + tracking |
| Emotion Recognizer | `emotion_recognizer.py` | 10.4KB | FER emotion classification |
| Head Pose Estimator | `head_pose_estimator.py` | 10.8KB | MediaPipe/OpenCV head pose |
| Attendance Tracker | `attendance_tracker.py` | 11.5KB | LBPH face recognition |
| Engagement Engine | `engagement_engine.py` | 17KB | Weighted scoring + alerts |
| Master Pipeline | `classroom_detector.py` | 10KB | Orchestration pipeline |
| API Server | `main.py` | 22KB | FastAPI + WebSocket |
| Dashboard HTML | `index.html` | 27KB | 7-view Vietnamese dashboard |
| Dashboard CSS | `styles.css` | 28KB | Dark theme styles |
| Dashboard JS | `app.js` | 35KB | Frontend logic |

### 5.3 Luồng dữ liệu (Data Flow)

```
Camera Frame (BGR)
      │
      ▼
Face Detector (OpenCV DNN) ──→ Bounding boxes + Face crops
      │
      ├──→ Emotion Recognizer (FER) ──→ 7 emotions + learning state
      │
      ├──→ Head Pose Estimator (MediaPipe) ──→ yaw/pitch/roll + attention
      │
      └──→ Attendance Tracker (LBPH) ──→ student ID + status
      
      Tất cả kết quả gom lại
              │
              ▼
      Engagement Engine ──→ Score(0-100) + Alerts + Suggestions
              │
              ├──→ SQLite (lưu log buổi học)
              │
              └──→ WebSocket → Dashboard (hiển thị real-time)
```

---

## 6. MÔ HÌNH DỮ LIỆU

### 6.1 Sơ đồ ERD

```
┌─────────────────┐     ┌─────────────────────┐
│    sessions      │     │   engagement_logs    │
├─────────────────┤     ├─────────────────────┤
│ id (PK)         │◄───┤│ id (PK)             │
│ session_name    │     │ session_id (FK)      │
│ class_name      │     │ timestamp            │
│ subject         │     │ total_faces          │
│ teacher_name    │     │ avg_engagement       │
│ start_time      │     │ avg_emotion_score    │
│ end_time        │     │ avg_attention_score  │
│ status          │     │ emotion_distribution │
│ created_at      │     │ learning_states      │
└────────┬────────┘     │ attention_dist       │
         │              └─────────────────────┘
         │
         │         ┌─────────────────────┐
         ├────────►│    attendance        │
         │         ├─────────────────────┤
         │         │ id (PK)             │
         │         │ session_id (FK)     │
         │         │ student_id          │
         │         │ student_name        │
         │         │ status              │
         │         │ arrival_time        │
         │         └─────────────────────┘
         │
         │         ┌─────────────────────┐
         └────────►│    alerts            │
                   ├─────────────────────┤
                   │ id (PK)             │
                   │ session_id (FK)     │
                   │ alert_type          │
                   │ severity            │
                   │ message             │
                   │ suggestion          │
                   │ timestamp           │
                   └─────────────────────┘

┌─────────────────────┐     ┌─────────────────────┐
│    students          │     │  session_summaries   │
├─────────────────────┤     ├─────────────────────┤
│ id (PK)             │     │ id (PK)             │
│ student_id (unique) │     │ session_id (FK)     │
│ name                │     │ avg_engagement      │
│ class_name          │     │ peak_engagement     │
│ has_consent         │     │ lowest_engagement   │
│ enrolled_at         │     │ duration_minutes    │
└─────────────────────┘     │ present_count       │
                            │ alerts_count        │
                            │ recommendations     │
                            │ emotion_distribution│
                            └─────────────────────┘
```

### 6.2 Chi tiết bảng dữ liệu

#### 6.2.1 Bảng `sessions`

| Cột | Kiểu | Ràng buộc | Mô tả |
|-----|------|-----------|-------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã buổi học |
| session_name | TEXT | NOT NULL | Tên buổi học |
| class_name | TEXT | | Tên lớp |
| subject | TEXT | | Môn học |
| teacher_name | TEXT | | Tên giáo viên |
| start_time | TEXT | DEFAULT CURRENT_TIMESTAMP | Thời gian bắt đầu |
| end_time | TEXT | | Thời gian kết thúc |
| status | TEXT | DEFAULT 'active' | Trạng thái: active / ended |
| created_at | TEXT | DEFAULT CURRENT_TIMESTAMP | Thời gian tạo |

#### 6.2.2 Bảng `engagement_logs`

| Cột | Kiểu | Ràng buộc | Mô tả |
|-----|------|-----------|-------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã log |
| session_id | INTEGER | FOREIGN KEY → sessions(id) | Buổi học |
| timestamp | TEXT | NOT NULL | Thời điểm ghi nhận |
| total_faces | INTEGER | DEFAULT 0 | Số khuôn mặt phát hiện |
| avg_engagement | REAL | DEFAULT 0 | Engagement TB (0-100) |
| avg_emotion_score | REAL | DEFAULT 0 | Điểm cảm xúc TB |
| avg_attention_score | REAL | DEFAULT 0 | Điểm chú ý TB |
| emotion_distribution | TEXT | | JSON phân bố cảm xúc |
| learning_state_distribution | TEXT | | JSON phân bố trạng thái |
| attention_distribution | TEXT | | JSON phân bố hướng nhìn |

#### 6.2.3 Bảng `students`

| Cột | Kiểu | Ràng buộc | Mô tả |
|-----|------|-----------|-------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Mã nội bộ |
| student_id | TEXT | UNIQUE NOT NULL | Mã học sinh (VD: HS001) |
| name | TEXT | NOT NULL | Họ tên |
| class_name | TEXT | | Tên lớp |
| has_consent | INTEGER | DEFAULT 0 | Phụ huynh đã đồng ý (0/1) |
| enrolled_at | TEXT | DEFAULT CURRENT_TIMESTAMP | Ngày đăng ký |

---

## 7. ĐẶC TẢ API

### 7.1 Tổng quan API

| Phương thức | Endpoint | Mô tả |
|------------|----------|-------|
| POST | `/api/sessions/start` | Bắt đầu buổi học |
| POST | `/api/sessions/stop` | Kết thúc buổi học |
| GET | `/api/sessions` | Danh sách buổi học |
| GET | `/api/sessions/active` | Buổi học đang hoạt động |
| GET | `/api/sessions/{id}` | Chi tiết buổi học |
| GET | `/api/sessions/{id}/summary` | Tóm tắt buổi học |
| GET | `/api/sessions/{id}/engagement` | Timeline engagement |
| GET | `/api/sessions/{id}/attendance` | Điểm danh buổi học |
| GET | `/api/sessions/{id}/alerts` | Cảnh báo buổi học |
| GET | `/api/engagement/current` | Engagement hiện tại |
| GET | `/api/attendance/current` | Điểm danh hiện tại |
| GET | `/api/cameras` | Danh sách camera |
| POST | `/api/cameras` | Thêm camera mới |
| POST | `/api/cameras/test` | Kiểm tra kết nối camera |
| POST | `/api/cameras/{id}/start` | Bật camera |
| POST | `/api/cameras/{id}/stop` | Dừng camera |
| DELETE | `/api/cameras/{id}` | Xóa camera |
| GET | `/api/students` | Danh sách học sinh |
| POST | `/api/students/enroll` | Đăng ký học sinh |
| POST | `/api/students/enroll-camera` | Đăng ký từ camera |
| GET | `/api/stats` | Thống kê hệ thống |
| WS | `/ws` | WebSocket thời gian thực |

### 7.2 Chi tiết API quan trọng

#### 7.2.1 POST /api/sessions/start

**Request Body (JSON):**
```json
{
  "session_name": "Buổi học 11/04/2026",
  "subject": "Toán học",
  "teacher_name": "Nguyễn Văn A",
  "class_name": "10A1"
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "session_id": 1,
  "message": "Buổi học đã bắt đầu"
}
```

**Error Response (400):**
```json
{
  "detail": "Đã có buổi học đang diễn ra. Hãy kết thúc trước."
}
```

#### 7.2.2 POST /api/cameras/test

**Request Body (Form Data):**
```
url: rtsp://admin:pass@192.168.1.100:554/stream1
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Kết nối thành công! Độ phân giải: 1920x1080",
  "resolution": "1920x1080"
}
```

#### 7.2.3 WebSocket /ws

**Server → Client Messages:**

```json
// Engagement Update
{
  "type": "engagement_update",
  "data": {
    "timestamp": "2026-04-11T10:30:00",
    "total_faces": 25,
    "avg_engagement": 72.5,
    "emotion_distribution": {"happy": 10, "neutral": 8, "sad": 3, "surprise": 2, "angry": 1, "fear": 1},
    "learning_state_distribution": {"engaged": 12, "neutral": 6, "confused": 3, "bored": 2, "frustrated": 2},
    "attention_distribution": {"looking_at_teacher": 18, "looking_away": 4, "looking_down": 2, "head_down": 1},
    "students": [
      {
        "face_id": 1,
        "emotion": "happy",
        "emotion_vi": "Vui vẻ",
        "learning_state": "engaged",
        "learning_state_vi": "Tích cực",
        "attention_direction": "looking_at_teacher",
        "attention_direction_vi": "Nhìn bảng/GV",
        "engagement_score": 85,
        "student_name": "Nguyễn Văn A"
      }
    ],
    "process_time_ms": 150
  }
}

// Alert
{
  "type": "alert",
  "data": {
    "alert_type": "LOW_ENGAGEMENT",
    "severity": "critical",
    "message": "⚠ Mức tham gia lớp thấp: 35%",
    "suggestion": "Thử thay đổi hoạt động hoặc đặt câu hỏi tương tác",
    "timestamp": "2026-04-11T10:35:00"
  }
}

// Session Status
{
  "type": "session_status",
  "data": {
    "status": "started",
    "session_id": 1
  }
}

// Heartbeat (mỗi 30 giây)
{
  "type": "heartbeat",
  "data": {
    "session_active": true,
    "active_cameras": 2,
    "avg_engagement": 72.5,
    "total_faces": 25
  }
}
```

---

## 8. GIAO DIỆN NGƯỜI DÙNG

### 8.1 Tổng quan giao diện

| Thành phần | Mô tả |
|-----------|-------|
| **Title Bar** | Logo, tên hệ thống, bộ đếm thời gian, trạng thái kết nối, avatar GV |
| **Sidebar** | 7 nút điều hướng dọc: Tổng quan, Điểm danh, Cảm xúc, Phân tích, Camera, Học sinh, Cài đặt |
| **Content Area** | Vùng nội dung chính, thay đổi theo view được chọn |
| **Toast Container** | Vùng hiển thị thông báo (góc phải dưới) |

### 8.2 Chi tiết các Views

#### View 1: Tổng quan (Dashboard)

```
┌────────────────────────────────────────────────────────────┐
│ [Môn học: ____] [Giáo viên: ____]    [▶ Bắt đầu buổi học] │
├────────┬───────────┬───────────┬───────────────────────────┤
│📊 0%   │👤 0       │✅ 0       │🔔 0                       │
│Mức TG  │Khuôn mặt  │Có mặt    │Cảnh báo                  │
├────────┴───────────┼───────────┴───────────────────────────┤
│  Gauge Chart       │  Phân bố cảm xúc                     │
│  (Engagement 0%)   │  😊 Vui vẻ    ━━━━━━ 0               │
│                    │  😐 Bình thường━━━━ 0                 │
│                    │  😲 Ngạc nhiên ━━ 0                   │
│                    │  😢 Buồn       ━ 0                    │
│                    │  😠 Tức giận   ━ 0                    │
│                    │  😨 Sợ hãi     ━ 0                    │
├────────────────────┼───────────────────────────────────────┤
│  Trạng thái học tập│  Phân bố hướng nhìn                   │
│  🎯 Tích cực: 0   │  👀 Nhìn bảng: 0  📱 Cúi đầu: 0      │
│  😐 Bình thường: 0│  👈 Nhìn khác: 0  💤 Gục đầu: 0      │
│  🤔 Bối rối: 0    │                                       │
│  😴 Chán nản: 0   │                                       │
│  😤 Thất vọng: 0  │                                       │
├────────────────────┴───────────────────────────────────────┤
│  Timeline Engagement (biểu đồ đường)                      │
├────────────────────────────────────────────────────────────┤
│  Cảnh báo gần đây                                         │
│  [HH:MM] ⚠ Nội dung cảnh báo...                          │
└────────────────────────────────────────────────────────────┘
```

#### View 5: Quản lý Camera

```
┌────────────────────────────────────────────────────────────┐
│  📹 Quản lý Camera                     [+ Thêm Camera]    │
├────────────────────────────────────────────────────────────┤
│  📷 Tổng: 2  ● Đang chạy: 1  ● Dừng: 1  ● Lỗi: 0       │
├────────────────────┬───────────────────────────────────────┤
│  ┌───────────────┐ │  ┌───────────────┐                    │
│  │ [Webcam USB]  │ │  │ [Camera IP]   │                    │
│  │   🖥️          │ │  │   📡          │                    │
│  │ ● Đang chạy   │ │  │ ● Đã dừng    │                    │
│  │───────────────│ │  │───────────────│                    │
│  │Camera trước   │ │  │Camera sau    │                    │
│  │cam_front      │ │  │cam_rear      │                    │
│  │URL: 0         │ │  │URL: rtsp://..│                    │
│  │FPS:15 Frames:2K│ │  │FPS:0 Frames:0│                   │
│  │[⏹ Dừng][Test]│ │  │[▶ Chạy][Test]│                    │
│  └───────────────┘ │  └───────────────┘                    │
├────────────────────┴───────────────────────────────────────┤
│  💡 Hướng dẫn kết nối Camera IP            [Mở rộng]      │
└────────────────────────────────────────────────────────────┘
```

### 8.3 Thiết kế giao diện

| Thuộc tính | Giá trị |
|-----------|---------|
| **Theme** | Dark theme (Deep Space Education) |
| **Font chính** | Inter (Google Fonts) |
| **Font mono** | JetBrains Mono |
| **Màu nền chính** | `#0a0f1a` |
| **Màu card** | `#141b2d` |
| **Accent Primary** | `#00d4ff` (Cyan) |
| **Accent Secondary** | `#7c3aed` (Purple) |
| **Accent Success** | `#10b981` (Green) |
| **Accent Warning** | `#f59e0b` (Amber) |
| **Accent Danger** | `#ef4444` (Red) |
| **Border Radius** | 12px |
| **Animation** | Fade-in 0.3s cho views, Pulse cho timer |

---

## 9. RÀNG BUỘC THIẾT KẾ

### 9.1 Ràng buộc công nghệ

| Thành phần | Công nghệ | Lý do |
|-----------|-----------|-------|
| Backend | Python 3.9+, FastAPI, Uvicorn | Hiệu năng cao, async, dễ phát triển |
| AI/ML | OpenCV 4.x, FER, MediaPipe | Tối ưu CPU, không yêu cầu GPU |
| Database | SQLite (aiosqlite) | Nhẹ, không cần server DB riêng |
| Frontend | HTML/CSS/JS thuần | Không phụ thuộc framework, nhẹ |
| Communication | WebSocket, REST API | Real-time + request-response |
| Config | YAML | Dễ đọc, dễ chỉnh sửa |

### 9.2 Ràng buộc phần cứng tối thiểu

| Thành phần | Tối thiểu | Khuyến nghị |
|-----------|-----------|-------------|
| CPU | 4 cores, 2.0 GHz | 8 cores, 3.0 GHz (Intel gen 10+) |
| RAM | 8 GB | 16 GB |
| Ổ cứng | 2 GB trống | SSD 10 GB trống |
| Mạng | LAN 100 Mbps | LAN 1 Gbps |
| Camera | 720p, 15 FPS | 1080p sub-stream, 25 FPS |
| OS | Windows 10 (64-bit) | Windows 11 |
| GPU | Không yêu cầu | — |

### 9.3 Ràng buộc đạo đức

| Nguyên tắc | Chi tiết |
|-----------|----------|
| Minh bạch | Giáo viên và học sinh được thông báo về sự tồn tại của hệ thống |
| Đồng ý | Có sự đồng ý bằng văn bản từ phụ huynh/giám hộ |
| Mục đích | Chỉ dùng để cải thiện chất lượng giảng dạy, không dùng để kỷ luật |
| Bảo mật dữ liệu | Dữ liệu xử lý local, không lưu ảnh gốc, mã hóa embedding |
| Quyền truy cập | Chỉ giáo viên phụ trách có quyền xem dữ liệu lớp mình |
| Xóa dữ liệu | Dữ liệu tự động xóa sau 90 ngày, phụ huynh có quyền yêu cầu xóa sớm |

---

## 10. TIÊU CHÍ CHẤP NHẬN

### 10.1 Tiêu chí chức năng

| ID | Tiêu chí | Pass/Fail |
|----|----------|-----------|
| AC-01 | Hệ thống phát hiện ≥ 90% khuôn mặt trong lớp 30 HS (chiếu sáng tốt) | |
| AC-02 | Cảm xúc được phân loại đúng ≥ 65% thời gian | |
| AC-03 | Hướng nhìn phân loại đúng ≥ 80% thời gian | |
| AC-04 | Điểm danh tự động đúng ≥ 85% HS đã đăng ký | |
| AC-05 | Engagement score cập nhật trên dashboard trong ≤ 3 giây | |
| AC-06 | Cảnh báo xuất hiện trong ≤ 5 giây khi điều kiện thỏa mãn | |
| AC-07 | Camera RTSP kết nối thành công khi URL hợp lệ | |
| AC-08 | Camera tự động kết nối lại khi mất tín hiệu | |
| AC-09 | Buổi học bắt đầu/kết thúc không lỗi | |
| AC-10 | Báo cáo sau giờ học hiển thị đầy đủ thông tin | |

### 10.2 Tiêu chí phi chức năng

| ID | Tiêu chí | Ngưỡng |
|----|----------|--------|
| AC-11 | Thời gian xử lý frame trên CPU | ≤ 200ms |
| AC-12 | RAM usage | ≤ 2GB |
| AC-13 | Dashboard load time | ≤ 3 giây |
| AC-14 | Hệ thống chạy liên tục | ≥ 4 giờ không crash |
| AC-15 | Dữ liệu không mất khi restart server | 100% |
| AC-16 | Giao diện hiển thị đúng Tiếng Việt | 100% |

### 10.3 Tiêu chí bảo mật

| ID | Tiêu chí |
|----|----------|
| AC-17 | Không có ảnh khuôn mặt gốc trong thư mục dữ liệu |
| AC-18 | Mật khẩu RTSP bị ẩn trên giao diện dashboard |
| AC-19 | Không có HTTP request ra internet (ngoại trừ lần đầu tải model) |
| AC-20 | Dữ liệu cũ hơn 90 ngày bị xóa tự động |

---

## 11. PHỤ LỤC

### 11.1 Cấu trúc thư mục dự án

```
classroom/
├── backend/
│   ├── main.py                  # FastAPI application
│   ├── config.py                # Configuration loader
│   ├── config.yaml              # System configuration
│   ├── models.py                # Pydantic data models
│   ├── database.py              # SQLite database module
│   ├── camera_manager.py        # Camera stream manager
│   ├── face_detector.py         # Face detection (OpenCV DNN)
│   ├── emotion_recognizer.py    # Emotion recognition (FER)
│   ├── head_pose_estimator.py   # Head pose estimation (MediaPipe)
│   ├── attendance_tracker.py    # Attendance tracking (LBPH)
│   ├── engagement_engine.py     # Engagement scoring engine
│   ├── classroom_detector.py    # Master AI pipeline
│   └── requirements.txt        # Python dependencies
├── data/
│   ├── classroom.db             # SQLite database
│   ├── face_embeddings/         # Student face data
│   └── session_exports/         # Export reports
├── images/                      # Static assets
├── index.html                   # Dashboard HTML
├── styles.css                   # Dashboard CSS
├── app.js                       # Dashboard JavaScript
└── SRS_Classroom_Engagement_System.md  # Tài liệu này
```

### 11.2 Dependencies (requirements.txt)

```
fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6
aiofiles==23.2.1
aiosqlite==0.19.0
pyyaml==6.0.1
pydantic==2.5.2
opencv-python-headless==4.8.1.78
numpy==1.26.2
fer==22.5.1
mediapipe==0.10.8
tensorflow-cpu==2.15.0
```

### 11.3 Bảng thuật ngữ Tiếng Việt

| Tiếng Anh | Tiếng Việt (Giao diện) |
|-----------|----------------------|
| Engagement | Mức tham gia / Tiếp nhận học tập |
| Dashboard | Bảng điều khiển |
| Session | Buổi học |
| Attendance | Điểm danh |
| Emotion | Cảm xúc |
| Analytics | Phân tích |
| Alert | Cảnh báo |
| Camera | Camera |
| Student | Học sinh |
| Settings | Cài đặt |
| Face Detection | Phát hiện khuôn mặt |
| Head Pose | Hướng nhìn / Tư thế đầu |
| Present | Có mặt |
| Late | Muộn |
| Absent | Vắng |
| Engaged | Tích cực |
| Confused | Bối rối |
| Bored | Chán nản |
| Frustrated | Thất vọng |
| Looking at teacher | Nhìn bảng/GV |
| Looking away | Nhìn chỗ khác |
| Looking down | Cúi đầu |
| Head down | Gục đầu |

### 11.4 Lịch sử thay đổi

| Phiên bản | Ngày | Mô tả |
|-----------|------|-------|
| 1.0 | 11/04/2026 | Phiên bản đầu tiên - đầy đủ các yêu cầu |

---

**--- HẾT TÀI LIỆU ---**
