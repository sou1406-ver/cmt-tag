# Sentiment bình luận phim tiếng Việt

Python CLI cho **POS / NEG / NEU**. Luồng chính:
**Crawl Facebook + dữ liệu được cung cấp → Lọc/tiền xử lý → Gán nhãn → Train → Đánh giá**.

Dataset hiện tại: **25.810 comment**, **425 nhãn sentiment người**, **6.968 ứng viên gán nhãn chưa duyệt**.
Bản local: `outputs/canonical/versions/filtered_20261112_final/comments.csv`.
`text_raw` giữ nguyên; `text_minimal` là cột riêng. Candidate chưa quality-approved,
không tự đổi active pointer hoặc coi các nhãn development là independent gold test.

## Quy trình dự án

| Bước | Công việc và trạng thái |
| --- | --- |
| Thu thập | Crawl Facebook theo phim/bài đăng, giữ ID và provenance; bổ sung bộ CSV khoảng 29k được bạn cung cấp. Nguồn ban đầu/nhãn `overall` của CSV chưa xác minh. |
| Lọc dữ liệu | Canonical 38.642 → 25.810 dòng; loại legacy có `_`, quá 1.000 ký tự, lỗi rõ ràng, human EXCLUDE và exact duplicates. Không xóa raw. |
| Tiền xử lý | NFC, HTML entities hợp lệ, CRLF/NBSP và trim; giữ emoji, emoticon, dấu câu, phủ định và teencode. Kiểm quality/leakage trước khi dùng. |
| Gán nhãn | POS/NEG/NEU theo guideline V2.1; REVIEW/EXCLUDE giữ trong lịch sử. Hiện có 425 nhãn sentiment còn lại, 6.968 ứng viên chưa duyệt. |
| Huấn luyện | BoW/TF-IDF với NB/LR/SVM; fit đặc trưng trên train, chia theo nhóm bài và chống trùng. Chỉ chạy khi có release hợp lệ. |
| Đánh giá | Macro-F1, precision/recall/F1 từng lớp và confusion matrix; phân biệt development CV với test độc lập. |

Đây là quy trình chính để trình bày BTL. Các hướng thử rồi bỏ và số đo cũ
chỉ nằm trong [lịch sử dự án](docs/PROJECT_HISTORY.md); không cần kể lại từng phase.
**Chưa train lại trên 25.810 dòng** vì candidate chưa được duyệt; không lấy kết quả
baseline cũ làm kết quả của dataset này.

## Setup

Chạy PowerShell tại root repo; dùng Python 3.12 và **một `.venv` duy nhất**:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements/classical-base.txt
.\.venv\Scripts\python.exe -m pip install -r requirements/crawler.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Máy làm việc đã có `.venv`; không cần tạo lại. Trong VS Code chọn interpreter
`.venv/Scripts/python.exe`; mở `cmt-tag.code-workspace` để thấy repo và dữ liệu sau lọc.
Không cần các môi trường mang tên phase cũ.

Build/filter và xử lý nhãn dùng standard library. Các test DOM cần Selenium và
Chrome/Brave; test model cần sklearn. Không nâng package/pin trong lần dọn này.
`requirements/locks/classical-windows-py312.txt` giữ nguyên để tái lập môi trường cũ.

## Sáu lệnh chính

Dùng Python của môi trường đã cài dependencies. Trước tiên có thể thêm `--help`.

| Việc | Lệnh |
| --- | --- |
| Crawl | `python -m src.crawler interactive --channel brave` |
| Build/filter | `python scripts/build_master_dataset.py --filter-canonical outputs/canonical/versions/rebuild_20261112 --legacy-max-characters 1000 --output outputs/canonical/versions/NEW_FILTERED` |
| Export annotation | `python -m src.annotation export --data-root DATA_ROOT --version VERSION --split train --count 150 --output NEW_TASK` |
| Import annotation | `python -m src.annotation import-human --task TASK_JSON --csv LABELS_CSV --annotator NAME --blind --output NEW_EVENTS` |
| Train | `python -m src.models train --release APPROVED_RELEASE --train-mode gold-only --output NEW_RUN` |
| Evaluate | `python -m src.models evaluate --run NEW_RUN --output NEW_EVALUATION` |

Các placeholder phải thay bằng artifact đúng contract. Export nhận **prepared records/split**;
train nhận **release đã qua kiểm tra**. Candidate filtered chưa được duyệt nên chưa có
approved release tương ứng; không đưa thẳng CSV vào train để bỏ qua quality/leakage guards.
Build cũng nhận `--config CONFIG --output-root DATA_ROOT` cho prepared records/split;
chỉ dùng cấu hình nguồn được phê duyệt, không dùng `overall` legacy làm ground truth.
Các gate `agreement`/`release` thuộc cùng CLI annotation, không phải pipeline phase mới.
Đường dẫn output đã tồn tại bị từ chối ghi đè. Cleanup không chạy crawl, AI hay train dữ liệu thật.

Tiền xử lý dùng một implementation: `from src.preprocessing import preprocess`.
Chỉ NFC, HTML entities hợp lệ ngoài URL/email/code, CRLF/NBSP và trim hai đầu;
giữ khoảng trắng nội bộ, emoji/emoticon, dấu `-`, phủ định và teencode.
Legacy raw có `_` hoặc >1.000 ký tự bị loại; Facebook >1.000 được giữ REVIEW.
Exact duplicates được loại có ledger; near-duplicates chỉ đánh dấu/bảo vệ leakage.

## Cấu trúc

```text
src/crawler/        Selenium, DOM, journal/resume và export
src/data/           import, schema, quality và grouped split
src/dataset/        canonical filter, lineage I/O và frozen-test guards
src/preprocessing/  một bộ tiền xử lý tối thiểu
src/annotation/     task, human events, agreement và release gates
src/models/         BoW/TF-IDF, NB/LR/SVM và đánh giá
scripts/            một entry point build/filter
configs/            cấu hình nguồn/fixture cần thiết
requirements/       dependencies hiện tại và lock lịch sử
tests/             fixture và regression cho chức năng còn giữ
```

[Guideline V2.1](docs/guidelines/MOVIE_SENTIMENT_V2_1.md) ·
[Quy tắc/số liệu lọc](docs/DATASET_FILTER_REPORT.md) ·
[Crawler](docs/CRAWLER.md) · [Lịch sử dự án và cleanup](docs/PROJECT_HISTORY.md).

Raw, labels, provenance, test reservations, checkpoint và kết quả local giữ nguyên.
Snapshot cũ trong `data/` vẫn nguyên byte; không phải filtered candidate hiện tại.
Code/tài liệu thực nghiệm cũ được truy xuất tại tag **`before-cleanup-20261112`**,
không cần chạy lại Phase A–J. Quy trình v3.1/v3.2 đã ngừng dùng làm mặc định.
