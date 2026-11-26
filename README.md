# cmt-tag · Phân loại cảm xúc bình luận tiếng Việt

Bài tập lớn môn Xử lý dữ liệu văn bản. Dự án phân loại cảm xúc trong bình luận Facebook về phim thành **POS** (tích cực), **NEG** (tiêu cực) và **NEU** (trung tính). Người gán dùng `REVIEW` cho câu cần xem lại và `EXCLUDE` cho câu bị loại. [Hướng dẫn gán nhãn](docs/guidelines/SENTIMENT_GUIDELINE.md)

## Chạy demo từ bản đóng gói trên Windows

Demo cần bản đóng gói cục bộ có launcher, thư viện và dữ liệu. Nếu chưa có môi trường, cài **Python 3.12 64-bit** rồi chạy `CAI_DAT.cmd` để cài thư viện từ `offline_wheels/`. Xem `DOC_TRUOC_KHI_CHAY.md` trong gói để biết cách chuyển sang máy khác.

| Muốn thử | Mở file | Mô hình và dữ liệu |
| --- | --- | --- |
| Demo web | `Mo_Demo.cmd` | Bốn baseline được fit khi mở ứng dụng từ **4.945 câu train V2** đã khóa. |
| Demo dòng lệnh | `CHAY_DEMO.cmd` | Bốn baseline, PhoBERT và ViSoBERT đã huấn luyện trên **425 câu development**. |

Web chạy tại [127.0.0.1:8768](http://127.0.0.1:8768/), hiển thị văn bản sau chuẩn hóa, nhãn dự đoán và điểm từng lớp. Tab **Thực nghiệm** trình bày kết quả đã báo cáo trên E+C. Nếu thiếu snapshot train, web vẫn mở để thử chuẩn hóa văn bản.

Trong demo dòng lệnh, nhập `/model` để đổi mô hình hoặc Enter ở dòng trống để thoát.

Hai lệnh tương đương khi chạy từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m src.web_demo --open
.\.venv\Scripts\python.exe -X utf8 -B -m src.models predict
```

Web mặc định đọc `outputs/03_Dau_vao_chinh_thuc/`. Thêm `--train-dir <thu_muc>` nếu snapshot V2 nằm ở vị trí khác.

## Dữ liệu và thực nghiệm V2

- Workbook chính có **14.408 bình luận sau lọc**. Dữ liệu nguồn, nhãn và các lô chờ gán được lưu cục bộ. [Chỉ mục dữ liệu](outputs/README.md)
- Đầu vào chính thức đã khóa **4.945 câu train** và **613 câu T2 có nhãn người**, gồm 189 câu test gốc và 424 câu bổ sung. Bản chính dùng `normalize_v2`, bản đối chứng giữ cách viết gốc sau làm sạch kỹ thuật. Hai bản có cùng ID và nhãn. Manifest nằm cạnh dữ liệu cục bộ trong `outputs/03_Dau_vao_chinh_thuc/` và `outputs/04_Dau_vao_phu/`.
- Lượt chấm chính thức trên **toàn bộ T2 đang chờ**. Báo cáo hiện có kết quả thử nghiệm E+C và một lượt thử riêng trên 424 câu bổ sung. [Báo cáo bài tập lớn](docs/BAO_CAO_BTL.md)

## Quy trình

1. Thu thập bình luận bằng Python và Selenium theo từng bài đăng, ghi mã phim để truy nguồn. [Hướng dẫn crawl](docs/CRAWLER.md)
2. Lọc bình luận rỗng hoặc trùng, chuẩn hóa Unicode và khoảng trắng, áp dụng các sửa đổi từ viết tắt và lỗi gõ đã duyệt. Giữ emoji, emoticon và từ thể hiện sắc thái. [Script chuẩn hóa](scripts/chuan_hoa_binh_luan_v2.py)
3. Gán nhãn cảm xúc theo nội dung bình luận. Rà lại các trường hợp mơ hồ và dùng nhãn người cho tập test. [Hướng dẫn gán nhãn](docs/guidelines/SENTIMENT_GUIDELINE.md)
4. Tách train và test theo bài đăng, kiểm tra trùng và gần trùng ở cả dạng gốc lẫn dạng chuẩn hóa. [Script khóa đầu vào V2](scripts/freeze_v2_official.py)
5. So sánh BoW, TF-IDF, PhoBERT và ViSoBERT bằng macro-F1, accuracy và F1 từng lớp. Dùng E+C để so sánh cách tiền xử lý trước lượt chấm chính thức trên T2. [Thiết kế và kết quả thực nghiệm](docs/BAO_CAO_BTL.md)
