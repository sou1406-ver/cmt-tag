# Lịch sử guideline gán nhãn

Bản đang dùng: `docs/guidelines/SENTIMENT_GUIDELINE.md`. Mỗi lượt gán ghi SHA256 của file tại thời điểm giao trong manifest; nhãn thuộc về đúng SHA đó.

| Ngày | Mốc | Thay đổi | Lượt gán dùng |
|---|---|---|---|
| 10–14/11/2026 | V2.0, V2.1 | Cảm xúc hướng vào phim (V1 của dự án) | 425 nhãn người, Gold V1 |
| 15/11/2026 | V3.1 | Chuyển sang cảm xúc chung, chỉ đọc `text_clean` | Pilot 200 câu (Kappa 5 nhãn 0,60; 3 nhãn 0,78) |
| 15/11/2026 | V3.2 | Thu hẹp EXCLUDE; công kích người là NEG; tách tranh luận NEU/NEG; mỉa mai đọc nghĩa đen | Không có |
| 15/11/2026 | V3.3 | Mọi đối tượng đều tính; cảm xúc thuật lại hoặc giả định không tính; chốt tín hiệu mỉa mai và đánh giá nhẹ ("không tệ" là POS); lời lịch sự không tính; spam/quảng cáo EXCLUDE; bỏ ví dụ còn tranh cãi | Batch 1 lượt chính thức |
