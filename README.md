# Phân loại sắc thái bình luận phim tiếng Việt

Đặc tả chính thức: [CODEX_HANDOFF_MOVIE_SENTIMENT.md](CODEX_HANDOFF_MOVIE_SENTIMENT.md).
Đã triển khai **Phase A/B**, **Phase C tooling** và **Phase D baseline trên fixture**. Phạm vi chỉ
là comment về phim với ba sentiment `POS / NEG / NEU`.
`REVIEW` và `EXCLUDE` là trạng thái, không phải lớp huấn luyện.

Phase 0 đã audit nguồn local 29k: [quyết định dùng fixture trước](docs/PHASE_0_DATA_AUDIT.md).
Phase C có workflow CLI blind annotation, agreement/Kappa, silver provider và
annotation release: [hướng dẫn Phase C](docs/PHASE_C_REPORT.md). Chưa có gold
hoặc Kappa người thật; nhãn `overall` chưa được xác minh, không được gọi là gold.

Repository phục vụ pipeline Python CLI: thu thập → tiền xử lý → gán nhãn
bán tự động → trích xuất đặc trưng → huấn luyện → đánh giá → báo cáo.
Không xây web, dashboard hoặc giao diện ứng dụng. Tooling C/D đã kiểm thử bằng fixture;
các bước huấn luyện/đánh giá/báo cáo trên dữ liệu thật chưa có gold để chạy.
Baseline CLI và kết quả fixture: [Phase D](docs/PHASE_D_REPORT.md).

## Thu thập Facebook mới (Python CLI)

Dán nhiều link trong cùng run, dùng Brave:
`python -m src.crawler interactive --channel brave`. Nhập mã phim một lần;
dán link từng dòng, `movie <mã mới>` để đổi phim, Enter rỗng để kết thúc.

Crawler dùng Selenium: [hướng dẫn cài đặt, crawl, resume, validate và export](docs/CRAWLER.md).
Chạy `python -m src.crawler --help`. Dùng URL bài do người dùng cung cấp,
trình duyệt có giao diện để tự đăng nhập; không tự tìm phim hoặc đăng nhập mật khẩu.
Raw JSONL theo run độc lập, không ghép dữ liệu/nhãn legacy. Chỉ export các
observation đầy đủ vào CSV cùng `import_config.json` để chạy Phase B.

### Bình luận đã thu thập và chia sẻ

| Bài nguồn | Số comment/phản hồi | CSV | Excel |
|---|---:|---|---|
| Bài trang phim | 1.538 | [CSV](data/imports/facebook_fresh/comments.csv) | [Excel](data/imports/facebook_fresh/comments.xlsx) |
| Bài nhóm `1909400102999925` | 117 | [CSV](data/imports/facebook_group_1909400102999925/comments.csv) | [Excel](data/imports/facebook_group_1909400102999925/comments.xlsx) |
| Pilot 7 bài nhóm, 5 phim — 10/11/2026 | 504 | [CSV](data/imports/facebook_group_pilot_20261110/comments.csv) | [Excel](data/imports/facebook_group_pilot_20261110/comments.xlsx) |
| Bài nhiều bình luận, sau sửa mention — ID mới | 2.277 | [CSV](data/imports/facebook_high_activity_20261110/comments.csv) | [Excel](data/imports/facebook_high_activity_20261110/comments.xlsx) |
| Bổ sung 3 phim, 2 nhóm công khai — ID mới | 143 | [CSV](data/imports/facebook_diverse_sources_20261110/comments.csv) | [Excel](data/imports/facebook_diverse_sources_20261110/comments.xlsx) |
| Đợt đa dạng: 9 bài, 8 phim, 3 nhóm — ID mới | 252 | [CSV](data/imports/facebook_diversity_batch_20261110/comments.csv) | [Excel](data/imports/facebook_diversity_batch_20261110/comments.xlsx) |

Mỗi bản thuộc một run riêng, kèm nguồn, mã phim theo đầu vào và ID.
Hai bản đầu là `mua_do`; bản pilot có 5 phim và thêm cột `source_group`.
Chi tiết nguồn, số lượng và giới hạn của đợt mới: [pilot nhóm phim](docs/FACEBOOK_GROUP_PILOT_20261110.md).
Pilot gán nhãn người đã chuẩn bị **70 fanpage + 130 group**, cùng phim Mưa Đỏ,
seed 42, hai file độc lập chưa có nhãn: [hướng dẫn và file gán](data/tasks/source_quality_pilot_20261110/README.md).
Chưa có kết quả người gán, agreement/Kappa hoặc tỷ lệ usable thật.
Đợt bulk mới là hai bài Mai trong nhóm khoảng 1,6 triệu thành viên, không trùng
ID ba bản trước: [nguồn, sửa lỗi href và đối soát](docs/FACEBOOK_HIGH_ACTIVITY_20261110.md).
Đợt tiếp thêm Interstellar, The Dark Knight và Nhà Bà Nữ, có nhóm Chê Phim Review
256,7K thành viên: [nguồn và giới hạn truy cập](docs/FACEBOOK_DIVERSE_SOURCES_20261110.md).
Đợt đa dạng tiếp theo xác minh 12 bài, kiểm mẫu trước khi crawl sâu 9 bài;
chưa đạt mục tiêu 20–30 bài. Có [danh sách nguồn, thời gian và báo cáo chất lượng sơ bộ](docs/FACEBOOK_DIVERSITY_BATCH_20261110.md).
Cột `text` bỏ tag tài khoản được nhận dạng từ node DOM, giữ emoji Unicode,
phủ định và xuống dòng. Dữ liệu chưa gán nhãn; các run còn `partial`, chưa xác
nhận đủ toàn bộ bình luận. `export_manifest.json` trong từng thư mục ghi nguồn,
cách xử lý, số lượng và checksum. Raw và profile trình duyệt vẫn giữ local.

Import từ thư mục gốc repo:

```powershell
python scripts/prepare_data.py --config data/imports/facebook_fresh/import_config.json
python scripts/prepare_data.py --config data/imports/facebook_group_1909400102999925/import_config.json
python scripts/prepare_data.py --config data/imports/facebook_group_pilot_20261110/import_config.json
python scripts/prepare_data.py --config data/imports/facebook_high_activity_20261110/import_config.json
python scripts/prepare_data.py --config data/imports/facebook_diverse_sources_20261110/import_config.json
python scripts/prepare_data.py --config data/imports/facebook_diversity_batch_20261110/import_config.json
```

## Setup và test

Phase B chỉ cần **Python 3.10+**, dùng standard library. Không cần cài package
trong `requirements-data.txt`. Không sửa virtualenv cũ trong `.venv`.

Chạy tại thư mục gốc:

```powershell
python -m unittest discover -s tests -v
python scripts/prepare_data.py --config configs/data_fixture.json --output-root outputs/fixture_data
```

Máy hiện tại chưa có Python trên PATH chạy được. Có thể dùng Python bundled
đã kiểm tra (đổi đường dẫn nếu máy khác):

```powershell
$pythonExe = 'C:\Users\phuc1\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $pythonExe -m unittest discover -s tests -v
& $pythonExe scripts/prepare_data.py --config configs/data_legacy.json
```

Test tích hợp của `gan_nhan.py` dùng pandas nếu có, nếu thiếu sẽ ghi rõ skipped;
các test nền tảng dữ liệu không cần pandas. Các script sentiment cũ có
dependency riêng: `gan_nhan.py` và `crawl/tien_xu_ly.py` dùng pandas;
`trich_dac_trung.py` dùng numpy, pandas, scipy và scikit-learn. Gensim chỉ
cần cho helper Word2Vec/KeyedVectors, pyvi khi chọn tách từ. Đây không phải
dependency Phase B; môi trường audit hiện thiếu scipy/scikit-learn/gensim/pyvi.

## Dữ liệu và chạy pipeline

Kiểm kê lịch sử Phase A/B: `crawl/dataset.csv` có **3.471 dòng raw**;
hai file derived có **3.430 dòng**. Toàn bộ `nhan_nguoi` trống. Không có file
29k hoặc metadata bài/comment được xác nhận ở thời điểm đó. Những CSV này
không có trong bản clone hiện tại. CSV legacy được giữ local và gitignore;
bản Facebook sạch được chia sẻ riêng như mục trên.
Clone repo mới vẫn chạy được fixture CSV/JSON trong `tests/fixtures`.

Ngày 09/11/2026 đã thấy nguồn local `../data_module1.csv` có 29.688 dòng,
cột `id,comment,overall`, nhãn `pos/neg/neu`. Chưa nhập nguồn này vào pipeline,
chưa xác minh provenance hoặc coi nhãn có sẵn là gold. Config legacy chỉ dùng
khi các file local được tham chiếu đã có đầy đủ.

Với dữ liệu local hiện có:

```powershell
python scripts/prepare_data.py --config configs/data_legacy.json
```

Lệnh in `data_version`, số lượng, warnings, đường dẫn report và manifest.
Sau đó xác minh phiên bản vừa tạo:

```powershell
python scripts/validate_data.py --data-root data --version <data_version>
```

Lệnh dưới đây **phải thất bại** với dữ liệu hiện tại, vì chưa có gold:

```powershell
python scripts/validate_data.py --data-root data --version <data_version> --require-gold
```

Mỗi phiên bản gồm:

```text
data/raw/<input_sha256>/<original_name>      snapshot byte nguyên vẹn
data/processed/<version>/records.jsonl       tất cả dòng + metadata + provenance
data/processed/<version>/quality_decisions.jsonl
data/processed/<version>/near_duplicates.jsonl
data/processed/<version>/config.json
data/processed/<version>/report.json
data/processed/<version>/run.json
data/splits/<version>/manifest.json
data/splits/<version>/{train,dev,test}_blind.jsonl
```

Không ghi đè dữ liệu gốc hoặc phiên bản đã có. Cùng input/config/code/runtime
sẽ có cùng version, IDs, processed records và split. Chạy lại đúng phiên bản
đã có trả lỗi để bảo vệ artifacts; có thể đọc/validate phiên bản hiện tại hoặc
chọn `--output-root` mới khi cần chạy lại kiểm chứng. `run.json` ghi thời điểm
hoàn tất; report lưu checksum input/code/config/output và Python runtime.
Một thư mục chưa có `run.json` status complete là run chưa hoàn tất, không sử dụng.

## Cấu hình nguồn mới

Dựa theo `configs/data_fixture.json` cho CSV và JSON array of objects, UTF-8
(có hoặc không BOM). Mỗi nguồn khai báo rõ `source_dataset`, `path`, `format`,
và `columns` map tên chuẩn → cột đầu vào. Không tự dò cột.

```json
{
  "path": "data_local/comments.json",
  "format": "json",
  "source_dataset": "source_batch_01",
  "post_namespace": "facebook",
  "columns": {
    "text_raw": "message",
    "comment_id": "id",
    "post_id": "post",
    "post_url": "url",
    "collected_at": "collection_time"
  },
  "license": null,
  "privacy": null
}
```

Nguồn cùng nền tảng dùng cùng `post_namespace` để nối các post/comment ID;
không mặc định numeric ID của hai nền tảng là cùng bài. Metadata thiếu là
`null`. ID nội bộ là hash định danh nguồn + comment ID nếu có, nếu thiếu dùng
hash raw + occurrence của bản trùng; không giả mạo ID ngoài hay thời gian thu thập.
Tách nguồn theo batch khi cần; không nhập raw và derived thành hai corpus độc lập.

Config local dùng file gán nhãn cũ làm **annotation sidecar**, join theo hash
`text_raw` chính xác, không theo thứ tự dòng hay `clean`. `report.json` báo
dòng match/unmatched. Nhãn `positive/negative/neutral` map sang đề xuất máy
`POS/NEG/NEU`, `hard` sang REVIEW, `unrelated` sang đề xuất EXCLUDE.
`model_version=unknown_legacy_run` ghi rõ không biết phiên bản chạy cũ;
`do_tin` chỉ là heuristic, không phải xác suất. Nhãn máy EXCLUDE chưa được
con người xác nhận **không tự loại comment**.

## Bảo toàn dữ liệu và chống leakage

- Giữ `text_raw`; processed chỉ NFC + chuẩn hóa khoảng trắng. Giữ emoji,
  dấu câu, chữ số, teencode, phủ định và cả nội dung ngoài phim trong comment.
- Quality loại rỗng, UI exact match, suffix UI có dấu ellipsis; spam chỉ theo
  regex cấu hình rõ ràng (mặc định rỗng). Không lọc theo độ dài hay chính tả.
- Exact dedup theo NFC/whitespace/casefold. Mỗi dòng vẫn nằm trong records,
  bản trùng có `duplicate_of` và không trở thành mẫu độc lập.
- Near duplicate: token 3-gram Jaccard ≥ 0.9, từ 40 ký tự (cấu hình được).
  Giữ cả hai dòng, xuất cặp + score `pending_review`, gom cùng nhóm split.
  Đây là heuristic bảo thủ, không phát hiện hết paraphrase và không tự xóa.
- Union các post ID/URL, comment ID, exact duplicate và near candidate;
  nối cả nhóm bắc cầu trước khi split. Seed 42; cố gắng gần tỷ lệ yêu cầu,
  giữ nguyên nhóm kể cả khi một tập rỗng hoặc phân phối lệch.
- Pool ban đầu không dùng nhãn máy/người để cân bằng; phân phối thật được
  báo riêng sau lọc. Sau annotation cần kiểm tra lại đại diện ba lớp.
- Thiếu post metadata ở dữ liệu thật: chỉ kiểm tra trùng text/nhóm phát hiện,
  **không chứng minh được độc lập bài viết hoặc phim/nguồn chưa từng thấy**.
- Manifest B là **annotation pool reservation**, `locked_gold=false`.
  Bản `*_blind.jsonl` không có nhãn hay dự đoán/score. Dùng chúng cho người
  gán dev/test; không mở đề xuất máy để quyết định đáp án holdout.
- Lịch sử `annotations.human` và `annotations.machine` tách biệt, append-only.
  Nhãn người cũ chưa có người xác nhận/timestamp/guideline vẫn chưa là gold.
  Dev/test gold phải có xác nhận `evidence_mode=blind`, không dùng nhãn máy.
  Nhãn người xung đột trên exact duplicates cần phân xử trước khi dùng gold.

Chi tiết field và validation: [docs/DATA_SCHEMA.md](docs/DATA_SCHEMA.md).

## Scripts cũ và các phase tiếp theo

`gan_nhan.py` được giữ thuật toán cũ để đối chiếu, chỉ vá bảo toàn nhãn người,
metadata và từ chối ghi đè file. Không dùng nhãn luật làm gold hoặc ép cân bằng.
`trich_dac_trung.py` giữ các helper nhưng CLI giờ yêu cầu `records.jsonl`,
`--split-manifest` và `--near-duplicates`, xác minh nhóm rồi chỉ fit train pool.
Chưa chạy numerical feature extraction vì môi trường thiếu sklearn/scipy.
Không dùng `X_*.npz` cũ đã fit toàn corpus cho thực nghiệm. Phase D sẽ nối
gold labels, train-only vectorization, transform dev/test và test vocabulary.

Annotation sampling và train/evaluate đã có CLI ở `src.annotation`/`src.baseline`;
chưa triển khai active learning, pseudo-labeling hay Transformer. Các trường provenance/pseudo trong schema
chỉ là ràng buộc dữ liệu, không phải một thuật toán pseudo đã được kiểm định.
Tiếp theo: xác minh nguồn dữ liệu thật, chạy pilot người gán độc lập và xây gold
dev/test; chỉ sau đó dùng baseline cho kết luận nghiên cứu. Chưa có metric sentiment
trên dữ liệu thật được công bố; Kappa/gold thật vẫn cần người gán.

Theo yêu cầu thu thập lại corpus, crawler Python mới được triển khai riêng;
không sửa thuật toán Phase B. `crawl/crawl.js` là công cụ thu thập legacy
chạy trong trình duyệt, được giữ để đối chiếu; không phải ứng dụng web của dự án.
Demo MMR độc lập và script Hello World đã được loại bỏ sau khi audit tham chiếu;
chi tiết: [báo cáo dọn repository](docs/REPO_CLEANUP_AUDIT.md).
Chỉ code/config/docs/fixture được đưa lên Git; không đưa
CSV comment thật, snapshot, annotation thật, model, media hoặc virtualenv.

Audit và báo cáo phase: [Phase A](docs/REPO_AUDIT_PHASE_A.md),
[Phase B](docs/PHASE_B_REPORT.md).
