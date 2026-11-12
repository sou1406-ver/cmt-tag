# Dữ liệu và kết quả local

Dataset hiện tại: `canonical/versions/filtered_20261112_final/`.
**25.810 comment; 425 nhãn sentiment người; 6.968 ứng viên chưa được duyệt.**

| File | Mục đích |
| --- | --- |
| [comments.csv](canonical/versions/filtered_20261112_final/comments.csv) | Xem dữ liệu sau lọc, cột raw và minimal riêng |
| [exclusions.csv](canonical/versions/filtered_20261112_final/exclusions.csv) | ID đã loại và lý do, không xóa nguồn gốc |
| [annotation_candidates.local.csv](canonical/versions/filtered_20261112_final/annotation_candidates.local.csv) | Ứng viên gán nhãn; chưa phải task được duyệt |
| `human_history.local.jsonl` | Giữ lịch sử quyết định người, kể cả mẫu đã loại |
| `protection.local.json`, `direct_near_duplicates.local.csv` | Frozen-test/leakage protection và near-duplicate evidence |
| `manifest.json`, `summary.json` | Checksum và thống kê |

Raw/provenance nguồn vẫn được lưu. Canonical nguồn ở
`canonical/versions/rebuild_20261112/`; các output/model/nhãn cũ giữ nguyên tại
vị trí đã pin. Không di chuyển hay xóa các folder đó chỉ để Explorer trông gọn.
Chúng là bằng chứng lịch sử, không phải những bước phải chạy lại.

Quy trình chính: [README](../README.md). Quy tắc lọc và số liệu:
[báo cáo lọc](../docs/DATASET_FILTER_REPORT.md). Các hướng đã bỏ:
[lịch sử](../docs/PROJECT_HISTORY.md).

Không tự đổi active pointer hoặc approve candidate. Không commit comment data mới.
Chỉ mục này được đưa lên Git; những file local được liên kết ở trên không tự có
khi clone repository. Snapshot `data/canonical/` trên Git là bản review cũ.
