# cmt-tag · Phân loại cảm xúc bình luận tiếng Việt

Bài tập lớn môn **Xử lý dữ liệu văn bản**. Dự án xây dựng bộ dữ liệu bình luận Facebook về phim và so sánh các mô hình phân loại cảm xúc tiếng Việt, từ phương pháp học máy truyền thống đến mô hình ngôn ngữ pretrained.

## 1. Bài toán

Đầu vào là văn bản `text_clean` của một bình luận; đầu ra là cảm xúc chung do chính người viết thể hiện. Không sử dụng bài đăng, comment cha, tên phim hoặc nguồn làm đặc trưng để suy đoán nhãn. Cảm xúc có thể hướng tới phim, diễn viên, người bình luận hoặc đối tượng khác.

| Nhãn | Ý nghĩa |
| --- | --- |
| POS | Tích cực |
| NEG | Tiêu cực |
| NEU | Trung tính |
| REVIEW | Cần xem lại; bắt buộc có ghi chú |
| EXCLUDE | Không sử dụng được hoặc nằm ngoài phạm vi dữ liệu |

Chỉ POS, NEG và NEU là lớp đầu ra của mô hình. Xem [hướng dẫn gán nhãn](docs/guidelines/SENTIMENT_GUIDELINE.md) để biết cách xử lý câu mơ hồ, mỉa mai, emoji và bình luận Việt–Anh.

## 2. Trạng thái V2

Số liệu dưới đây theo [báo cáo BTL cập nhật 26/11/2026](docs/BAO_CAO_BTL.md), không phải thống kê trực tiếp từ workbook đang được lưu cục bộ.

| Hạng mục | Số bình luận | Trạng thái |
| --- | ---: | --- |
| Corpus sau lọc | 14.408 | Workbook V2 |
| Train chính thức | 4.945 | Đã đóng băng |
| Quyết định nhãn T2 | 652 | Nhãn do người gán chốt |
| T2 dùng để chấm | 613 | Đã đóng băng |
| Hàng chờ gán | 1.731 | Ngoài train và test chính thức |

| Tập | POS | NEG | NEU | Tổng |
| --- | ---: | ---: | ---: | ---: |
| Train | 1.149 | 2.150 | 1.646 | 4.945 |
| T gốc | 55 | 61 | 73 | 189 |
| T bổ sung | 119 | 145 | 160 | 424 |
| **T2** | **174** | **206** | **233** | **613** |

Trong 652 quyết định T2 có 32 REVIEW và 7 EXCLUDE nên chỉ 613 câu được dùng để tính điểm. T2 là tập đánh giá cố định; bổ sung nhãn vào corpus hoặc train không tự động mở rộng tập này. Không lấy hàng chờ T2 làm dữ liệu huấn luyện cho lượt chính thức.

**Chưa có kết quả chấm chính thức trên toàn bộ T2.** Phần bổ sung 424 câu đã được dùng trong một lượt thử nghiệm một seed; T gốc 189 câu chưa được chấm. Kết quả phát triển trên E+C được báo cáo riêng.

## 3. Quy trình

1. **Thu thập:** crawler Python/Selenium theo bài đăng, lưu `comment_id`, `post_id`, mã phim và nguồn để truy vết. [Hướng dẫn crawler](docs/CRAWLER.md).
2. **Làm sạch:** lọc dữ liệu không sử dụng được và xử lý trùng lặp; chuẩn hóa Unicode, thực thể HTML hợp lệ và khoảng trắng. Giữ emoji, emoticon và từ thể hiện sắc thái. [Công cụ chuẩn hóa V2](scripts/chuan_hoa_binh_luan_v2.py).
3. **Gán nhãn:** đọc nội dung bình luận, dùng đề xuất nhãn AI khi phù hợp, rà các trường hợp chưa rõ và giữ nhãn người cho T2. [Guideline](docs/guidelines/SENTIMENT_GUIDELINE.md).
4. **Chuẩn bị dữ liệu:** nối nhãn theo ID; loại rò rỉ giữa train và T2 theo ID, bài đăng, văn bản trùng và gần trùng, kiểm tra cả cách viết gốc và dạng chuẩn hóa.
5. **Huấn luyện và đánh giá:** so sánh sáu mô hình trên cùng danh sách train, báo cáo macro-F1, accuracy và F1 từng lớp. Tách kết quả phát triển khỏi lượt chấm chính thức.

## 4. Mô hình thực nghiệm

| Nhóm | Mô hình |
| --- | --- |
| Baseline | BoW + MultinomialNB |
| Baseline | BoW + ComplementNB |
| Baseline | TF-IDF từ + LinearSVC |
| Baseline | TF-IDF ký tự + LinearSVC |
| Transformer | PhoBERT (`vinai/phobert-base`) |
| Transformer | ViSoBERT (`uitnlp/visobert`) |

Hai mô hình Transformer có cấu hình chính thức 4 epoch, learning rate 2e-5, batch size 16, tối đa 128 token và ba seed. Chi tiết revision, trọng số lớp và các kết quả ablation nằm trong [báo cáo thực nghiệm](docs/BAO_CAO_BTL.md).

### Lưu ý về đầu vào V2

- Ablation trên E+C cho kết quả tốt hơn khi giữ cách viết gốc sau làm sạch kỹ thuật.
- Báo cáo ngày 26/11 ghi nhận đầu vào chính thức được đóng băng với `normalize_v2`. Cần ghi rõ lý do lựa chọn này so với tiêu chí ablation trước khi chấm T2.
- Không thay đổi quy tắc tiền xử lý dựa trên kết quả T2.

## 5. Cấu trúc repository

| Đường dẫn | Nội dung |
| --- | --- |
| [src/crawler/](src/crawler/) | Thu thập bình luận và xuất dữ liệu |
| [src/annotation/](src/annotation/) | Công cụ gán nhãn và kiểm tra |
| [src/data/](src/data/), [src/dataset/](src/dataset/) | Xử lý, chuẩn bị và kiểm tra dữ liệu |
| [src/preprocessing/](src/preprocessing/) | Tiền xử lý văn bản |
| [src/models/](src/models/) | Mô hình và thực nghiệm |
| [scripts/](scripts/) | Script vận hành và tái lập |
| [configs/](configs/) | Cấu hình và mẫu đầu vào |
| [requirements/](requirements/) | Dependency theo nhóm chức năng |
| [tests/](tests/) | Kiểm thử |
| [docs/](docs/) | Báo cáo, hướng dẫn và lịch sử |
| [outputs/README.md](outputs/README.md) | Chỉ mục các dữ liệu lưu cục bộ |

## 6. Chuẩn bị lại đầu vào thực nghiệm

Chạy từ thư mục gốc repo, với môi trường Python đã cài dependency phù hợp và các snapshot, nhãn, manifest, hồ sơ checkpoint cục bộ đầy đủ. Dùng thư mục output mới để không ghi đè dữ liệu đã khóa.

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_v2_normalized --output outputs/V2_chuan_hoa_chay_lai
.\.venv\Scripts\python.exe -m scripts.freeze_v2_official --snapshot outputs/V2_chuan_hoa_chay_lai --input-view normalize_v2 --output outputs/V2_dong_bang_chay_lai
```

Hai script này chuẩn bị và đóng băng đầu vào; không huấn luyện hoặc chấm mô hình. Lệnh đóng băng ở trên tái hiện lựa chọn đầu vào ghi trong báo cáo, không phải kết luận rằng chuẩn hóa tốt hơn. Xem [báo cáo BTL](docs/BAO_CAO_BTL.md) và [chỉ mục dữ liệu](outputs/README.md) để biết các đầu vào cần có.

### Dữ liệu và quyền riêng tư

Repo chỉ lưu code, cấu hình, tài liệu và fixture phù hợp. Dữ liệu crawl thật, workbook, nhãn, danh sách bài test, manifest chứa dữ liệu, checkpoint và browser profile được giữ cục bộ theo [`.gitignore`](.gitignore). Clone repo không đồng nghĩa có đầy đủ dữ liệu để tái lập kết quả. Không commit các dữ liệu này hoặc thông tin đăng nhập lên GitHub.

## 7. Tài liệu chính

- [Báo cáo BTL và thực nghiệm V2](docs/BAO_CAO_BTL.md)
- [Hướng dẫn gán nhãn](docs/guidelines/SENTIMENT_GUIDELINE.md)
- [Hướng dẫn crawler](docs/CRAWLER.md)
- [Báo cáo hiệu chuẩn và thực nghiệm C](docs/annotation/BAO_CAO_THUC_NGHIEM_V2_C_3_SEED.md)
- [Chỉ mục dữ liệu V2](outputs/README.md)
- [Lịch sử dự án](docs/PROJECT_HISTORY.md)
