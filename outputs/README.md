# Dữ liệu và kết quả local

Chỉ mục lục này được đưa lên Git. CSV, workbook, model, snapshot và coordinator
giữ local theo `.gitignore`. Các đường dẫn bên dưới có trên máy làm việc;
checkout code trên máy khác không tự có những dữ liệu này.

## File đang dùng

| Cần làm gì | Đường dẫn |
| --- | --- |
| 186 nhãn sentiment đã nhập | [sentiment.csv](phase_g2/human_import_01/sentiment.csv) |
| 64 quyết định EXCLUDE giữ riêng | [excluded.csv](phase_g2/human_import_01/excluded.csv) |
| Đủ 250 quyết định đã chuẩn hóa | [decisions.csv](phase_g2/human_import_01/decisions.csv) |
| History, receipt và input snapshot | [human_import_01/](phase_g2/human_import_01/) |
| Workbook 250 câu người dùng đã gán | [legacy_train_candidates.xlsx](phase_g2/annotation_task/legacy_train_candidates.xlsx) |
| Audit toàn bộ 29.688 dòng legacy | [legacy_quality_report.json](phase_g2/legacy_audit/legacy_quality_report.json) |
| Master 39.842 records, gồm nguồn chưa xác minh | [master.csv](phase_g/master/master.csv) |
| 400 quyết định development ban đầu | [annotations.csv](development/reviewed/annotations.csv) |
| Corpus hợp nhất 532 nhãn và audit chuẩn hóa (local, immutable) | `phase_g3/unified/` |
| Tái lập baseline và bằng chứng blocker fold Phase G.3 (local) | `phase_g3/ablation/` |

186 nhãn mới ở `human_import_01` chưa tự merge vào release cũ hoặc dùng train.
Không sửa ID/text trong workbook. Nếu gán lại rồi import, chọn output mới;
không ghi đè history hoặc snapshot cũ. Coordinator chứa nhãn legacy/provenance,
không dùng thay workbook để gán mù.

## Lịch sử theo nhóm công việc

| Nhóm | Thư mục |
| --- | --- |
| Dữ liệu phát triển và nhãn người | `development/`, `annotation_a_20261110/`, `review_multifilm_20261110/` |
| Mô hình và thí nghiệm khóa | `phase_e/`, `phase_e1/`, `phase_e2/` |
| Master, exposure, blind test preparation | `phase_g/`, `phase_g1/` |
| Legacy audit, task và import hiện tại | `phase_g2/` |
| Unified human dataset và normalization ablation | `phase_g3/` |
| Crawl/export các đợt trước | `fresh_fb_*`, `group_*`, `high_activity_*`, `diverse_sources_*`, `diversity_*`, `facebook_5k_*` |
| Pilot và chọn mẫu cũ | `source_quality_pilot_*`, `pilot_format_*`, `negative_annotation_*` |
| Kiểm tra, demo, support và snapshot thử | `*_support/`, `*_smoke/`, `scope_diagnosis/`, `cleanup_audit_*`, `merge_fb_*`, `phase_d_demo/`, `release_fix_wip/` |

Các folder này giữ nguyên trên đĩa. Nhiều path/checksum được manifest ghi nhận,
nên không gom/move/xóa lịch sử theo tên folder. Không coi support hoặc bản sao
export là một nguồn dữ liệu mới khi hợp nhất.

## Xem gọn trong VS Code

Mở [cmt-tag.code-workspace](../cmt-tag.code-workspace): nhãn đã nhập và workbook
được ghim thành hai folder riêng, phần code/tài liệu nằm trong `Repo`.
Terminal vẫn bắt đầu ở root repository để các lệnh Python dùng đúng path.

Explorer ẩn cache, virtualenv, browser profile/cache và cây `outputs` trong
root repo. Đây chỉ là cấu hình hiển thị, không xóa file. Mở file theo các link
trên hoặc File → Open Folder → `outputs` để xem toàn bộ lịch sử; có thể tắt
`files.exclude.outputs` trong `.vscode/settings.json` nếu cần hiện lại ở root.
