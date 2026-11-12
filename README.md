# Sentiment bình luận phim tiếng Việt

Pipeline Python CLI phân loại **POS / NEG / NEU**, giữ provenance và chống
leakage. Không xây web/dashboard.

**Hiện tại: REBUILD_VERIFIED / QUALITY_REVIEW_PENDING.** Đã rebuild từ raw,
loại đúng block 1.200 dòng legacy; còn **38.642 records**, 642 quyết định người
và **524 nhãn sentiment**. Không thay nhãn, không duyệt corpus, không train/API.

[Dữ liệu canonical để kiểm tra](data/canonical/README.md) được đưa lên Git theo
yêu cầu chủ repo: CSV raw/normalized tách cột, ledger loại và workbook 200 câu.
Đây là snapshot chờ review, **không phải dataset đã được duyệt**.

Candidate mới [plain_text_v3_2](docs/CLEANING_V3_2_REPORT.md) đã chạy trên đủ
38.642 dòng: 1.833 view thay đổi, nhãn/raw giữ nguyên, pool đề xuất8.812/approved0.
Corpus và workbook100 mới giữ **local** tại `outputs/canonical/versions/cleaning_v3_2_candidate/`;
snapshot Git v3.1 không bị thay thế, active pointer chưa đổi.

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
