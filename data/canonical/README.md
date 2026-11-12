# Canonical dataset để kiểm tra

Version: **canonical_37cf670237e3398b5c96**; REBUILD_VERIFIED /
QUALITY_REVIEW_PENDING. Chia sẻ theo yêu cầu chủ repository, chưa duyệt train/AI.

- [comments.csv](canonical_37cf670237e3398b5c96/comments.csv): đủ38.642 retained
  records, text_raw và text_normalized riêng, source/provenance và nhãn người cũ.
- [exclusions.csv](canonical_37cf670237e3398b5c96/exclusions.csv):1.200 dòng bị loại,
  source IDs/hash/lý do và quyết định lịch sử; không trộn comment bị loại lại corpus.
- [Workbook review200](canonical_37cf670237e3398b5c96/canonical_quality_review.xlsx).
- [Manifest/checksums](canonical_37cf670237e3398b5c96/manifest.json) và
  [audit từng vùng raw](canonical_37cf670237e3398b5c96/source_regions.json).

Không thêm cột author/name/account-ID. Văn bản raw có thể còn tên/mention do
nguồn cũ; không tự đoán/xóa tên bằng regex. Original legacy provenance chưa
xác minh; overall không phải gold. Active pointer chưa đổi, approved0.
Nguồn gốc đầy đủ/exclusion raw/history immutable vẫn local. Xem
[readiness](../../docs/DATASET_QUALITY_READINESS_REPORT.md) để biết giới hạn.
