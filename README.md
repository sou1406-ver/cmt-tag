# Phân loại sắc thái bình luận phim tiếng Việt

Bài tập lớn Xử lý dữ liệu văn bản: xây dựng pipeline Python CLI để phân loại
bình luận phim thành **tích cực (POS)**, **tiêu cực (NEG)** và **trung lập (NEU)**.

**Thu thập dữ liệu → Lọc và tiền xử lý → Kiểm tra chất lượng → Gán nhãn → Huấn luyện → Đánh giá**

## Quy trình thực hiện

1. **Thu thập dữ liệu:** crawl bình luận Facebook từ các bài thảo luận/review phim bằng Selenium, kết hợp bộ CSV khoảng 29.000 dòng được cung cấp. Bình luận Facebook được lưu cùng mã phim, mã bài đăng, mã bình luận và thông tin nguồn.
2. **Lọc và tiền xử lý:** loại dữ liệu không sử dụng được và bình luận trùng hoàn toàn; chuẩn hóa Unicode NFC, HTML entities hợp lệ và một số khoảng trắng kỹ thuật. Giữ riêng văn bản gốc, bảo toàn emoji, emoticon, dấu câu, phủ định và teencode.
3. **Kiểm tra chất lượng:** kiểm tra nội dung, nguồn, trùng lặp và nguy cơ dữ liệu cùng bài hoặc gần trùng xuất hiện ở cả train và test. Những trường hợp chưa rõ tiếp tục chờ người duyệt.
4. **Gán nhãn:** người gán quyết định POS/NEG/NEU theo guideline V2.1. REVIEW dành cho câu chưa đủ căn cứ; EXCLUDE dành cho câu ngoài phạm vi hoặc không sử dụng được. Lịch sử quyết định được giữ lại.
5. **Huấn luyện:** biểu diễn văn bản bằng BoW hoặc TF-IDF, thử Naive Bayes, Logistic Regression và Linear SVM. Vectorizer chỉ được fit trên phần train.
6. **Đánh giá:** báo cáo Macro-F1, Accuracy, Precision/Recall/F1 từng lớp và confusion matrix. Chia dữ liệu theo nhóm bài đăng, kiểm tra trùng lặp và phân biệt kết quả phát triển với test độc lập.

Nguồn gốc ban đầu và cách tạo nhãn `overall` của bộ CSV được cung cấp chưa được
xác minh. Nhãn này **không được dùng làm ground truth**.

## Dữ liệu hiện tại

| Hạng mục | Số lượng |
| --- | ---: |
| Bình luận sau lọc | **25.810** |
| Facebook | 7.146 |
| Bộ dữ liệu được cung cấp | 18.664 |
| Bình luận còn nhãn sentiment người | **425** |
| Ứng viên gán nhãn chưa duyệt | **6.968** |

Dữ liệu local nằm tại `outputs/canonical/versions/filtered_20261112_final/`:

- `comments.csv`: dữ liệu sau lọc; `text_raw` và `text_minimal` là hai cột riêng.
- `exclusions.csv`: ID bị loại và lý do.
- `annotation_candidates.local.csv`: danh sách ứng viên gán nhãn, chưa phải bộ nhãn đã duyệt.
- `manifest.json`: checksum các artifact; lịch sử nhãn và thông tin chống leakage nằm cùng thư mục.

Chính sách lọc: loại bình luận legacy có `_` trong raw hoặc dài **trên 1.000 ký tự**;
Facebook trên 1.000 ký tự được giữ để review. Không loại chỉ vì câu ngắn, có emoji
hay teencode. Near-duplicates được đánh dấu/bảo vệ, không tự xóa ý kiến độc lập.

**Dataset này đang chờ duyệt chất lượng, chưa được dùng để train lại.** 425 nhãn
người là dữ liệu phát triển còn lại sau lọc, không phải independent gold test.
Các kết quả thí nghiệm trước đây được ghi riêng trong [lịch sử dự án](docs/PROJECT_HISTORY.md).

## Cài đặt và chạy trong VS Code

Dùng Python 3.12, mở terminal PowerShell tại root repository:

```powershell
# Chỉ tạo môi trường nếu chưa có .venv
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements/classical-base.txt
python -m pip install -r requirements/crawler.txt
```

Nếu máy đã có `.venv`, chỉ cần kích hoạt. Trong VS Code, chọn interpreter
`.venv/Scripts/python.exe`. Mở `cmt-tag.code-workspace` để xem repo và thư mục
dữ liệu sau lọc. Chỉ dùng một môi trường cho workflow hiện tại.

## Các lệnh chính

Chạy sau khi kích hoạt `.venv`. Những giá trị viết hoa là placeholder cần thay
bằng đường dẫn hoặc ID thực tế; thêm `--help` để xem đầy đủ tham số.

```powershell
# 1. Crawl: nhập mã phim rồi dán lần lượt các link Facebook
python -m src.crawler interactive --channel brave

# 2. Tạo bản lọc mới từ canonical nguồn đã xác minh
python scripts/build_master_dataset.py --filter-canonical outputs/canonical/versions/rebuild_20261112 --legacy-max-characters 1000 --output outputs/canonical/versions/NEW_FILTERED

# 3. Xuất task gán nhãn từ prepared records và split hợp lệ
python -m src.annotation export --data-root DATA_ROOT --version VERSION --split train --count 150 --output NEW_TASK

# 4. Nhập quyết định của người gán
python -m src.annotation import-human --task TASK_JSON --csv LABELS_CSV --annotator NAME --blind --output NEW_EVENTS

# 5. Huấn luyện từ release đã qua kiểm tra
python -m src.models train --release APPROVED_RELEASE --train-mode gold-only --output NEW_RUN

# 6. Đánh giá run đã huấn luyện
python -m src.models evaluate --run NEW_RUN --output NEW_EVALUATION
```

Build cũng nhận `--config CONFIG --output-root DATA_ROOT` để chuẩn bị records và
split. Export annotation yêu cầu prepared data; train yêu cầu release hợp lệ.
Hiện chưa có approved release cho dataset filtered, nên không đưa trực tiếp CSV
vào train. Output đã tồn tại không được ghi đè. Clone repo không tự có toàn bộ
raw, coordinator và model local cần cho các lệnh trên.

## Pilot 3 AI qua web — một file 600 câu

```powershell
python -m src.annotation pilot prepare
python -m src.annotation pilot export-web
# Tự tải cùng file/prompt lên ba chat web độc lập, rồi nhập CSV/JSON tải về:
python -m src.annotation pilot import-web --provider GPT --response PATH.csv --model "model hiển thị trên web"
python -m src.annotation pilot import-web --provider Claude --response PATH.csv --model "model hiển thị trên web"
python -m src.annotation pilot import-web --provider Gemini --response PATH.csv --model "model hiển thị trên web"
python -m src.annotation pilot analyze
python -m src.annotation pilot audit-import
```

Gửi **cùng một file đủ 600 câu**, không chia 500+100:
`outputs/ai_labeling/pilot_20261113/web_upload/pilot_600.json` và hướng dẫn trong
`PROMPT.txt` cạnh đó. Dùng chat mới, không đưa kết quả AI khác vào prompt.
Không tải coordinator/report/private manifest lên AI. Không có API client/key hay
token billing trong workflow; người dùng tự thao tác web. Kết quả cần đủ ID,
nhãn POS/NEG/NEU/REVIEW/EXCLUDE, reason ngắn. Import từ chối ID lạ/trùng/thiếu,
nhãn sai hoặc sửa nhãn cũ; có --allow-partial để giữ phần đúng nếu web cắt output.
Model web không rõ phiên bản thì ghi UNKNOWN_WEB_MODEL, không tự đoán.

Pool pilot riêng mở Facebook trong post development, giữ chặn quality
EXCLUDE/REVIEW, test/reserved/holdout và exact/near duplicate. Pool KEEP từ 6.967
lên 12.308: Facebook 31 → 5.372 (3 → 46 post), legacy giữ 6.936. 954 Facebook
record thiếu identity đủ tin cậy vẫn ngoài pool; không đoán post/comment ID.

Đã niêm phong **450 Facebook chưa nhãn** từ 46 post/31 mã phim (cap 12/post,
36/phim; thực tế tối đa 10/post), trộn mù với **150 calibration từ 425 nhãn người**
(50 POS/62 NEG/38 NEU, gồm 129 Facebook + 21 legacy). AI chỉ thấy record_id/text,
không thấy cohort/nhãn/metadata. Calibration không bao giờ vào silver; movie_id
legacy để null. Không PyVi cho input AI. Trước khi tải dữ liệu lên web vẫn cần
quyền chia sẻ nguồn: 21 legacy calibration chưa có xác minh quyền gửi ra ngoài.
20 mẫu tag-only mới đạt kiểm tra cấu trúc, chưa có semantic human review/FPR.

Sau import ba bên: metrics hiệu chuẩn từng AI/đồng thuận 3/3 có coverage và
abstention; pairwise/Fleiss; human audit tối đa 50 đồng thuận + 50 bất đồng, ẩn
nhãn AI. SILVER_CANDIDATE chưa approved; không tự tạo release, train hoặc chạy lại
gold. Report và mọi dữ liệu/predictions/workbook chỉ lưu local trong pilot folder.

Đã nhập đủ 600 ID từ mỗi web. Trên 150 nhãn development: Macro-F1 GPT 0,7008,
Claude 0,6972, Gemini 0,6843; không phải kết quả independent test. 383/600 đồng
thuận 3/3; 184 silver candidate chưa approved. Phân công người: review_blind.xlsx
100 câu và friend_share/review_friend_350.xlsx 350 câu còn lại, không trùng ID,
ẩn nhãn AI; giữ riêng 150 calibration. Các file chia sẻ chỉ local, không push data.

Trong lúc chờ 350 câu, có các bước **không train**:

```powershell
python -m src.annotation pilot audit-errors
# Chỉ khi bạn đã trả workbook; khai báo đúng nguồn, không tự coi nhãn AI là người:
python -m src.annotation pilot friend-import --annotator friend --origin human
python -m src.models plan-expansion
```

`friend-import` kiểm đúng ID/text/hash/guideline, không trùng 100 câu hoặc 150
calibration; hỗ trợ nguồn `human`, `human_reviewed_ai`, `ai`. AI-only vẫn là
suggestion, không vào training plan. Import giống hệt có thể lặp; bản sửa nhãn
phải dùng output mới để giữ lịch sử. File đang gán chỉ được đọc khi gọi import.

Audit lỗi tại `pilot_20261113/error_analysis/REPORT.md`: tách nhóm 3/3 và bất đồng;
những dấu hiệu cảm xúc/mỉa mai/đích người chỉ là review cue, không phải nguyên
nhân đã xác minh. Trong 14 lệch ở nhóm 3/3, 11 thuộc REVIEW/EXCLUDE, 3 thuộc
sentiment. Không suy rộng tỷ lệ trên mẫu có chủ đích thành lỗi toàn pool.

`configs/development_human_expansion.json` chuẩn bị 425 cũ vs 425 + human mới:
validation giữ nguyên 25 fold của 425 cũ cho cả hai điều kiện; thêm nhãn vào train
khi post và exact/near duplicate không chạm validation. Hiện biết 425 + 86 = 511
nhãn sentiment, 14 EXCLUDE giữ lịch sử, 350 câu vẫn chờ. Kế hoạch local ở
`pilot_20261113/development_plan/REPORT.md`; chưa có fit/predict/metrics mới,
không dùng silver hoặc gold và chưa approved release. Sau khi nhập bạn, tạo
kế hoạch output mới để giữ bản trước; không ghi đè artifact.

## Candidate mới: lọc tag-only và URL

```powershell
python scripts/build_master_dataset.py --quality-filter outputs/canonical/versions/filtered_20261112_final --output outputs/canonical/versions/filtered_20261113_quality_v1
```

Chỉ tạo version dẫn xuất; không đổi active pointer. Raw/minimal/human decisions
được giữ nguyên. `text_annotation_view` dùng chung cho future annotation;
model opt-in nhận `text_model(text_annotation_view)`. Tag-only chỉ tự EXCLUDE khi
metadata nguồn/DOM và phép xóa khớp; tên chưa xác minh chỉ REVIEW. URL-only tự
EXCLUDE; URL kèm nội dung giữ lại hoặc REVIEW. Human decisions chỉ nhận flags,
không bị loại hoặc thay text. DOM aggregate chỉ gọi `DOM_RULE_MATCH`.

Trong version mới, `candidate.local.jsonl` giữ mọi record với metadata quyết định;
`annotation_candidates.local.csv` chỉ gồm KEEP từ pool eligible cũ, không tự duyệt.
Version quality_v1 flag 315 tag-only EXCLUDE và 154 REVIEW; không có URL-only
trong dữ liệu thật. 315 câu vốn ngoài pool cũ; pool KEEP còn 6.967/6.968, một câu
chuyển REVIEW do reservation guard. Giữ đủ 425 nhãn sentiment; chưa duyệt AI pool.
REVIEW ở `review_candidates.local.jsonl`; audit/ví dụ local tại
`outputs/quality_filter_review/REPORT.md`. Các file đã tồn tại không ghi đè;
lần chạy khác cần output/review path mới. Không AI labeling hoặc evaluate lại gold.

## Thử nghiệm tiền xử lý trên nhãn phát triển

```powershell
python -m pip install -r requirements/classical-base.txt
python -m src.models preprocessing-cv --output outputs/preprocessing_experiments
```

Implementation opt-in: `src/preprocessing/model.py`; minimal view và model/config
Gold cũ không đổi. So A/B/C/D và các đối chứng tắt PyVi/teencode/rút chữ lặp bằng
5-fold × 5 seed, dùng chung fold: 425 nhãn người, kèm bảng phụ 346 Facebook.
79 legacy record thiếu post_id có group riêng, **không bảo đảm chống leakage theo
bài cho legacy**. Word vectorizer dùng `token_pattern=r'(?u)[^\s]+'`,
`lowercase=False`; char_wb (3,5) không dùng token_pattern. PyVi 0.1.1 được pin,
bảng teencode hẹp có kiểm soát, giữ `k` và emoticon. DOM metadata hiện chỉ đủ
`DOM_RULE_MATCH`, không gọi là verified; không xóa tiền tố tên bằng regex mới.

Kết quả development local: `outputs/preprocessing_experiments/REPORT.md`,
`comparison.csv`, `fold_results.csv`, `paired_deltas.csv`, `view_audit.csv`.
Char-SVM: A → C đạt Macro-F1 0,5434 → 0,5614 trên 425 câu; Facebook-only
0,5642 → 0,5677. DOM view không cải thiện ổn định; giữ pipeline mới opt-in.
Không tự chuyển active pipeline, không chọn cấu hình bằng gold hoặc evaluate lại.
Output đã tồn tại thì chọn thư mục output mới; dữ liệu/comment chỉ lưu local.

## Gold test: post mới, một người gán

File link: `outputs/gold/posts.csv`, cột `movie_id,post_url`. Chọn link trước khi
đọc comment. Quy trình có năm lệnh; **người dùng tự crawl**, các lệnh còn lại
không mở trình duyệt. Thay `RUN_ID` bằng run vừa crawl xong:

```powershell
python -m src.crawler crawl-batch --input outputs/gold/posts.csv --max-comments 100 --channel brave
python -m src.annotation gold sample --run RUN_ID
python -m src.annotation gold recheck --annotator user
python -m src.annotation gold agreement
python -m src.annotation gold evaluate
```

`sample` tái dùng exporter hiện có; cũng nhận `--export PATH` nếu đã có export.
Lệnh ghi SHA file link vào `outputs/gold/manifest.json` trước các bước khác,
từ chối post/comment cũ và reserve toàn bộ post mới khỏi AI/train. Chỉ lọc text
rỗng và exact duplicate trong batch; không lọc quality REVIEW, từ khóa hay độ dài.
DOM chỉ được chọn khi chứng minh là raw bị xóa không quá `mention_count` đoạn
tên hợp lệ; còn lại giữ raw. Near-duplicate với dữ liệu cũ giữ lại, gắn cờ.
Cap crawl lấy trực tiếp từ config run, phải là số nguyên **1–200**; tổng record
mỗi post (kể cả truncated còn trong journal) không được vượt cap đó. Cap được
ghi vào manifest, receipt và mô tả lấy mẫu, không mặc định là 60.
SHA/bản sao danh sách link nằm ở `outputs/gold/input_seals/` cùng thời điểm thực
tế; niêm phong sau khi crawl bắt đầu không được gọi là khóa trước crawl.
Lấy mẫu seed **20261113**, tối đa **12/post, 100/group, 36/phim, 300 câu**;
thiếu thì báo đúng số và cap chặn, không nới quota.

Điền `gold_test.xlsx` (id/text không sửa; label POS/NEG/NEU/REVIEW/EXCLUDE).
`recheck` chỉ chạy sau khi điền đủ, xuất `gold_recheck.xlsx`: ngẫu nhiên tối đa
100 ID cho **cùng người gán**, không hiện nhãn cũ. Thực hiện trong **<1 ngày**.
`agreement` tính **intra-annotator** agreement/Kappa và confusion matrix; nếu
lệch, điền `label_final` trong `gold_disagreements.xlsx` rồi chạy lại cùng lệnh
với `--final`. Code giữ cả hai nhãn ban đầu, chỉ khóa test sau quyết định cuối.
REVIEW/EXCLUDE không bị ép thành NEU và không vào metrics sentiment.

`evaluate` chỉ dùng test đã khóa và chạy **đúng một lần**; receipt được ghi
trước fit/predict, kể cả chạy lỗi cũng không tự cho phép thử lại. Code loại
train trùng/near-trùng hoặc vướng reservation, không bypass guard. Bốn cấu hình
cố định: BoW + ComplementNB/MNB; TF-IDF từ + LinearSVC balanced; TF-IDF char_wb
(3,5) + LinearSVC balanced. Không tune trên gold. Kết quả và bốn confusion PNG
ở `outputs/gold/results/`; mọi file chứa comment chỉ local, không commit.

Đây là test **một người gán**, recheck 100 câu trong <1 ngày; số comment đầu/post
bị giới hạn bởi `max_comments` thực tế trong config (1–200), theo thứ tự Facebook
hiển thị. Không coi là lấy mẫu ngẫu nhiên toàn Facebook hoặc inter-annotator agreement.

Trạng thái local ngày **13/11/2026** để review quy trình:

- Run `fb_b5f54539dce14c07a370a65b4835861d`: 1.184 comment/reply, 31 bài;
  26 success, 5 partial; cap 100/post. Export dùng `--allow-partial` có xác nhận
  của người dùng: raw không lỗi schema/trùng ID, nhưng có 72 lượt DOM không parse
  được; không xác minh độ bao phủ. Không diễn giải 72 lượt là 72 comment bị mất.
- SHA-256 `posts.csv`: `5b3be3850c7021b8b0404f5a76476f1944534db5cf2b6e9442338276ad61e0ef`.
  Bản sao được niêm phong lúc **23:25:53 +07:00 ngày 12/11**, sau khi run bắt đầu;
  không có bằng chứng khóa danh sách trước crawl.
- Chọn 230 câu từ 31 bài, 5 định danh cộng đồng/trang và 16 mã phim, gồm mã
  `phim_noi_chung` không xác định phim cụ thể. Có 125 reply; loại 1 exact duplicate
  trong batch; giữ và gắn cờ 2 câu gần trùng dữ liệu cũ. Thiếu 70 câu vì quota;
  không nới cap. Detector near-duplicate có bỏ shingle xuất hiện trên 256 records,
  nên không bảo đảm phát hiện mọi near-duplicate. Reserve toàn bộ 31 bài/1.184 ID.
- Một người gán 230 câu, gán lại mù 100 câu và chốt 9 bất đồng: agreement 91%,
  Cohen's Kappa 0,8792 trên 5 quyết định. Hai lượt gần nhau (khoảng 8 phút theo
  lúc kiểm tra lượt hai), có nguy cơ nhớ nhãn; không coi đây là hai người duyệt.
- Đã khóa 230 quyết định: POS 46, NEG 76, NEU 40, EXCLUDE 68; 162 câu sentiment
  đủ trạng thái cho đánh giá. Gold sau đó đã evaluate một lần với cấu hình cũ;
  giữ nguyên receipt/results, không chạy lại. Dataset filtered
  giữ nguyên manifest SHA `602d98e0ee184c8c01f7bd89e2e129918341a367fcfcf862e7b9f56d3352d0f6`.
- Lần kiểm thử gần nhất: **167/167 unittest pass**. Đã kiểm ID, text hash, nhãn
  hợp lệ, seed tái lập, reservation và checksum workbook khi khóa.

Reviewer kiểm tra `src/annotation/gold.py`, `src/models/core.py`,
`src/dataset/blind.py`, `src/data/pipeline.py` và `tests/test_gold_test.py`.
Ưu tiên audit guard leakage, bằng chứng chọn DOM, quota, blind recheck và receipt
đánh giá một lần. Số liệu trên là tóm tắt local; repository không chứa workbook,
comment hoặc nhãn theo ID để reviewer độc lập tái tính số liệu thật. Không gửi
nội dung test cho AI để chọn/sửa nhãn; dùng fixture để review implementation.

## Cấu trúc repository

```text
src/
  crawler/        Thu thập Facebook, journal, resume và export
  data/           Import, schema, kiểm tra chất lượng và chia nhóm
  dataset/        Lọc canonical, provenance và bảo vệ test
  preprocessing/  Tiền xử lý tối thiểu
  annotation/     Task, nhãn người, agreement và release
  models/         BoW/TF-IDF, mô hình và đánh giá
scripts/          Entry point build/filter
configs/          Cấu hình nguồn và fixture
requirements/     Dependencies và lock cần tái lập
tests/           Unit tests và fixture
docs/            Guideline, hướng dẫn, báo cáo lọc và lịch sử
data/            Snapshot dữ liệu/nhãn đã lưu
outputs/         Dataset và kết quả local
```

## Nhập bình luận để demo

Model demo học từ 425 nhãn người development, với cấu hình cố định.
Không dùng gold để train hoặc tune.
Tạo model local một lần bằng `python -m src.models build-demo`, sau đó chạy:

```powershell
.\.venv\Scripts\python.exe -m src.models predict
```

Menu có BoW + MultinomialNB, BoW + ComplementNB, TF-IDF word + SVM,
TF-IDF char_wb + SVM, so sánh bốn baseline, PhoBERT và ViSoBERT.
Nhập `/model` để đổi model; Enter trống hoặc Ctrl+C để kết thúc.
Có thể dùng `python -m src.models predict --model bow_complement_nb --text "Diễn xuất rất hay"`.
Bốn baseline nằm ở `outputs/demo_baselines_425/`; checkpoint Transformer
nằm ở `outputs/demo_transformers_425/`, không commit. Bình luận vừa nhập
không được lưu. Đây là demo dự đoán, có thể sai; không trả xác suất và không
phải một lần đánh giá gold mới.

Transformer cần PyTorch (`requirements/torch-cpu.txt`) và
`requirements/demo-transformers.txt`, cài cùng requirements classical hiện tại.
Train demo bằng `python -m src.models build-transformer-demo --model phobert`
hoặc `--model visobert`: 3 epoch cố định, batch 8, max length 128, AdamW 2e-5,
seed 20261113, chỉ 425 nhãn development, không chọn epoch theo gold.
PhoBERT dùng PyVi 0.1.1 để tách từ nhất quán lúc train/inference; đây là
xấp xỉ, khác bộ RDRSegmenter được tác giả khuyến nghị.
Xem model card [PhoBERT](https://huggingface.co/vinai/phobert-base-v2) và
[ViSoBERT](https://huggingface.co/uitnlp/visobert). Hai checkpoint demo mới
chưa được đánh giá độc lập; tên model không bảo đảm dự đoán tốt hơn baseline.

## Kiểm thử và tài liệu

```powershell
python -m unittest discover -s tests
```

- [Guideline gán nhãn V2.1](docs/guidelines/MOVIE_SENTIMENT_V2_1.md)
- [Hướng dẫn crawler và xử lý lỗi](docs/CRAWLER.md)
- [Báo cáo lọc dữ liệu](docs/DATASET_FILTER_REPORT.md)
- [Chỉ mục dữ liệu local](outputs/README.md)
- [Lịch sử thử nghiệm và các hướng đã bỏ](docs/PROJECT_HISTORY.md)

Raw, nhãn người, frozen splits, checkpoint và kết quả cũ được giữ nguyên.
Các hướng xử lý v3.1/v3.2 không còn là mặc định. Code và tài liệu trước đợt dọn
được lưu tại tag `before-cleanup-20261112`; không cần chạy lại các phase cũ.
