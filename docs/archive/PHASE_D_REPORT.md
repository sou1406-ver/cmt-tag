# Phase D — Baseline CLI, fixture-only

## Cài đặt và chạy

Python 3.10+ theo dự án; các wheel pinned dưới đây đã kiểm chứng với CPython
3.12.14 Windows. Khi dùng Python khác cần phiên bản package có wheel tương thích.
Dependency riêng, không sửa requirements-data.txt của Phase B:

```powershell
.\.venv-crawler\Scripts\python.exe -m pip install -r requirements-baseline.txt
.\.venv-crawler\Scripts\python.exe scripts/make_baseline_fixture.py --output outputs/phase_d_demo
.\.venv-crawler\Scripts\python.exe -m src.baseline train --release outputs/phase_d_demo/release --output outputs/phase_d_demo/models --usage-root outputs/phase_d_demo/usage
.\.venv-crawler\Scripts\python.exe -m src.baseline evaluate --run outputs/phase_d_demo/models --output outputs/phase_d_demo/final
```

Các thư mục output phải mới; không ghi đè. Fixture JSON có 210 dòng, nhãn kỳ vọng
được tác giả fixture định nghĩa, không phải annotation người thật. Source namespace,
post IDs, provenance, release và mọi báo cáo đều chỉ rõ synthetic. Near-duplicate
heuristic bị tắt cho fixture bằng min_chars=10000 vì các template cố tình lặp;
không áp dụng config này lên dữ liệu thật. Không coi fixture là thử nghiệm chống
leakage thực địa; kiểm thử group/near/exact đã có riêng trong tests Phase B/C.

## Thiết kế thực nghiệm

- BoW và TF-IDF; word unigram/unigram+bigram; NB alpha=1; LR/LinearSVC C=1,
  class_weight None/balanced. NB không áp dụng class_weight. Tổng 20 candidates
  dev, 6 champions theo cell + Majority. Tie-break cố định theo thứ tự khai báo.
- Fit vectorizer/model chỉ train; dev chọn ngram/weight và winner bằng Macro-F1.
  Không fit lại bằng dev, không xem dự đoán test trước khi selection.json lưu.
- Evaluate tính cả 7 mô hình đã chốt trước trên cùng test một lần, không dùng
  test để chọn winner. Registry riêng khóa ID test; tune thêm hoặc evaluate lặp
  cùng test qua thư mục output khác bị chặn. Registry phải dùng cùng một
  `--usage-root` xuyên thực nghiệm; đổi/xóa registry không tạo ra test độc lập.
- Registry được đặt trước khi predict để một lần đánh giá bị ngắt vẫn được
  coi là đã mở test. Không tự xóa để chạy lại và không sửa release bất biến.
- Model/vectorizer joblib, config/seed/version/code hash, train/tune IDs,
  checksum, dev scores, predictions, metrics, comparison CSV và error analysis.
  Chỉ nạp joblib do chính pipeline tạo và tin cậy, không tải model lạ để load.
- Guard release phải ready, holdout locked, gold human confirmed/blind hoặc
  EXCLUDE human blind (không tính metric). Machine holdout, unresolved REVIEW,
  duplicate conflict hoặc nhóm đã dùng trái phép đều bị từ chối.
- Train mode `--train-mode mixed|silver-only|gold-only`; silver vẫn ghi origin
  silver. Người đã REVIEW/EXCLUDE không bị nhãn máy ghi đè. Pseudo có score/audit
  là workflow khác, không tự bật ở đây. Chưa có đủ dữ liệu thật để chạy so sánh
  gold-only/silver-only/mixed hoặc kiểm soát chênh kích thước train.

## Kết quả CLI thực tế trên fixture (không phải kết quả nghiên cứu)

Run local `outputs/phase_d_demo`: train/dev/test = 126/42/42, test support
POS 16, NEG 9, NEU 17. Dev chọn bow_nb (tie theo thứ tự cố định).

| Cell | Accuracy | Macro Precision | Macro Recall | Macro-F1 |
|---|---:|---:|---:|---:|
| BoW × NB | 1.000 | 1.000 | 1.000 | 1.000 |
| BoW × LR | 1.000 | 1.000 | 1.000 | 1.000 |
| BoW × LinearSVC | 1.000 | 1.000 | 1.000 | 1.000 |
| TF-IDF × NB | 1.000 | 1.000 | 1.000 | 1.000 |
| TF-IDF × LR | 1.000 | 1.000 | 1.000 | 1.000 |
| TF-IDF × LinearSVC | 1.000 | 1.000 | 1.000 | 1.000 |
| Majority | 0.2143 | 0.0714 | 0.3333 | 0.1176 |

Template rất dễ và lặp từ lớp nên điểm 1.0 là điều dễ đoán; không chứng minh
khả năng hiểu mỉa mai/phủ định hoặc khái quát phim khác. Sáu model có confusion
matrix diag(16,9,17); metrics.json có P/R/F1/support từng lớp và thời gian
fit/predict thực đo, comparison.csv có bảng chéo. Error analysis chứa lỗi
Majority; tag chỉ là candidate để review thủ công, không phải nhãn nhóm lỗi
đã xác minh. Không có lỗi model trên fixture này không có nghĩa hệ thống hết lỗi.

## Kiểm chứng và giới hạn

`tests/test_baseline.py` kiểm tra end-to-end, 7 cell, vocabulary không chứa token
chỉ test có, deterministic selection/metrics, confusion 3×3 cả khi prediction
thiếu lớp, từ chối test machine labels, silver train hợp lệ và model checksum.
Fixture không thay thế ngân sách gold dev>=200/test>=300. Các lớp có ít mẫu cần
báo support và độ bất định, không kết luận từ vài F1; báo cáo tự ghi cảnh báo.
Challenge làm giàu lớp hiếm chưa được dựng từ nguồn thật và không được trộn với
Accuracy test đại diện. Chưa có nghiên cứu teacher-student/distillation thật.

`.gitattributes` bổ sung riêng cho guideline nguyên bản: giữ byte và chấp nhận
hai dấu cách Markdown hard-break. Đã xác minh checksum working tree và Git blob
đều trùng bản gốc, không chỉnh nội dung guideline để làm whitespace check pass.

Tham khảo API: [CountVectorizer](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.CountVectorizer.html),
[metrics](https://scikit-learn.org/stable/modules/model_evaluation.html).

Trước commit Phase D: **64 tests PASS, không skip** (60 trước D + 4 baseline),
compileall và git diff check pass. Không chạy train/evaluate trên 29k.
