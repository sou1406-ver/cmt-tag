# Tiến độ gán nhãn cảm xúc V2

**Cập nhật 23/11/2026.** V2 phân loại sắc thái chung do người viết thể hiện trong `text_clean`, bất kể đối tượng được nhắc tới. Ba lớp mô hình là POS, NEG và NEU. REVIEW và EXCLUDE được lưu để theo dõi quyết định gán nhãn.

## Phần đã hoàn thành

| Tập | Số câu | Vai trò |
| --- | ---: | --- |
| E | 41 | Ví dụ chọn từ pilot 200 câu đã gán độc lập A/B và đối soát. |
| C | 159 | Phần pilot còn lại dùng để hiệu chuẩn AI với nhãn người. E+C có 184 câu thuộc ba lớp sentiment. |
| T | 202 | Tập test đã khóa, lấy từ 12 bài. Trong 50 câu người dùng gán mù trước khi xem AI, 47 nhãn khớp quyết định cuối. Có 189 câu thuộc ba lớp sentiment. |
| U | 798 | Ba AI gán. Người dùng chốt 181 câu bất đồng và kiểm tra 62 câu đồng thuận, sửa 1 nhãn. Có 773 câu dùng được cho train, gồm 231 POS, 257 NEG và 285 NEU. |

## Kết quả train thử

Hai cấu hình dùng cùng 5 fold chia theo bài viết trên 184 câu E+C có nhãn người từ 28 bài. U chỉ thêm vào train của mỗi fold sau khi kiểm tra trùng bài và nội dung với validation. Bảng dùng macro-F1 gộp các dự đoán ngoài fold. T vẫn dành cho lần chấm cuối.

| Mô hình | E+C | E+C+U |
| --- | ---: | ---: |
| BoW + ComplementNB | 0,380 | 0,476 |
| BoW + MultinomialNB | 0,334 | 0,521 |
| TF-IDF từ + LinearSVC | 0,345 | 0,592 |
| TF-IDF ký tự 3–5 + LinearSVC | 0,481 | 0,603 |

Với mô hình ký tự, F1 của POS tăng từ 0,314 lên 0,529 và vẫn thấp hơn NEG và NEU. Kết quả này là số liệu phát triển trên E+C, với 32 mẫu POS trong tổng 184 câu validation.

## Lượt gán mở rộng

Từ bốn export Facebook V2 có **12.795 bình luận**, giữ **8.965 câu** từ **74 bài, 55 phim và 4 nguồn**. Đã xuất **90 CSV local**, mỗi file tối đa 100 câu và chỉ có `comment_id`, `text_clean`. Manifest lưu seed `20261123`, SHA-256 của prompt và guideline snapshot, cùng checksum từng file.

| Lý do loại khỏi lượt mở rộng | Số câu |
| --- | ---: |
| Thuộc một trong 12 bài của T | 2.109 |
| ID đã có trong pilot hoặc U, sau khi chặn T | 998 |
| Trạng thái làm sạch kỹ thuật khác KEEP | 611 |
| Trùng nội dung với bình luận thuộc bài của T | 30 |
| Trùng đúng nội dung thuộc reservation cũ | 5 |
| Trùng nội dung đã gán | 10 |
| Trùng đúng nội dung trong pool mới | 61 |
| Gần trùng nội dung trong pool mới | 6 |
| **Tổng loại** | **3.830** |

Phân bố pool mới gồm 6.322 câu từ Maybe You Never Watched This Movie, 2.449 từ Chê Phim Review, 178 từ XEM PHIM & BÌNH PHIM và 16 từ Cuồng Phim. Số lượng phản ánh pool sau lọc và tập trung vào hai nguồn lớn.

Lượt 1 đã chuẩn bị xong. Người dùng gán trên web với ChatGPT, Claude và Gemini. Chỉ các câu bất đồng mới được gán lại một lần trong chat mới với cùng prompt và guideline. Người dùng chốt các câu vẫn bất đồng và kiểm tra ngẫu nhiên 10% trong từng nhóm đồng thuận. Lưu nguồn nhãn theo lượt và giữ câu chưa chốt ở PENDING. CSV, prompt chứa ví dụ thật và kết quả theo từng ID lưu local tại `outputs/annotation_expansion_round_01/`.
