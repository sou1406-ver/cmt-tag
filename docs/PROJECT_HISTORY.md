# Lịch sử dự án

## 1. Thu thập và gán nhãn

Crawler chuyển sang Selenium, giữ journal/resume, post/comment identity và
provenance. Mention chỉ xóa khi DOM xác nhận; không thu thêm danh tính tác giả.
Hai task Facebook và một task legacy tạo 650 quyết định người, gồm 532 nhãn
sentiment trước lọc. Đây là nhãn một người cho development, không phải gold test độc lập.
Nguồn/phương pháp tạo nhãn `overall` legacy chưa xác minh nên không dùng làm ground truth.

## 2. Những mô hình đã thử

Grouped CV trên 346 nhãn Facebook: baseline LR masked Macro-F1 0,4828;
char TF-IDF + LinearSVC đạt 0,5802 ở split lịch sử. Năm seed grouped CV cho
0,5593 ± 0,0146; hai chiều movie transfer chỉ 0,0707/0,1397.
Các số này thuộc protocol cũ, không phải kết quả trên dataset filtered hay independent test.
Ranking diagnostic không chứng minh prior shift. Transformer mới là pilot, không có
kết luận hiệu năng cuối cùng. Checkpoint, fold, predictions và kết quả local giữ nguyên.

## 3. Những hướng đã bỏ khỏi workflow

Các chuỗi normalizer v3.1/v3.2, khôi phục token, alias, audit và workbook theo
phase gây nhiều trạng thái/entry point và rủi ro sửa sai biểu cảm/dấu câu.
Chúng được bỏ khỏi code hiện hành cùng runner thực nghiệm, script gán nhãn luật,
feature script độc lập và CLI wrappers. Không ghép các thuật toán khác nhau rồi
coi là code trùng: phần thực sự dùng lại được chuyển nguyên hàm vào owner hiện có.

## 4. Chiến lược dữ liệu hiện tại

Dùng canonical raw đã xác minh: 38.642 → **25.810 comment**, gồm 7.146 Facebook
và 18.664 legacy. Loại legacy raw có `_`, legacy >1.000 ký tự, dữ liệu không dùng
được, quyết định human EXCLUDE và exact duplicates. Block 1.200 câu cũ vẫn ở ngoài.
Facebook >1.000 ký tự giữ REVIEW. Không loại chỉ vì câu ngắn, emoji hay teencode;
không tự gán NEU cho câu kể chuyện. Có **425 nhãn sentiment**, **6.968 ứng viên chưa duyệt**.

Chỉ dùng tiền xử lý tối thiểu; không tiếp tục kế hoạch v3.2. Raw/human history
không đổi, near-duplicates không tự xóa, frozen test/split được bảo vệ. Candidate
chưa approved; không tự chuyển active pointer, tạo nhãn AI hoặc train lại.
Xem [báo cáo lọc](DATASET_FILTER_REPORT.md) cho số liệu và checksum gốc.

## 5. Cleanup và tái lập

Tag remote **before-cleanup-20261112** trỏ tới
`0c9e1a240f5661d1df25949ee33f1ff9ff1e4238`, chứa toàn bộ code/config/tài liệu cũ.
Để tái lập một thí nghiệm cũ, checkout **toàn bộ tag** trong working tree riêng
rồi dùng đúng môi trường và artifact local đã pin; không chép riêng một module
cũ vào pipeline mới. Không rewrite history và không xóa artifact local.

Các implementation còn dùng được gộp theo trách nhiệm:

- `minimal_filter_text`: master → `src/preprocessing/__init__.py`, public alias `preprocess`.
- `normal`, `protection`, `check_protection`: master/unified → `src/dataset/common.py`.
- `protection_set`, `duplicate_groups`: phase_i → `src/data/split.py`.
- `FILM`, `AD`, `verified_post`, `layers`: semantic_quality/quality_readiness → `src/data/quality.py`.
- `assert_intakes_allowed`: test_posts → `src/dataset/blind.py`, giữ cả registry/quarantine checks.
- Build/filter và prepared-data CLI dùng chung `scripts/build_master_dataset.py`.
- Train/evaluate giữ một implementation trong `src/models/core.py` (trước là baseline).

Các file lịch sử còn ở working tree có lý do cụ thể:

| File/nhóm | Bằng chứng phải giữ |
| --- | --- |
| `docs/guidelines/MOVIE_SENTIMENT_V2_0.md` | `src/annotation/guidelines.py:validate_guideline` kiểm task cũ bằng SHA `b094bcffc28f5099b6aa0278f95eaf4ee35cba1ee4f3965afa7009d26bd43844`; V2.1 giữ nguyên SHA `7d0a308a6c64f36308cd980b4e05b4b7fb7eb76b3d80d5f172b96f7c2619ee9a` |
| `requirements/locks/classical-windows-py312.txt` | Lock Windows/Python 3.12 cho kết quả CV cũ; không sửa pin |
| `requirements/transformer.txt`, `requirements/torch-cpu.txt` | Recipe dependency của checkpoint H được giữ: tag `before-cleanup-20261112:docs/archive/PHASE_H_REPORT.md` dòng 93–101 yêu cầu các root include trỏ tới hai file này; package pins/CPU index giữ nguyên, không dùng cho workflow hiện tại |
| `docs/figures/phase_e2/*.png` | Sáu figure ROC/PR/scores của kết quả E.2 đã khóa, không phải hướng dẫn chạy hiện tại |
| `docs/annotation_reviews/multifilm_20261110/*` | Audit/decision evidence của bộ nhãn người; `outputs/development/reviewed/manifest.json` pin `audit_report.json` |
| `data/**` và `outputs/README.md` | Snapshot data/task/provenance và chỉ mục đã tồn tại, giữ nguyên byte; hướng dẫn cũ ở đó chỉ thuộc snapshot, dùng tag để tái lập |
| `configs/phase_i.json` | `src/data/quality.py` đọc `exact_ui_strings`; filter đọc lineage/test reservation config đã pin |
| `configs/canonical_dataset.json` | Recipe canonical nguồn của bản lọc; manifest nguồn và raw SHA giữ nguyên |
| `configs/data_fixture.json`, `configs/data_legacy.json` | Fixture/regression của prepared-data contract trong `tests/test_data_foundation.py`; không tự dùng legacy overall làm gold |

Bằng chứng audit đầy đủ từng file/import/pin/blob backup nằm local tại
`outputs/repository_simplification_20261112/`. Không đưa comment hoặc dataset mới lên Git.

### Kiểm chứng sau dọn

Bộ lọc chạy lại trên đúng `rebuild_20261112` vào
`outputs/canonical/versions/cleanup_verify_20261112/`: **11/11 artifact content
hashes khớp**, gồm raw view, exclusions, groups/protection, human history và pool.
Reference manifest SHA vẫn là `602d98e0ee184c8c01f7bd89e2e129918341a367fcfcf862e7b9f56d3352d0f6`.
Manifest rebuild mới chỉ đổi `implementation_sha256` vì master đã được rút gọn;
không đổi output hash, source hash, approval hay pointer. 1.215 baseline artifact/data
files khớp; 9 hàm di chuyển có AST body giống nguyên bản. Checkpoint ban đầu có
một lần đọc không khớp guard; đọc lại khớp hash trong snapshot audit trước cleanup
và manifest, không sửa file hoặc bỏ qua guard. Lần rebuild thành công kiểm cả protected inputs.

Inventory: **341 → 133 tracked files**, **51 → 1 scripts**, sáu lệnh chính được
smoke test. Source 70 → 30 files; configs 30 → 5. Không thêm phase/framework/workbook.
Trước dọn: 405 tests (404 pass, 1 skip). Sau khi bỏ test của chức năng đã bỏ và
chuyển regression còn giá trị: **143 pass, 0 fail, 0 skip**. Riêng G.1 với
`python -S` (không site-packages/Selenium): 1 pass, 2 skip có lý do, không import error.
269 input trong lineage và 1.215 baseline files vẫn đúng checksum; import graph
97 edges và các link tài liệu chính hợp lệ. Raw comments mới không nằm trong commit.
