# Mục lục tài liệu

## Đang sử dụng

| Nội dung | Tài liệu |
| --- | --- |
| Gán nhãn theo guideline hiện tại | [V2.1](guidelines/MOVIE_SENTIMENT_V2_1.md) |
| Audit legacy, task 250 và kết quả import 186 sentiment/64 EXCLUDE | [Phase G.2](PHASE_G2_LEGACY_AUDIT.md) |
| Master và điều kiện independent test | [Phase G](PHASE_G_REPORT.md) |
| Crawl không count cap, quota test và platform | [Điều chỉnh G.1](PHASE_G1_UPDATE.md) |
| Chuẩn bị danh sách bài, receipt, preflight và text_view | [Luồng intake](PHASE_G_FOLLOWUP.md) |
| Cách chạy crawler hiện có | [Crawler CLI](CRAWLER.md) |
| Vị trí dữ liệu và kết quả local | [Mục lục outputs](../outputs/README.md) |

## Kết quả mô hình đã khóa

| Mục đích | Tài liệu |
| --- | --- |
| Baseline 346 nhãn người | [Development baseline](DEVELOPMENT_BASELINE.md) |
| Thử tiền xử lý tiếng Việt | [Phase E](PHASE_E_REPORT.md) |
| BoW và repeated grouped CV | [Phase E.1](PHASE_E1_REPORT.md) |
| Cross-domain ranking diagnostic | [Phase E.2](PHASE_E2_REPORT.md) |
| Unified 532 human labels and normalization ablation (PARTIAL; frozen-fold isolation blocker) | [Phase G.3](PHASE_G3_REPORT.md) |
| Giant component audit and direct-isolation development ablation | [Phase G.3.1](PHASE_G3_1_REPORT.md) |
| Parent/reply leakage verification and legacy OOF diagnostics | [Phase G.3.2](PHASE_G3_2_REPORT.md) |

## Hợp đồng và lịch sử

- [Schema/provenance](DATA_SCHEMA.md).
- [Annotation tooling](PHASE_C_REPORT.md), [baseline tooling](PHASE_D_REPORT.md).
- [Guideline V2.0 bất biến](guidelines/MOVIE_SENTIMENT_V2_0.md).
- [Audit ban đầu](REPO_AUDIT_PHASE_A.md), [Phase B](PHASE_B_REPORT.md),
  [quyết định nguồn legacy](PHASE_0_DATA_AUDIT.md),
  [audit dọn repository](REPO_CLEANUP_AUDIT.md).
- Các báo cáo crawl, patch, figures và annotation review vẫn giữ đường dẫn
  cũ để truy xuất lịch sử. Không đổi tên/move chúng chỉ để thay cách hiển thị.
