# Phân loại sắc thái bình luận phim tiếng Việt

Bài tập lớn Xử lý dữ liệu văn bản: xây dựng pipeline Python CLI để phân loại
bình luận phim thành **tích cực (POS)**, **tiêu cực (NEG)** và **trung lập (NEU)**.

**Thu thập dữ liệu → Lọc và tiền xử lý → Kiểm tra chất lượng → Gán nhãn → Huấn luyện → Đánh giá**

## Quy trình thực hiện

1. **Thu thập dữ liệu:** crawl bình luận Facebook từ các bài thảo luận/review phim bằng Selenium, kết hợp bộ CSV khoảng 29.000 dòng được cung cấp. Bình luận Facebook được lưu cùng mã phim, mã bài đăng, mã bình luận và thông tin nguồn.
2. **Lọc và tiền xử lý:** loại dữ liệu không sử dụng được và bình luận trùng hoàn toàn; chuẩn hóa Unicode NFC, HTML entities hợp lệ và một số khoảng trắng kỹ thuật. Giữ riêng văn bản gốc, bảo toàn emoji, emoticon, dấu câu, phủ định và teencode.
3. **Kiểm tra chất lượng:** kiểm tra nội dung, nguồn, trùng lặp và nguy cơ dữ liệu cùng bài hoặc gần trùng xuất hiện ở cả train và test. Những trường hợp chưa rõ tiếp tục chờ người duyệt.
4. **Gán nhãn:** người gán quyết định POS/NEG/NEU theo guideline V2.1. REVIEW dành cho câu chưa đủ căn cứ; EXCLUDE dành cho câu ngoài phạm vi hoặc không sử dụng được. Lịch sử quyết định được giữ lại.
5. **Huấn luyện:** biểu diễn văn bản bằng BoW hoặc TF-IDF, thử Naive Bayes, Logistic Regression và Linear SVM. Vectorizer chỉ được fit trên phần train.
6. **Đánh giá:** báo cáo Macro-F1, Accuracy, Precision/Recall/F1 từng lớp và confusion matrix. Chia dữ liệu theo nhóm bài đăng, kiểm tra trùng lặp và phân biệt kết quả phát triển với test độc lập.

Nguồn gốc ban đầu và cách tạo nhãn `overall` của bộ CSV được cung cấp chưa được
xác minh. Nhãn này **không được dùng làm ground truth**.

## Dữ liệu hiện tại

| Hạng mục | Số lượng |
| --- | ---: |
| Bình luận sau lọc | **25.810** |
| Facebook | 7.146 |
| Bộ dữ liệu được cung cấp | 18.664 |
| Bình luận còn nhãn sentiment người | **425** |
| Ứng viên gán nhãn chưa duyệt | **6.968** |

Dữ liệu local nằm tại `outputs/canonical/versions/filtered_20261112_final/`:

- `comments.csv`: dữ liệu sau lọc; `text_raw` và `text_minimal` là hai cột riêng.
- `exclusions.csv`: ID bị loại và lý do.
- `annotation_candidates.local.csv`: danh sách ứng viên gán nhãn, chưa phải bộ nhãn đã duyệt.
- `manifest.json`: checksum các artifact; lịch sử nhãn và thông tin chống leakage nằm cùng thư mục.

Chính sách lọc: loại bình luận legacy có `_` trong raw hoặc dài **trên 1.000 ký tự**;
Facebook trên 1.000 ký tự được giữ để review. Không loại chỉ vì câu ngắn, có emoji
hay teencode. Near-duplicates được đánh dấu/bảo vệ, không tự xóa ý kiến độc lập.

**Dataset này đang chờ duyệt chất lượng, chưa được dùng để train lại.** 425 nhãn
người là dữ liệu phát triển còn lại sau lọc, không phải independent gold test.
Các kết quả thí nghiệm trước đây được ghi riêng trong [lịch sử dự án](docs/PROJECT_HISTORY.md).

## Cài đặt và chạy trong VS Code

Dùng Python 3.12, mở terminal PowerShell tại root repository:

```powershell
# Chỉ tạo môi trường nếu chưa có .venv
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements/classical-base.txt
python -m pip install -r requirements/crawler.txt
```

Nếu máy đã có `.venv`, chỉ cần kích hoạt. Trong VS Code, chọn interpreter
`.venv/Scripts/python.exe`. Mở `cmt-tag.code-workspace` để xem repo và thư mục
dữ liệu sau lọc. Chỉ dùng một môi trường cho workflow hiện tại.

## Các lệnh chính

Chạy sau khi kích hoạt `.venv`. Những giá trị viết hoa là placeholder cần thay
bằng đường dẫn hoặc ID thực tế; thêm `--help` để xem đầy đủ tham số.

```powershell
# 1. Crawl: nhập mã phim rồi dán lần lượt các link Facebook
python -m src.crawler interactive --channel brave

# 2. Tạo bản lọc mới từ canonical nguồn đã xác minh
python scripts/build_master_dataset.py --filter-canonical outputs/canonical/versions/rebuild_20261112 --legacy-max-characters 1000 --output outputs/canonical/versions/NEW_FILTERED

# 3. Xuất task gán nhãn từ prepared records và split hợp lệ
python -m src.annotation export --data-root DATA_ROOT --version VERSION --split train --count 150 --output NEW_TASK

# 4. Nhập quyết định của người gán
python -m src.annotation import-human --task TASK_JSON --csv LABELS_CSV --annotator NAME --blind --output NEW_EVENTS

# 5. Huấn luyện từ release đã qua kiểm tra
python -m src.models train --release APPROVED_RELEASE --train-mode gold-only --output NEW_RUN

# 6. Đánh giá run đã huấn luyện
python -m src.models evaluate --run NEW_RUN --output NEW_EVALUATION
```

Build cũng nhận `--config CONFIG --output-root DATA_ROOT` để chuẩn bị records và
split. Export annotation yêu cầu prepared data; train yêu cầu release hợp lệ.
Hiện chưa có approved release cho dataset filtered, nên không đưa trực tiếp CSV
vào train. Output đã tồn tại không được ghi đè. Clone repo không tự có toàn bộ
raw, coordinator và model local cần cho các lệnh trên.

## Gold test: post mới, một người gán

File link: `outputs/gold/posts.csv`, cột `movie_id,post_url`. Chọn link trước khi
đọc comment. Quy trình có năm lệnh; **người dùng tự crawl**, các lệnh còn lại
không mở trình duyệt. Thay `RUN_ID` bằng run vừa crawl xong:

```powershell
python -m src.crawler crawl-batch --input outputs/gold/posts.csv --max-comments 100 --channel brave
python -m src.annotation gold sample --run RUN_ID
python -m src.annotation gold recheck --annotator user
python -m src.annotation gold agreement
python -m src.annotation gold evaluate
```

`sample` tái dùng exporter hiện có; cũng nhận `--export PATH` nếu đã có export.
Lệnh ghi SHA file link vào `outputs/gold/manifest.json` trước các bước khác,
từ chối post/comment cũ và reserve toàn bộ post mới khỏi AI/train. Chỉ lọc text
rỗng và exact duplicate trong batch; không lọc quality REVIEW, từ khóa hay độ dài.
DOM chỉ được chọn khi chứng minh là raw bị xóa không quá `mention_count` đoạn
tên hợp lệ; còn lại giữ raw. Near-duplicate với dữ liệu cũ giữ lại, gắn cờ.
Cap crawl lấy trực tiếp từ config run, phải là số nguyên **1–200**; tổng record
mỗi post (kể cả truncated còn trong journal) không được vượt cap đó. Cap được
ghi vào manifest, receipt và mô tả lấy mẫu, không mặc định là 60.
SHA/bản sao danh sách link nằm ở `outputs/gold/input_seals/` cùng thời điểm thực
tế; niêm phong sau khi crawl bắt đầu không được gọi là khóa trước crawl.
Lấy mẫu seed **20261113**, tối đa **12/post, 100/group, 36/phim, 300 câu**;
thiếu thì báo đúng số và cap chặn, không nới quota.

Điền `gold_test.xlsx` (id/text không sửa; label POS/NEG/NEU/REVIEW/EXCLUDE).
`recheck` chỉ chạy sau khi điền đủ, xuất `gold_recheck.xlsx`: ngẫu nhiên tối đa
100 ID cho **cùng người gán**, không hiện nhãn cũ. Thực hiện trong **<1 ngày**.
`agreement` tính **intra-annotator** agreement/Kappa và confusion matrix; nếu
lệch, điền `label_final` trong `gold_disagreements.xlsx` rồi chạy lại cùng lệnh
với `--final`. Code giữ cả hai nhãn ban đầu, chỉ khóa test sau quyết định cuối.
REVIEW/EXCLUDE không bị ép thành NEU và không vào metrics sentiment.

`evaluate` chỉ dùng test đã khóa và chạy **đúng một lần**; receipt được ghi
trước fit/predict, kể cả chạy lỗi cũng không tự cho phép thử lại. Code loại
train trùng/near-trùng hoặc vướng reservation, không bypass guard. Bốn cấu hình
cố định: BoW + ComplementNB/MNB; TF-IDF từ + LinearSVC balanced; TF-IDF char_wb
(3,5) + LinearSVC balanced. Không tune trên gold. Kết quả và bốn confusion PNG
ở `outputs/gold/results/`; mọi file chứa comment chỉ local, không commit.

Đây là test **một người gán**, recheck 100 câu trong <1 ngày; nguồn là tối đa
Số comment đầu/post bị giới hạn bởi `max_comments` thực tế trong config (1–200),
theo thứ tự Facebook hiển thị. Không coi là lấy mẫu ngẫu
nhiên toàn Facebook hoặc inter-annotator agreement. Trong task chuẩn bị code,
chỉ chạy fixture: chưa crawl, train hay evaluate gold thật.

## Cấu trúc repository

```text
src/
  crawler/        Thu thập Facebook, journal, resume và export
  data/           Import, schema, kiểm tra chất lượng và chia nhóm
  dataset/        Lọc canonical, provenance và bảo vệ test
  preprocessing/  Tiền xử lý tối thiểu
  annotation/     Task, nhãn người, agreement và release
  models/         BoW/TF-IDF, mô hình và đánh giá
scripts/          Entry point build/filter
configs/          Cấu hình nguồn và fixture
requirements/     Dependencies và lock cần tái lập
tests/           Unit tests và fixture
docs/            Guideline, hướng dẫn, báo cáo lọc và lịch sử
data/            Snapshot dữ liệu/nhãn đã lưu
outputs/         Dataset và kết quả local
```

## Kiểm thử và tài liệu

```powershell
python -m unittest discover -s tests
```

- [Guideline gán nhãn V2.1](docs/guidelines/MOVIE_SENTIMENT_V2_1.md)
- [Hướng dẫn crawler và xử lý lỗi](docs/CRAWLER.md)
- [Báo cáo lọc dữ liệu](docs/DATASET_FILTER_REPORT.md)
- [Chỉ mục dữ liệu local](outputs/README.md)
- [Lịch sử thử nghiệm và các hướng đã bỏ](docs/PROJECT_HISTORY.md)

Raw, nhãn người, frozen splits, checkpoint và kết quả cũ được giữ nguyên.
Các hướng xử lý v3.1/v3.2 không còn là mặc định. Code và tài liệu trước đợt dọn
được lưu tại tag `before-cleanup-20261112`; không cần chạy lại các phase cũ.
