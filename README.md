# cmt-tag · Phân loại cảm xúc bình luận tiếng Việt

Bài tập lớn môn Xử lý dữ liệu văn bản. `cmt-tag` thu thập bình luận Facebook về phim, chuẩn hóa văn bản và chuẩn bị dữ liệu để phân loại cảm xúc thành **POS** (tích cực), **NEG** (tiêu cực) và **NEU** (trung tính). Nhãn dựa trên cảm xúc thể hiện trong chính bình luận. Các quyết định `REVIEW` và `EXCLUDE` nằm ngoài ba lớp mô hình. [Hướng dẫn gán nhãn](docs/guidelines/SENTIMENT_GUIDELINE.md)

## Dữ liệu V2

| Tập dữ liệu | Số câu | Vai trò |
| --- | ---: | --- |
| Workbook chuẩn hóa | 14.408 | Bình luận sau lọc, có văn bản gốc, văn bản chuẩn hóa và nhãn đã có |
| Train chính thức | 4.945 | Nhãn E, C, U và nhãn mở rộng đã duyệt, sau lọc trùng với T2 |
| Test T2 | 613 | Nhãn người, gồm 189 câu T gốc và 424 câu bổ sung |
| Hàng chờ gán | 1.731 | Để dành cho lượt gán tiếp theo |

Train và T2 đã đóng băng trong `outputs/03_Dau_vao_chinh_thuc/` cùng cấu hình và SHA-256. Lượt chấm chính thức trên T2 chưa chạy. Repo công khai chứa mã nguồn, tài liệu và fixture. Bình luận, nhãn, workbook, danh sách link thực tế và hồ sơ đăng nhập lưu cục bộ. [Chỉ mục dữ liệu](outputs/README.md)

## Cài đặt trên Windows

Dùng Python 3.12 và Brave hoặc Chrome. Tại thư mục gốc repo, tạo môi trường lần đầu rồi cài các gói cần cho crawl và chế độ Excel.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements/crawler.txt openpyxl
```

## 1. Thu thập bình luận

Mở Brave với profile riêng để đăng nhập Facebook. Đóng cửa sổ dùng profile đó sau khi đăng nhập.

```powershell
.\.venv\Scripts\python.exe -m src.crawler login --channel brave --profile data/browser_profile_brave_manual
```

Chế độ tương tác nhận mã phim và từng link bài đăng. Gõ `movie MA_PHIM` để đổi phim, Enter trên dòng trống để kết thúc.

```powershell
.\.venv\Scripts\python.exe -m src.crawler interactive --channel brave --profile data/browser_profile_brave_manual --max-comments 100
```

Để chạy theo danh sách, tạo CSV UTF-8 với `movie_id,post_url`. Khi dùng `--campaign-v2`, khai báo `source_type=page` cho nguồn trang và có thể đặt `max_comments` riêng cho từng bài. Danh sách V2 trên máy nằm tại `data/posts_v2.csv`. [CSV mẫu](configs/post_urls.example.csv)

```powershell
.\.venv\Scripts\python.exe -m src.crawler crawl-batch --campaign-v2 --input data/posts_v2.csv --channel brave --profile data/browser_profile_brave_manual --max-comments 300
.\.venv\Scripts\python.exe -m src.crawler validate --run RUN_ID
.\.venv\Scripts\python.exe -m src.crawler export --run RUN_ID --format xlsx
```

Thay `RUN_ID` bằng mã crawler in ra. Journal lưu ở `data/crawl_runs/RUN_ID/`, còn workbook để rà lưu ở `data/imports/RUN_ID/review.xlsx`. Số bình luận lấy được phụ thuộc vào nội dung Facebook hiển thị. Cột `clean_status` ghi tình trạng kỹ thuật của văn bản và người gán xác định nhãn cảm xúc riêng. [Hướng dẫn crawler](docs/CRAWLER.md)

## 2. Chuẩn hóa văn bản và nối nhãn

`normalize_v2` chuẩn hóa Unicode và khoảng trắng, giải mã HTML entity, rồi áp dụng các quy tắc viết tắt và lỗi gõ đã duyệt. Các quy tắc giữ emoji, emoticon và từ tục để bảo toàn sắc thái. Ví dụ, `mún xem rùi, thanh kiu =))` thành `muốn xem rồi, thanh kiu =))`.

Thử một câu ngay trong terminal.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.chuan_hoa_binh_luan_v2 --text "mún xem rùi, thanh kiu =))"
```

Với Excel, script giữ các sheet và thêm cột **Bình luận chuẩn hóa** vào bản xuất. Chọn tên đầu ra mới. Dùng `--sheet` và `--column` nếu workbook có nhiều bảng hoặc dùng tên cột riêng.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.chuan_hoa_binh_luan_v2 --input data/binh_luan.xlsx --output data/binh_luan_chuan_hoa.xlsx
```

Nhãn đã duyệt được nối lại theo `comment_id`. Bản đọc chính trên máy là `outputs/02_Du_lieu_va_nhan/01_Crawl_va_nguon_goc/Cmt_V2_ban_chuan.xlsx`. [Quy trình gán và đối soát](docs/annotation/QUY_TRINH_GAN_NHAN.md)

## 3. Chuẩn bị train và test chính thức

Hai lệnh dưới dựng lại dữ liệu từ nguồn V2 đã khóa và tạo một bản đầu vào mới. Cần có các tệp V2 cục bộ và hai bản kê checkpoint trong `data/local_models/v2_fresh_checkpoints/`. Bước đóng băng kiểm tra trùng ID, cùng bài đăng và văn bản trùng hoặc gần trùng với T2, rồi ghi SHA-256 cho dữ liệu và cấu hình.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/classical-base.txt
.\.venv\Scripts\python.exe -m scripts.prepare_v2_normalized --output outputs/V2_chuan_hoa_chay_lai
.\.venv\Scripts\python.exe -m scripts.freeze_v2_official --snapshot outputs/V2_chuan_hoa_chay_lai --input-view normalize_v2 --output outputs/V2_dong_bang_chay_lai
```

## Thử nghiệm phát triển

Các mô hình đối chiếu gồm hai baseline BoW + Naive Bayes, hai baseline TF-IDF + LinearSVC, PhoBERT và ViSoBERT. Trong lượt so sánh gần nhất trên **184 câu E+C**, chia 5 fold theo bài đăng và dùng hai seed, kết quả macro-F1 là trung bình ± độ lệch chuẩn mẫu.

| Mô hình | Giữ cách viết gốc sau làm sạch kỹ thuật | Dùng `normalize_v2` |
| --- | ---: | ---: |
| TF-IDF từ + LinearSVC | **0,6815 ± 0,0039** | 0,6687 ± 0,0108 |
| ViSoBERT | **0,8262 ± 0,0148** | 0,8100 ± 0,0232 |

Các điểm trên thuộc tập phát triển E+C. [Báo cáo BTL](docs/BAO_CAO_BTL.md) ghi cấu hình mô hình, kết quả thử nghiệm và thiết kế chấm T2.
