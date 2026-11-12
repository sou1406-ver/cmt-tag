# Quá trình phát triển dự án

Dự án phân loại sentiment bình luận phim tiếng Việt thành POS/NEG/NEU.
Lịch sử dưới đây tổng hợp bằng chứng A–J; trạng thái cũ không thay thế trạng
thái hiện tại. **Hiện đang PENDING quality review**, chưa freeze corpus hoặc
phát hành pilot AI. Đọc [pipeline hiện tại](CURRENT_PIPELINE.md) để thao tác;
[kết quả thực nghiệm](EXPERIMENT_RESULTS.md) để hiểu các số đo.

## 1. Từ script legacy đến dữ liệu có provenance

| Giai đoạn / trạng thái hiện nay | Vấn đề và mục tiêu | Cách làm, code/config | Kết quả đã có và giới hạn |
| --- | --- | --- | --- |
| A — SUPERSEDED audit ban đầu | Script crawl chỉ có text; preprocessing cũ bỏ nhiều tín hiệu; chưa có test/config | Đọc nguồn, hash CSV, kiểm runtime; giữ raw và tách nhãn luật khỏi người. `crawl/`, `gan_nhan.py`, `trich_dac_trung.py` | 3.471 raw, 3.430 derived; cột người trống. Nhãn luật không phải gold. [Audit A](archive/REPO_AUDIT_PHASE_A.md) |
| Cleanup MMR — SUPERSEDED | Demo Manim/MMR không thuộc sentiment | Kiểm call sites rồi bỏ hai module MMR và Hello World; giữ crawler, ML helpers, dữ liệu | 39 tests và fixture trước/sau khớp; không xóa media local theo tên. [Quyết định](archive/REPO_CLEANUP_AUDIT.md) |
| B — HISTORICAL foundation, SHARED contracts | Thiếu schema, raw snapshots và split chống trùng | `src/data/`: CSV/JSON import, human/machine events riêng, exact/near + post union, seeded split, hash validation; `configs/data_legacy.json` | 3.471 representatives; pool 2.430/521/520, 15 near pairs; 0 gold. Thiếu post metadata nên không chứng minh độc lập bài. [B](archive/PHASE_B_REPORT.md) |
| 0 / C — HISTORICAL annotation contracts | File bạn cung cấp 29k không biết nguồn hay cách gán overall | Audit local; `src/annotation/` export blind, ID-based import, Kappa/adjudication, silver permission gate; guidelines V2.0/V2.1 bất biến | 29.688 legacy, không có post/movie provenance. Xây workflow trên fixture, không biến overall thành gold hay tự tính Kappa người thật. [Nguồn](archive/PHASE_0_DATA_AUDIT.md), [C](archive/PHASE_C_REPORT.md) |
| D — EXPERIMENTAL fixture validation | Cần chứng minh vectorizer train-only và model/evaluation CLI hoạt động | `src/baseline/core.py`, release/usage guards, BoW/TF-IDF × NB/LR/SVM | Fixture 126/42/42 cho F1=1,0; chỉ kiểm phần mềm, không phải hiệu năng nghiên cứu. [D](archive/PHASE_D_REPORT.md) |

## 2. Crawler, nguồn dữ liệu và nhãn người

Crawler ban đầu dùng Playwright; triển khai hiện tại là Selenium trong
`src/crawler/`. Interactive, Store, run_posts, journal/checkpoint/resume được
tái dùng; không tạo crawler riêng cho mỗi batch. Parser DOM bỏ account mention
nhận dạng được, gồm group-user links đã xác minh; tên text thường không bị
đoán cắt bằng chữ hoa. Không thêm author_name/author_id. Emoji được giữ hoặc
khôi phục từ alias có evidence, không được chuyển thành sentiment mặc định.

Các sửa đổi quan trọng: post scope/layout, accountLink group pattern, Counter
thay quét toàn journal, checkpoint theo lô nhưng raw vẫn fsync, finish partial
giữ resumable. `success/visible_dom_exhausted` không chứng minh lấy hết Facebook.
[Guide hiện hành](CRAWLER.md); [triển khai gốc](archive/CRAWLER_IMPLEMENTATION.md),
[durability/resume patch](archive/CRAWLER_PATCH_REPORT.md).

Các đợt group giúp đa dạng hơn fanpage, nhưng là convenience sampling: pilot
504 dòng từ 7 bài, bulk 2.277 text mới chủ yếu hai bài Mai, sau đó 143 dòng
đa nguồn và 252 dòng từ 9 bài/8 phim. Không cộng các export/raw/preview thành
những observations độc lập; master G đối chiếu identity và lineage.
[Group pilot](archive/FACEBOOK_GROUP_PILOT_20261110.md),
[bulk](archive/FACEBOOK_HIGH_ACTIVITY_20261110.md),
[đa nguồn](archive/FACEBOOK_DIVERSE_SOURCES_20261110.md),
[batch diversity](archive/FACEBOOK_DIVERSITY_BATCH_20261110.md).

400 quyết định Facebook gồm pilot Mưa Đỏ và tập đa phim được một người gán,
không phải hai annotator độc lập. Sau duyệt 19 quyết định (11 CHANGE/8 KEEP),
có **346 sentiment = 110 POS / 144 NEG / 92 NEU**, 4 REVIEW, 50 EXCLUDE.
Lý do thiếu được ghi đúng là thiếu theo phê duyệt, không bịa giải thích.
V2.1 công nhận trải nghiệm cảm xúc tích cực/đồng cảm có thể là POS; cảm xúc
đơn thuần chưa rõ thái độ vẫn có thể REVIEW. Nhãn development không là gold
test độc lập. [Baseline và lịch sử duyệt](archive/DEVELOPMENT_BASELINE.md).

## 3. Từ baseline đến audit độ tổng quát

| Giai đoạn / trạng thái | Khác biệt so với trước | Implementation / config | Kết quả và giới hạn |
| --- | --- | --- | --- |
| Development baseline — EXPERIMENTAL | Train trên 346 nhãn người đã chốt, grouped CV thay vì fixture | `scripts/development_baseline.py`, `configs/baseline_development.json`, entity_mask.json | LR masked Macro-F1 0,4828. Ba fold theo bài; chỉ development. [Báo cáo](archive/DEVELOPMENT_BASELINE.md) |
| E — EXPERIMENTAL | Phân biệt tác động feature/preprocessing thay vì chỉ đổ lỗi thiếu data | `src/preprocessing/vietnamese.py`, `src/baseline/preprocessing_experiments.py`, preprocessing_experiments.json | Char-SVM B3 0,5802; segmentation SVM 0,4844; B6 mask 0,5729. Không mọi chuẩn hóa đều tốt. [E](archive/PHASE_E_REPORT.md) |
| E.1 — EXPERIMENTAL | Bổ sung BoW và kiểm độ nhạy split | bow_robustness.py, bow_robustness.json; 5 seed × 3 grouped folds | Char-SVM 0,5593 ± 0,0146 trên 5 OOF scores; transfer chỉ 0,0707/0,1397. 90/110 POS ở Mưa Đỏ; các khối Mưa Đỏ không đổi fold qua seed. [E.1](archive/PHASE_E1_REPORT.md) |
| E.2 — EXPERIMENTAL diagnostic | Kiểm ranking thay vì chỉ argmax | `scripts/run_ranking_diagnostics.py`, ranking_diagnostics.json, dùng estimator E.1 và ánh xạ score/class order | Ranking có tín hiệu yếu/không đồng đều, không đủ chứng minh prior shift hay sửa threshold bằng nhãn target. [E.2](archive/PHASE_E2_REPORT.md) |

Không lựa chọn lại split/nhãn để nâng điểm. Các số CV, transfer và pilot một
fold không được xếp chung thành leaderboard. Chi tiết lớp/support ở
[bảng kết quả tổng hợp](EXPERIMENT_RESULTS.md).

## 4. Master, leakage và mở rộng human development

| Giai đoạn / trạng thái | Vấn đề / cách xử lý | Kết quả thực và ràng buộc |
| --- | --- | --- |
| G — ACTIVE master, PENDING independent test | `master.py`, `blind.py`, master_dataset.json/blind_test.json: nối identity có bằng chứng, giữ variants, exposure ledger, test quota | 60.627 observations → **39.842 master records**: 10.154 Facebook/archives + 29.688 legacy. Không phải 39.842 Facebook identities. Test lúc chuẩn bị **0/180**, thiếu attestation. [G](archive/PHASE_G_REPORT.md) |
| G follow-up/G.1 — ACTIVE guard contracts | `exposure.py`, `test_posts.py`: rà 8 post, intake preflight, đổi blind header sang text_view; tách crawl count cap khỏi quota test | Cả 8 chưa chứng minh unused; draft 25/25 blocked. Thu thập có thể `all` nhưng vẫn timeout/round/resume; test vẫn 10/bài,20/phim; quarantine toàn bài. MoMo không nhập test Facebook. [Follow-up](archive/PHASE_G_FOLLOWUP.md), [G.1](archive/PHASE_G1_UPDATE.md) |
| G.2 — HISTORICAL import, ACTIVE provenance caveat | `legacy_audit.py`, legacy_audit.json: chọn 250 để người gán, không dùng overall | 186 sentiment = 79/77/30, 64 EXCLUDE không lý do theo phép người dùng; đủ history/receipt. Tổng **650 decisions / 532 sentiment**. Legacy vẫn thiếu nguồn/bài, không là test. [G.2](PHASE_G2_LEGACY_AUDIT.md) |
| G.3 — SUPERSEDED strict-gate result, preserved | `unified.py`, normalization_ablation.py: thống nhất 532 human rows, basic_v1; giữ fold E | Giant component 10.275 records nối 222/346 supervised FB rows khiến full-component gate chặn A/B/C/D. Không coi bridge gián tiếp là direct duplicate. [G.3](archive/PHASE_G3_REPORT.md) |
| G.3.1 — EXPERIMENTAL narrower protocol | component_audit.py, direct_leakage_ablation.py: giữ graph G; direct identity/exact/near isolation riêng | Zero measurable direct fold overlap; A/B/C/D chạy cùng frozen FB folds. Legacy thêm vào train làm F1 FB giảm; provenance legacy vẫn không chứng minh independent. [G.3.1](archive/PHASE_G3_1_REPORT.md) |
| G.3.2 — ACTIVE verification for historical experiments | parent_thread_audit.py xác minh source row, không suy parent từ field thiếu; legacy_error_analysis.py đọc OOF | 346/346 source rows khớp, 113 reply có parent; zero direct/thread fold crossings. Sửa cách diễn giải zero-parent cũ; không sửa data/split. [G.3.2](archive/PHASE_G3_2_REPORT.md) |
| H — EXPERIMENTAL / PARTIAL | `src/transformer/`, configs/phase_h/: PhoBERT dùng RDR segmentation, ViSoBERT verbatim, checkpoint mới mỗi fold | ViSoBERT smoke + fold-0 pilot 0,3895 FB / 0,5191 FB+legacy. Chưa full CV; PhoBERT chưa chạy do Java/RDR. Không gọi pilot là thắng SVM. [H](archive/PHASE_H_REPORT.md) |

## 5. Các phiên bản plain text và human quality gates

| Giai đoạn / trạng thái hiện nay | Bổ sung so với trước / code | Kết quả quan sát, không phải quality accuracy |
| --- | --- | --- |
| I — SUPERSEDED pilot readiness | phase_i.py: raw-preserving cleaning, unify human ledger, exact/direct-near pool | 650 decisions/532 sentiment giữ nguyên. Preview 500 với 250/250 nguồn; báo cáo cũ ghi READY nhưng bị I.1 pause. Không có AI predictions thật. [I](PHASE_I_DATA_CLEANING_REPORT.md) |
| I.1 — SUPERSEDED quality preview | phase_i1.py, repetition.py, semantic_quality.py: structural repetition, domain proposals, alias review | 20.014 KEEP/19.828 REVIEW, 0 auto EXCLUDE; 14.355 pool, preview 493 legacy/7 FB. Tất cả quality chưa người duyệt. [Audit](archive/PHASE_I1_QUALITY_REPORT.md), [rules](archive/PHASE_I1_PREPROCESSING_RULES.md) |
| I.2 — HISTORICAL engine, component retained | plain_text.py: protected regions, reviewed compounds/alias; rebuild from raw | 7.015 rows đổi, 15.481 compound replacements, 753 emoji restorations; còn 38.833 unresolved occurrences. 200-row workbook, không truncate. [I.2](archive/PHASE_I2_REPORT.md), [spec](archive/PHASE_I2_PREPROCESSING_SPEC.md) |
| I.3 — HISTORICAL engine, ACTIVE input contract | plain_text_v3.py + phase_i3.py: name masks, shape gates, offline exact segmentation roundtrip; tighten missing FB identity | 26.561 old occurrences restored; còn 12.264. 2.814 accepted token types; candidate FB101 chỉ từ3 bài. 200 format decisions vẫn pending. Không chứng minh tokenizer gốc. [I.3](archive/PHASE_I3_REPORT.md), [spec](archive/PHASE_I3_PLAIN_TEXT_SPEC.md) |
| I.4 — SUPERSEDED semantic presentation, ACTIVE reservation | phase_i4.py: tách technical/format/domain/spam, same-text checksum gates; 200 semantic review +40 reserved | Chưa có human judgments/metrics. Metadata bài không đủ chứng minh comment domain. [I.4](archive/PHASE_I4_REPORT.md), [protocol](archive/PHASE_I4_QUALITY_PROTOCOL.md) |
| I.4.1 — ACTIVE candidate / PENDING normalization approval | final_normalization.py, abbreviations_v3_1.json: bounded/split entity repair, contextual abbreviation/underscore recovery, protected punctuation | **plain_text_v3_1**, 13.804 rows khác I.3, thêm596 old underscore occurrences; vẫn giữ raw/human/annotation pointer. 150 review rows +10 controls, chưa approval. [Report](archive/PHASE_I4_1_NORMALIZATION_REPORT.md), [spec](PHASE_I4_1_NORMALIZATION_SPEC.md) |
| J — ACTIVE / PENDING review and freeze | quality_readiness.py, quality_review.py, quality_release.py, phase_j_v1.json: three quality layers, same200-ID semantic migration, exact40 holdout export/import | **9.788 proposed / 0 approved**, FB24 từ3 bài. Format200/normalization150/domain200 còn trống ở snapshot J. No real precision/recall; pilot0, freeze pending. [Readiness](DATASET_QUALITY_READINESS_REPORT.md), [handoff](QUALITY_REVIEW_HANDOFF.md) |

I.4.1 là candidate chính, không đồng nghĩa `text_annotation` đã được đổi sang
v3.1: pointer vẫn ở I.3 đến khi có approval đúng version/hash. J giữ riêng
domain và spam, không biến OFF_TOPIC thành NEU hoặc heuristic thành nhãn người.
40 quality-holdout IDs không phải independent sentiment test; metadata không
đủ chứng minh độc lập bài. Dừng ở đây để người dùng điền review, không kéo dài
preprocessing chỉ nhằm tăng KEEP.

## 6. Structural consolidation hiện tại

Không có experiment mới. Chuẩn hóa cách tìm code và kiến thức: ba tài liệu này,
một guide môi trường, shared XLSX/ID integrity, version-dispatch facade và một
quality CLI. Các script/requirement cũ là compatibility aliases; engines/configs
được checksum pin vẫn ở nguyên path/byte. Archive chỉ giữ báo cáo gốc để đào sâu.
Không dùng số file giảm làm thước đo nghiên cứu. Các thay đổi sau cập nhật đúng
mục trong tài liệu này; không mặc định tạo thêm phase report/module mới.
