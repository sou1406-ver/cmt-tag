# Sentiment bình luận phim tiếng Việt

Pipeline Python CLI phân loại **POS / NEG / NEU**, giữ provenance và chống
leakage. Không xây web/dashboard.

**Hiện tại: filtered candidate 25.810 comment, chưa quality-approved.**
Facebook7.146 /legacy18.664;425 nhãn sentiment người còn lại. Đã bỏ legacy
chứa `_`, legacy>1.000 ký tự, human EXCLUDE và exact duplicates; không phục hồi
word segmentation. Raw và lịch sử650 quyết định giữ nguyên.

[Report lọc dữ liệu](docs/DATASET_FILTER_REPORT.md) · Dataset local:
`outputs/canonical/versions/filtered_20261112_final/comments.csv` · Pool đề xuất6.968,
**approved0**; không train/API hoặc đổi active pointer.

[Canonical snapshot cũ trên Git](data/canonical/README.md) vẫn giữ nguyên.
Corpus filtered mới không commit theo yêu cầu. Thử nghiệm v3.2 tạm dừng. Facebook>1.000 giữ REVIEW; legacy>1.000 loại. Không tự gán NEU.

## Quickstart

Chạy từ root repo với môi trường đã setup:

```powershell
.\.venv-phase-e\Scripts\python.exe -m src.dataset.quality_review --help
.\.venv-phase-e\Scripts\python.exe -m unittest discover -s tests
```

[Setup môi trường](docs/guides/ENVIRONMENT.md) phân biệt classical/crawler và
Transformer; không cài chung các pin NumPy/sklearn không tương thích.
[File cần người dùng điền và lệnh import](docs/QUALITY_REVIEW_HANDOFF.md).
Output đã tồn tại không được ghi đè; nguồn gốc và ledger đầy đủ vẫn local; snapshot review canonical có trong Git.

## Pipeline

Crawler → Raw/provenance → Preprocessing → Quality → Annotation →
Train-only features → Models → Evaluation.

- [Pipeline hiện tại](docs/CURRENT_PIPELINE.md): input/output, owner, config,
  entry point chuẩn và guards.
- [Quá trình phát triển](docs/PROJECT_EVOLUTION.md): A–J, vấn đề/cải tiến,
  kết quả và những trạng thái đã bị thay thế.
- [Kết quả thực nghiệm](docs/EXPERIMENT_RESULTS.md): protocol, metrics và
  giới hạn so sánh; development CV không phải independent test.

[Mục lục](docs/README.md) · [Bản đồ repository](docs/architecture/REPOSITORY_MAP.md) ·
[Dữ liệu local](outputs/README.md) · [Guideline V2.1](docs/guidelines/MOVIE_SENTIMENT_V2_1.md).

## Kiểm thử và bảo toàn

```powershell
python -m unittest discover -s tests
```

Giữ nguyên raw, nhãn người, guideline, split và kết quả đã khóa. Không dùng
legacy overall làm gold; không tự duyệt workbook, gọi AI, freeze/release hoặc
train chỉ để kiểm tra cấu trúc. Chức năng mới mở rộng owner hiện có trước;
cập nhật ba tài liệu tổng hợp thay vì thêm report/module theo tên phase.
