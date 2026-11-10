# Phân loại sắc thái bình luận phim tiếng Việt

Đặc tả chính thức: [CODEX_HANDOFF_MOVIE_SENTIMENT.md](CODEX_HANDOFF_MOVIE_SENTIMENT.md).
Đã triển khai **Phase A/B**, **Phase C tooling** và baseline thăm dò trên nhãn người. Phạm vi chỉ
là comment về phim với ba sentiment `POS / NEG / NEU`.
`REVIEW` và `EXCLUDE` là trạng thái, không phải lớp huấn luyện.

## Guideline và dữ liệu đang chuẩn bị

Dùng [guideline V2.1](docs/guidelines/MOVIE_SENTIMENT_V2_1.md) cho công việc mới;
[V2.0](docs/guidelines/MOVIE_SENTIMENT_V2_0.md) giữ nguyên cho các task cũ.
Nội dung 2.1: sự đồng cảm và trải nghiệm cảm xúc tích cực, đáng giá do
phim mang lại có thể là POS; cảm xúc đơn thuần chưa rõ thái độ vẫn là REVIEW.
Mã REVIEW của CLI gồm `REV_MIXED`, `REV_SARCASM`, `REV_TARGET`, `REV_CONTEXT`,
`REV_OTHER`; bất định cảm xúc/phủ định/media ghi chi tiết trong `reason`.

Hai file versioned bất biến, kiểm tra checksum cố định trong code. V2.0 được
khôi phục nguyên byte từ Git; V2.1 giữ nguyên byte của bản ở commit `13b5155`.
Không sửa nội dung dưới cùng phiên bản; task cũ giữ hash và nhãn, không tự đổi
thành đã gán theo guideline mới. Đợt duyệt mới ghi riêng hợp đồng V2.1.

Hai đợt 200 Mưa Đỏ và 200 đa phim được chuẩn bị thành **một bộ 400 dòng** ở
`outputs/development/`, nguồn XLSX giữ nguyên. Bản Excel làm việc là
`outputs/development/annotations.xlsx`: sheet `Duyet nhan` để duyệt đề xuất,
`400 binh luan` để tra nhãn đã chuẩn hóa, `Thong ke` để xem theo phim.
Nhãn cảm xúc đã xác nhận vẫn giữ POS. Sheet `400 binh luan` là snapshot lúc tạo
task; dữ liệu sau duyệt được xuất riêng ở `reviewed/`, không ghi đè workbook.

Trong `Duyet nhan`, điền cột E (`decision`) ở dòng 6–24: KEEP giữ nhãn,
CHANGE cần nhãn mới ở F và lý do ở H, DEFER cần lý do ở H và để ngoài train.
REVIEW cần mã ở G (kể cả KEEP nếu mã đang thiếu). Cột A là số dòng file gán gốc.
Không sửa các cột nguồn/đề xuất hoặc sheet snapshot. Lưu Excel rồi nhập:

```powershell
python scripts/import_development_review.py --annotator annotator_a --restore-trailing-spaces --allow-missing-change-reason
python scripts/development_baseline.py --dataset outputs/development/reviewed --output outputs/development/baseline_reviewed --run
```

Importer đọc Excel hoặc CSV, nối theo ID, yêu cầu đủ mọi quyết định và kiểm
tra nhãn/mã/lý do. Nhập thiếu sẽ không tạo output. Cùng file và người duyệt có
thể nhập lại an toàn; output có quyết định khác không bị ghi đè. `reviewed/`
giữ đủ 400 dòng, snapshot đầu vào, lịch sử trước/sau và manifest. DEFER giữ
nhãn/trạng thái gốc nhưng không vào train; không đồng nghĩa đã phân xử sentiment.
Baseline kiểm tra và phát lại bằng chứng duyệt trước khi fit, không chỉ đọc cờ.
Hai lệnh trên đã chạy với batch hiện tại. Người gán đã xác nhận cho phép nhập
11 CHANGE không có lý do; lịch sử ghi rõ thiếu lý do, không tự tạo giải thích.
Mặc định vẫn yêu cầu lý do. Flag phục hồi khoảng trắng chỉ chấp nhận dấu cách
ASCII cuối text và ghi log; nội dung gốc không đổi. source_round thiếu trong
workbook cũ được lấy từ ánh xạ ID khóa. Output/run đã có không bị ghi đè.

Chuẩn bị từ hai workbook local đã khóa checksum (không ghi đè output có sẵn):

```powershell
python scripts/prepare_development.py
python scripts/development_baseline.py
```

Bước thứ hai chỉ tạo kế hoạch, **không fit model**. Cấu hình
`configs/baseline_development.json` chuẩn bị TF-IDF + NB/LR/LinearSVC,
3-fold theo nhóm bài đăng và cụm trùng/gần trùng; hai biến thể dùng cùng fold.
`configs/entity_mask.json` liệt kê alias che tên phim/nhân vật, giữ văn bản gốc;
danh sách có giới hạn, tránh tự đoán tên người hoặc che các từ đơn mơ hồ.
Đã nhập **11 CHANGE + 8 KEEP**, không còn pending. Bản hiện tại ở
`outputs/development/reviewed/`: **110 POS / 144 NEG / 92 NEU**, ngoài train có
4 REVIEW và 50 EXCLUDE. Đã chạy sáu tổ hợp NB/LR/LinearSVC × original/masked
bằng 3-fold theo nhóm bài. Macro-F1 OOF cao nhất quan sát được là **0,4828**
(LR masked); model vẫn dự đoán NEG nhiều, recall POS/NEU còn yếu.
Đây là dữ liệu phát triển đã tiếp xúc và được chọn có chủ đích, chưa có gold
test độc lập. [Kết quả, confusion matrix và giới hạn](docs/DEVELOPMENT_BASELINE.md).

Phase 0 đã audit nguồn local 29k: [quyết định dùng fixture trước](docs/PHASE_0_DATA_AUDIT.md).
Phase C có workflow CLI blind annotation, agreement/Kappa, silver provider và
annotation release: [hướng dẫn Phase C](docs/PHASE_C_REPORT.md). Chưa có gold
hoặc Kappa người thật; nhãn `overall` chưa được xác minh, không được gọi là gold.

Repository phục vụ pipeline Python CLI: thu thập → tiền xử lý → gán nhãn
bán tự động → trích xuất đặc trưng → huấn luyện → đánh giá → báo cáo.
Không xây web, dashboard hoặc giao diện ứng dụng. Tooling C/D đã kiểm thử bằng
fixture và đã chạy CV thăm dò trên nhãn người; đánh giá gold độc lập vẫn chưa có.
Baseline CLI và kết quả fixture: [Phase D](docs/PHASE_D_REPORT.md).

## Phase E: thử tiền xử lý tiếng Việt và đặc trưng

Đã thử B0–B6 trên **đúng 346 nhãn và ba fold theo bài đã khóa**, LR/LinearSVC
với None/balanced, NB làm tham chiếu. So sánh raw word TF-IDF, chuẩn hóa nhẹ,
tách từ local, char_wb(3–5), word+char, teencode và mask; không thay nhãn/split.
Char TF-IDF + SVM balanced đạt **Macro-F1 0,5802**; cùng SVM word cũ là 0,4561.
Recall POS/NEU lên **0,4364 / 0,4239**. B6 chỉ thêm mask là 0,5729, chưa thấy
cải thiện. Đây vẫn là chọn mô hình trên CV phát triển, chưa có test độc lập.
[Toàn bộ bảng so sánh, confusion matrices và lỗi theo phim](docs/PHASE_E_REPORT.md).

```powershell
.\.venv-crawler\Scripts\python.exe -m venv .venv-phase-e
.\.venv-phase-e\Scripts\python.exe -m pip install -r requirements-phase-e-lock.txt
.\.venv-phase-e\Scripts\python.exe scripts/run_preprocessing_experiments.py
```

Run hiện tại ở `outputs/phase_e/`; đầu vào/fold khóa checksum, output không ghi
đè (dùng `--output` khác khi lặp). Môi trường tách từ riêng, pipeline cũ giữ
nguyên. Chưa cào thêm hoặc gọi AI gán nhãn; quyết định mở rộng nhãn sẽ dựa
trên phân tích lỗi và cần test độc lập sau đó.

## Phase E.1: BoW và độ ổn định grouped CV

Đã thêm CountVectorizer + MNB/ComplementNB, unigram và unigram+bigram.
So sánh 7 cấu hình trên fold cũ và 5 seed cố định, giữ nguyên mọi nhóm
post/comment ID/duplicate. Không thay nhãn, dữ liệu hoặc kết quả Phase E.

- Char-SVM: **Macro-F1 0,5593 ± 0,0146** qua 5 pooled OOF scores; mốc seed 42
  vẫn là 0,5802. Std không tính từ 15 fold độc lập.
- BoW tốt nhất: ComplementNB unigram **0,4887 ± 0,0157**, nhưng NEU còn yếu.
- Có 5 partition khác nhau, song các khối Mưa Đỏ không đổi sau căn chỉnh fold.
  90/110 POS thuộc Mưa Đỏ; chỉ có 20 POS ở các phim khác.
- Transfer char-SVM khác phim → Mưa Đỏ / ngược lại: **0,0707 / 0,1397**.
  Cả hai chỉ là diagnostic có giới hạn do Mưa Đỏ có 10 NEG và lệch nguồn/nhãn;
  không gọi là independent gold test, không dùng để chọn hyperparameter.

[Bảng kết quả, số lớp từng fold, bằng chứng lỗi và giới hạn](docs/PHASE_E1_REPORT.md).

```powershell
.\.venv-phase-e\Scripts\python.exe scripts/run_bow_robustness.py
```

Config `configs/bow_robustness.json`, dependencies dùng lockfile Phase E.
Artifact mới ở `outputs/phase_e1/`, từ chối ghi đè; dùng `--output` khác khi lặp.
Report xuất metrics/class/confusion matrix/timing, phân bố movie/post, từng
seed và transfer support. **174/174 test pass**; chưa thêm data, silver hoặc PhoBERT.

## Phase E.2: cross-domain ranking

Đã giữ nguyên hai transfer/char-SVM của E.1, xuất decision scores theo đúng
classes_, ROC-AUC OvR, AP/prevalence và ROC/PR/score distributions. Chiều khác
phim → Mưa Đỏ: AUC POS/NEG/NEU **0,580 / 0,707 / 0,610**; chiều ngược lại
**0,515 / 0,670 / 0,642**. Classification tái tạo đúng E.1; ranking còn tín
hiệu yếu–vừa nhưng chưa chứng minh chỉ cần đổi threshold hoặc có prior shift.
NEG Mưa Đỏ chỉ 10 câu; AP NEG chiều ngược 0,864 cần so prevalence 0,766.
[Kết quả, biểu đồ và giới hạn](docs/PHASE_E2_REPORT.md).

```powershell
.\.venv-phase-e\Scripts\python.exe -m pip install -r requirements-phase-e2.txt
.\.venv-phase-e\Scripts\python.exe scripts/run_ranking_diagnostics.py
```

Output mới `outputs/phase_e2/`, không ghi đè E/E.1. Không target calibration,
threshold tuning, AI labeling hoặc Transformer trong bước này.

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
seed 42: [hướng dẫn và file gán](data/tasks/source_quality_pilot_20261110/README.md).
Hiện một người gán dùng file A, nhãn đã chuẩn hóa giữ local; file B là template
dự phòng. Chưa có đánh giá đồng thuận nhiều người hoặc Kappa người thật.
Đợt gán chính mới có **200 câu / 25 chủ đề phim / 36 bài**, tách khỏi pilot:
[file gán và cách lấy mẫu](data/tasks/multifilm_annotation_200_20261110/README.md).
Gồm 120 mẫu ưu tiên có dấu hiệu phê bình và 80 mẫu ngẫu nhiên có phân tầng,
không ép tỷ lệ sentiment hoặc tự gán nhãn. Không dùng hai đợt làm gold test
độc lập; chưa tự gộp nhãn pilot vào train.
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
