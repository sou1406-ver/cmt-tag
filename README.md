# cmt-tag · Phân loại cảm xúc bình luận tiếng Việt

Bài tập lớn môn Xử lý dữ liệu văn bản. Dự án phân loại cảm xúc trong bình luận Facebook về phim thành **POS** (tích cực), **NEG** (tiêu cực) và **NEU** (trung tính).

## Quy trình dự án

1. **Thu thập.** Crawl bình luận bằng Python và Selenium theo từng bài đăng, ghi kèm mã phim để truy nguồn. [Hướng dẫn crawl](docs/CRAWLER.md)
2. **Làm sạch và chuẩn hóa.** Lọc bình luận rỗng hoặc trùng, chuẩn hóa Unicode, khoảng trắng, từ viết tắt và lỗi gõ đã duyệt. Giữ emoji, emoticon và từ thể hiện sắc thái. [Script chuẩn hóa](scripts/chuan_hoa_binh_luan_v2.py)
3. **Gán nhãn.** Xác định cảm xúc thể hiện trong chính bình luận. Rà lại các trường hợp mơ hồ và dùng nhãn người cho tập test. [Hướng dẫn gán nhãn](docs/guidelines/SENTIMENT_GUIDELINE.md)
4. **Chia dữ liệu và huấn luyện.** Tách train và test theo bài đăng, kiểm tra bình luận trùng hoặc gần trùng giữa hai tập. So sánh các baseline BoW, TF-IDF với PhoBERT và ViSoBERT.
5. **Đánh giá.** Báo cáo macro-F1, accuracy và F1 từng lớp. So sánh cách tiền xử lý trên E+C và dành T2 cho lượt chấm chính thức. [Báo cáo bài tập lớn](docs/BAO_CAO_BTL.md)

## Trạng thái V2

Workbook có **14.408 bình luận sau lọc**. Đã khóa **4.945 câu train** và **613 câu T2**, gồm 189 câu test gốc và 424 câu bổ sung. T2 chưa chấm. Dữ liệu và workbook lưu cục bộ. [Chỉ mục dữ liệu](outputs/README.md)
