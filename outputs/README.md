# Canonical candidate mới — 12/11/2026

V3.2 candidate bàn giao **local, chưa approved**:
`canonical/versions/cleaning_v3_2_candidate/`; workbook duy nhất
`canonical/versions/cleaning_v3_2_candidate/review/cleaning_review.xlsx` (100 blank decisions).
Repro17/17 artifacts: `canonical_support/cleaning_v3_2_candidate_repro/`;
verification: `canonical_support/cleaning_verification_v2/`.
Xem [cleaning report](../docs/CLEANING_V3_2_REPORT.md); không thay snapshot public v3.1.

[`data/canonical`](../data/canonical/README.md) chứa bản dữ liệu được người dùng
yêu cầu đưa lên Git để review. Phần local còn lại không tự có khi clone.

| Thành phần local | Đường dẫn |
| --- | --- |
| Raw curated + normalized + historical decisions, sealed manifest | `canonical/versions/rebuild_20261112/` |
| Workbook quality200 mới, chưa điền | `canonical/review/canonical_quality_review.xlsx` |
| Rebuild độc lập21/21 hashes giống nhau | `canonical_support/rebuild_repro/` |

Candidate38.642 records/524 retained sentiment, chưa source switch/quality approval.
Các bảng dưới là snapshot lịch sử, không phải số liệu canonical mới nhất.


# Dữ liệu và kết quả local

Chỉ mục lục này được đưa lên Git. CSV, workbook, model, snapshot và coordinator
giữ local theo `.gitignore`. Các đường dẫn bên dưới có trên máy làm việc;
checkout code trên máy khác không tự có những dữ liệu này.

## File đang dùng

| Cần làm gì | Đường dẫn |
| --- | --- |
| Domain/spam v3.1, cùng 200 ID I.4, bản cần điền hiện tại | [semantic_quality_review_v31_200.xlsx](phase_j/semantic_workbook_v1/semantic_quality_review_v31_200.xlsx) |
| Quality holdout, đúng 40 ID reservation, chưa có quyết định | [quality_holdout_40.xlsx](phase_j/holdout_workbook_v1/quality_holdout_40.xlsx) |
| Readiness, status, eligibility funnel, delta và coordinator Phase J | `phase_j/v2/` |
| Full-corpus/workbook/protected-input verification Phase J | `phase_j/verification_v1/` |
| Duyệt normalization I.4.1, 150 câu, chưa duyệt | [final_normalization_review_150.xlsx](phase_i4_1/workbook_v2/final_normalization_review_150.xlsx) |
| Đề xuất normalized từ raw, events, source audit và manifest I.4.1 | `phase_i4_1/v2/` |
| Kiểm chứng bất biến, idempotence và workbook I.4.1 | `phase_i4_1/verification_v1/` |
| Workbook domain/spam I.4, chưa có nhãn người | [semantic_quality_review_200.xlsx](phase_i4/workbook_v2/semantic_quality_review_200.xlsx) |
| Format summary, sampling probabilities, readiness và holdout I.4 | `phase_i4/v5/` |
| Workbook kiểm định format I.3, 200 câu | [plain_text_validation_200.xlsx](phase_i3/workbook_v3/plain_text_validation_200.xlsx) |
| Token audit, Facebook funnel và candidate I.3 chưa duyệt | `phase_i3/v3/` |
| Workbook plain text I.2 giữ làm lịch sử | [quality_review_200.xlsx](phase_i2/workbook_v1/quality_review_200.xlsx) |
| Corpus/candidate/audit Phase I.2 chưa duyệt | `phase_i2/v2/` |
| Duyệt chất lượng 200 câu Phase I.1 (để trống sentiment) | [quality_review_200.csv](phase_i1/v2/quality_review_200.csv) |
| Pilot mới chỉ để xem trước, chưa gửi AI | [pilot_500_candidate.csv](phase_i1/v2/pilot_500_candidate.csv) |
| 186 nhãn sentiment đã nhập | [sentiment.csv](phase_g2/human_import_01/sentiment.csv) |
| 64 quyết định EXCLUDE giữ riêng | [excluded.csv](phase_g2/human_import_01/excluded.csv) |
| Đủ 250 quyết định đã chuẩn hóa | [decisions.csv](phase_g2/human_import_01/decisions.csv) |
| History, receipt và input snapshot | [human_import_01/](phase_g2/human_import_01) |
| Workbook 250 câu người dùng đã gán | [legacy_train_candidates.xlsx](phase_g2/annotation_task/legacy_train_candidates.xlsx) |
| Audit toàn bộ 29.688 dòng legacy | [legacy_quality_report.json](phase_g2/legacy_audit/legacy_quality_report.json) |
| Master 39.842 records, gồm nguồn chưa xác minh | [master.csv](phase_g/master/master.csv) |
| 400 quyết định development ban đầu | [annotations.csv](development/reviewed/annotations.csv) |
| Corpus hợp nhất 532 nhãn và audit chuẩn hóa (local, immutable) | `phase_g3/unified/` |
| Tái lập baseline và bằng chứng blocker fold Phase G.3 (local) | `phase_g3/ablation/` |
| Audit giant component và ablation theo direct-isolation protocol (local) | `phase_g31/` |
| Parent/thread audit, error analysis OOF, legacy recheck candidates (local) | `phase_g32/` |
| Phase I unified corpus, local cleaning audit and 500-row blind pilot | `phase_i/v5/` |

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
| Giant component audit và direct-overlap development ablation | `phase_g31/` |
| Parent/reply leakage và legacy diagnostics | `phase_g32/` |
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
