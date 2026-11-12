# Tài liệu dự án

## Ba tài liệu chính

1. [CURRENT_PIPELINE](CURRENT_PIPELINE.md): cách vận hành hiện tại, code/config,
   môi trường và các ràng buộc dữ liệu.
2. [PROJECT_EVOLUTION](PROJECT_EVOLUTION.md): quá trình A–J, khác biệt giữa
   phiên bản, kết quả đã đo và những việc vẫn pending.
3. [EXPERIMENT_RESULTS](EXPERIMENT_RESULTS.md): bảng kết quả cùng protocol,
   không trộn fixture/CV/transfer/pilot thành một leaderboard.

Hiện đang **DATASET_FREEZE_PENDING**, chưa có quality approval hoặc pilot AI
mới. Các tài liệu lịch sử có thể ghi trạng thái tại thời điểm cũ; chúng không
thay thế readiness hiện tại.

## Thao tác và hợp đồng cần tra

- [Review handoff](QUALITY_REVIEW_HANDOFF.md): file cần điền, domain/spam,
  format/normalization, quality holdout và import.
- [Môi trường](guides/ENVIRONMENT.md): một setup guide, requirement owners,
  classical/Transformer isolated runtimes và lock reproduction.
- [Crawler CLI](CRAWLER.md): journal, session/profile, interactive/resume/export.
- [Guideline V2.1](guidelines/MOVIE_SENTIMENT_V2_1.md) và
  [V2.0 lịch sử](guidelines/MOVIE_SENTIMENT_V2_0.md), giữ nguyên checksum.
- [Repository map](architecture/REPOSITORY_MAP.md) và
  [consolidation plan/policy](architecture/CONSOLIDATION_PLAN.md).
- [Schema foundation](reference/DATA_SCHEMA.md),
  [dictionary Phase I lịch sử](reference/DATA_DICTIONARY_PHASE_I.md),
  [outputs local index](../outputs/README.md).

## Evidence lịch sử

Đọc ba tài liệu chính trước. Archive giữ narrative/metrics gốc; migration chỉ
đổi đường dẫn điều hướng để links còn đúng. Không sửa frozen results hoặc
guideline. Các file giữ ở path cũ vì runtime/provenance:

- [G.2 source audit](PHASE_G2_LEGACY_AUDIT.md): evidence_documents của I.3.
- [Phase I report](PHASE_I_DATA_CLEANING_REPORT.md): historical public_report path.
- [AI protocol](PHASE_I_ANNOTATION_PROTOCOL.md): runtime đọc prompt này; không
  có nghĩa pilot cũ vẫn được phép phát hành.
- [v3.1 spec](PHASE_I4_1_NORMALIZATION_SPEC.md) và
  [J readiness snapshot](DATASET_QUALITY_READINESS_REPORT.md): current detailed contracts.

<details>
<summary>Tra toàn bộ báo cáo gốc trong archive</summary>

- [Kết quả triển khai crawler — 09/11/2026](archive/CRAWLER_IMPLEMENTATION.md)
- [Patch crawler riêng sau Phase D](archive/CRAWLER_PATCH_REPORT.md)
- [Baseline thăm dò trên nhãn người đã duyệt](archive/DEVELOPMENT_BASELINE.md)
- [Bổ sung phim và cộng đồng — 10/11/2026](archive/FACEBOOK_DIVERSE_SOURCES_20261110.md)
- [Đợt bổ sung đa dạng nguồn — 10/11/2026](archive/FACEBOOK_DIVERSITY_BATCH_20261110.md)
- [Pilot bình luận nhóm phim — 10/11/2026](archive/FACEBOOK_GROUP_PILOT_20261110.md)
- [Cào bài nhiều bình luận và sửa mention group — 10/11/2026](archive/FACEBOOK_HIGH_ACTIVITY_20261110.md)
- [Phase 0 — audit local, 09/11/2026](archive/PHASE_0_DATA_AUDIT.md)
- [Phase B — Data foundation (hoàn tất 09/11/2026)](archive/PHASE_B_REPORT.md)
- [Phase C — Annotation foundation](archive/PHASE_C_REPORT.md)
- [Phase D — Baseline CLI, fixture-only](archive/PHASE_D_REPORT.md)
- [Phase E.1 — Kết quả BoW và kiểm tra độ ổn định](archive/PHASE_E1_REPORT.md)
- [Phase E.2 — Cross-domain Ranking Diagnostics](archive/PHASE_E2_REPORT.md)
- [Kết quả Phase E trên 346 nhãn người](archive/PHASE_E_REPORT.md)
- [Phase G.1 — Tách collection khỏi test sampling](archive/PHASE_G1_UPDATE.md)
- [Phase G.3.1 — Giant component and direct leakage audit](archive/PHASE_G3_1_REPORT.md)
- [Phase G.3.2 — Parent/thread verification and legacy diagnostics](archive/PHASE_G3_2_REPORT.md)
- [Phase G.3 — Unified human dataset and normalization ablation](archive/PHASE_G3_REPORT.md)
- [Phase G follow-up — exposure audit, text_view, new-post intake](archive/PHASE_G_FOLLOWUP.md)
- [Phase G — Master Dataset & Independent Blind Test Preparation](archive/PHASE_G_REPORT.md)
- [Phase H — PhoBERT-v2 and ViSoBERT development fine-tuning](archive/PHASE_H_REPORT.md)
- [Phase I.1 preprocessing and quality review](archive/PHASE_I1_PREPROCESSING_RULES.md)
- [Phase I.1 quality audit](archive/PHASE_I1_QUALITY_REPORT.md)
- [Phase I.2 raw-to-plain specification](archive/PHASE_I2_PREPROCESSING_SPEC.md)
- [Phase I.2 plain-text and quality review report](archive/PHASE_I2_REPORT.md)
- [Phase I.3 format recovery and source sampling specification](archive/PHASE_I3_PLAIN_TEXT_SPEC.md)
- [Phase I.3 recovery and sampling report](archive/PHASE_I3_REPORT.md)
- [Phase I.4.1 — Final Vietnamese Text Normalization Patch](archive/PHASE_I4_1_NORMALIZATION_REPORT.md)
- [Phase I.4 human quality validation protocol](archive/PHASE_I4_QUALITY_PROTOCOL.md)
- [Phase I.4 readiness and human quality review](archive/PHASE_I4_REPORT.md)
- [Phase A — Repo audit (07/11/2026)](archive/REPO_AUDIT_PHASE_A.md)
- [Audit dọn repository — 09/11/2026](archive/REPO_CLEANUP_AUDIT.md)

</details>

Không tự tạo report mới cho mỗi thay đổi. Cập nhật mục tương ứng trong ba
tài liệu chính; chỉ thêm tài liệu khi có trách nhiệm độc lập và cập nhật index.
