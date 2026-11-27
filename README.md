# cmt-tag · Phân loại cảm xúc bình luận tiếng Việt

Bài tập lớn môn Xử lý dữ liệu văn bản. Dự án phân loại cảm xúc trong bình luận Facebook về phim thành **POS** (tích cực), **NEG** (tiêu cực) và **NEU** (trung tính). Người gán dùng `REVIEW` cho câu cần xem lại và `EXCLUDE` cho câu bị loại. [Hướng dẫn gán nhãn](docs/guidelines/SENTIMENT_GUIDELINE.md)

## Quy trình dự án

1. **Thu thập.** Crawl bình luận bằng Python và Selenium theo từng bài đăng, ghi kèm mã phim để truy nguồn. [Hướng dẫn crawl](docs/CRAWLER.md)
2. **Làm sạch và chuẩn hóa.** Lọc bình luận rỗng hoặc trùng, chuẩn hóa Unicode, khoảng trắng, từ viết tắt và lỗi gõ đã duyệt. Giữ emoji, emoticon và từ thể hiện sắc thái. [Script chuẩn hóa](scripts/chuan_hoa_binh_luan_v2.py)
3. **Gán nhãn.** Xác định cảm xúc thể hiện trong chính bình luận. Rà lại các trường hợp mơ hồ và dùng nhãn người cho tập test. [Hướng dẫn gán nhãn](docs/guidelines/SENTIMENT_GUIDELINE.md)
4. **Chia dữ liệu và huấn luyện.** Tách train và test theo bài đăng, kiểm tra bình luận trùng hoặc gần trùng giữa hai tập. So sánh các baseline BoW, TF-IDF với PhoBERT và ViSoBERT.
5. **Đánh giá.** Dùng E+C để thử cách tiền xử lý. Trên T2, báo cáo Accuracy, Macro-Precision, Macro-Recall, Macro-F1 và ma trận nhầm lẫn. [Báo cáo bài tập lớn](docs/BAO_CAO_BTL.md)

## Trạng thái V2

Workbook có **14.408 bình luận sau lọc**. Bộ dữ liệu cuối V2 có **7.864 câu train** sau khi gộp hai nguồn gán nhãn AI qua hai lượt và các nhãn E/C/U đã chốt. T2 có **613 câu**, gồm 189 câu test gốc và 424 câu bổ sung. Sáu mô hình đã được chấm qua ba seed. [Kết quả T2](docs/BAO_CAO_BTL.md#5-kết-quả-trên-t2) · [Chỉ mục dữ liệu](outputs/README.md)

## Demo web

Bấm đúp **Mo_Demo.cmd** để mở [demo cục bộ](http://127.0.0.1:8768/). Khi bộ dữ liệu và mô hình cuối đã sẵn sàng, có thể chạy trực tiếp từ thư mục dự án.

```powershell
.\.venv\Scripts\python.exe -m src.web_demo --train-dir outputs\06_Du_lieu_cuoi_V2 --bert-receipt outputs\07_Mo_hinh_cuoi_V2\bert_modal_trained.json --open
```

Demo hiển thị bình luận sau chuẩn hóa, nhãn dự đoán và điểm từng lớp. `Mo_Demo.cmd` mở bộ dữ liệu cuối khi đã có biên nhận của cả hai mô hình BERT. Dùng `--train-dir` và `--bert-receipt` để chỉ định bộ dữ liệu và biên nhận tương ứng. Tab **Thực nghiệm** hiển thị điểm và ma trận nhầm lẫn trên T2.

Trên máy Windows mới, cài Python 3.12 64-bit có trình khởi chạy `py`, giải nén dự án rồi bấm `Khoi_Tao_May_Moi.cmd` và `Mo_Demo.cmd`. Để dự đoán với PhoBERT và ViSoBERT, chạy `.\.venv\Scripts\python.exe -m modal setup` và đăng nhập workspace Modal đã lưu checkpoint. Cài Brave và đăng nhập Facebook trên máy mới nếu dùng chức năng crawl.

Bản đóng gói offline trước đây có `CAI_DAT.cmd` để cài thư viện từ `offline_wheels/` và hướng dẫn trong `DOC_TRUOC_KHI_CHAY.md`. Bản đó dùng 4.945 câu train V2 cho demo web. `CHAY_DEMO.cmd` mở demo dòng lệnh với bốn baseline và hai BERT huấn luyện trên 425 câu development. Trong bản dòng lệnh, nhập `/model` để đổi mô hình hoặc Enter ở dòng trống để thoát. Lệnh tương đương là `.\.venv\Scripts\python.exe -X utf8 -B -m src.models predict`.

Để tự cài riêng phần baseline, dùng Python 3.12.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements\classical-base.txt
```

Snapshot dữ liệu được giữ cục bộ. Nếu thiếu snapshot train, demo vẫn mở để thử chuẩn hóa văn bản.

### BERT cho demo trên Modal

Khi chọn PhoBERT hoặc ViSoBERT, web chuẩn hóa và tokenize trên máy rồi gọi Modal để dự đoán. Mục Nhập bình luận hiển thị thêm kết quả TF-IDF từ trên cùng câu. Mục Crawl Facebook gửi các bình luận đã tokenize theo lô và hiển thị nhãn từng câu. Trọng số fine-tune lưu trên Modal Volume. Các lần dự đoán dùng container CPU theo yêu cầu.

Để huấn luyện lại từ snapshot cuối 7.864 câu, chạy từ thư mục dự án sau khi đã cài thư viện và đăng nhập Modal. Script dùng lại checkpoint đã lưu nếu khớp snapshot.

```powershell
.\.venv\Scripts\python.exe -m modal deploy scripts\modal_web_demo.py
.\.venv\Scripts\python.exe -m scripts.train_v2_final
```

Mở lại [demo](http://127.0.0.1:8768/) sau khi khởi động lại máy chủ. Pipeline dùng tokenizer của revision đã ghim trong `data/local_models/v2_fresh_checkpoints`. Demo dùng checkpoint seed `20261123`. Bảng T2 tổng hợp kết quả của ba seed `20261123`, `20261124`, `20261125`.
