# Sentiment bình luận phim tiếng Việt

Pipeline Python CLI phân loại **POS / NEG / NEU**, giữ provenance và chống
leakage. Không xây web/dashboard.

**Hiện tại: DATASET_FREEZE_PENDING.** Có 39.842 raw records, 650 quyết định
người và 532 nhãn sentiment. Normalization candidate là plain_text_v3_1;
9.788 records ở mức proposed, **0 approved**. Đang chờ review format,
normalization, domain/spam và quality holdout. Chưa phát hành pilot500 mới.

## Quickstart

Chạy từ root repo với môi trường đã setup:

```powershell
.\.venv-phase-e\Scripts\python.exe -m src.dataset.quality_review --help
.\.venv-phase-e\Scripts\python.exe -m unittest discover -s tests
```

[Setup môi trường](docs/guides/ENVIRONMENT.md) phân biệt classical/crawler và
Transformer; không cài chung các pin NumPy/sklearn không tương thích.
[File cần người dùng điền và lệnh import](docs/QUALITY_REVIEW_HANDOFF.md).
Output đã tồn tại không được ghi đè; dữ liệu/workbook local không tự có khi clone.

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
