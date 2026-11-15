# cmt-tag — Phân loại cảm xúc bình luận tiếng Việt

Bài tập lớn Xử lý dữ liệu văn bản, sử dụng **Python CLI** và bình luận phim
làm nguồn dữ liệu. Ba lớp sentiment: **POS / NEG / NEU**.

**Crawl → Lọc dữ liệu → Tiền xử lý tối thiểu → Kiểm tra chất lượng → Gán nhãn → Train → Đánh giá.**

## Hướng hiện tại

V2 phân loại **cảm xúc chung mà người viết thể hiện trong chính bình luận**,
chỉ dùng `text_clean`. Đối tượng cảm xúc có thể là phim, diễn viên, người bình luận,
group hoặc sự việc khác. Không suy sentiment từ comment cha/bài viết; không loại
câu chỉ vì ngoài lề phim. POS / NEG / NEU là ba lớp mô hình; REVIEW / EXCLUDE là
trạng thái xử lý, không phải hai lớp sentiment bổ sung.

- Chỉ dùng [guideline chính thức](docs/guidelines/SENTIMENT_GUIDELINE.md) và [changelog](docs/guidelines/GUIDELINE_CHANGELOG.md). Mỗi lượt prepare ghi SHA256 của bản được giao; không đổi luật giữa lượt gán.
- V1 xét thái độ đối với phim theo guideline V2.0/V2.1. Nhãn người, AI, model và Gold V1 chỉ giữ làm lịch sử, **không gộp hoặc đổi tên thành nhãn cảm xúc chung V2**. Muốn dùng lại phải gán lại theo định nghĩa mới và kiểm tra leakage.
- Gold V1 đã đánh giá một lần; không dùng để chọn preprocessing hoặc tune model V2. Chưa có independent Gold V2.
- Pilot lịch sử đã đối soát 200 quyết định, có 178 nhãn sentiment. Nhãn thuộc về SHA đã giao, chưa tự chuyển sang quy tắc mới; xem phần lịch sử bên dưới.
- Thiết kế là hai annotator A/B và người dùng adjudicator. Nguồn gán/AI hỗ trợ của hai workbook đã nhận chưa được xác minh; không khẳng định độ độc lập của lượt đó.
- Không gọi API gán nhãn tự động trong workflow đang chạy. Guideline yêu cầu người gán không dùng AI quyết định nhãn hoặc viết note. Không cần cài Transformer để crawl.

## Cài đặt

Python 3.12, Windows PowerShell, Brave hoặc Chrome:

```powershell
git clone https://github.com/sou1406-ver/cmt-tag.git
cd cmt-tag
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements/crawler.txt
```

Repo đã được người dùng chuyển public. Nếu đã có `.venv`, dùng lại.
**Lịch sử Git vẫn có dữ liệu Facebook**; bỏ track không xóa lịch sử. Người dùng
chọn chưa đổi visibility ngày 15/11/2026. Xem [privacy audit](GIT_PRIVACY_AUDIT.md)
và [kế hoạch dọn lịch sử, chưa thực hiện](GIT_HISTORY_CLEANUP_PLAN.md).
Trong VS Code chọn `.venv/Scripts/python.exe`, hoặc mở `cmt-tag.code-workspace`.
Các lệnh dưới gọi trực tiếp Python của venv, không cần activate.

## Crawl Facebook

Đăng nhập thủ công bằng profile riêng, rồi đóng cửa sổ profile đó trước khi crawl:

```powershell
.\.venv\Scripts\python.exe -m src.crawler login --channel brave --profile data/browser_profile_brave_manual
.\.venv\Scripts\python.exe -m src.crawler interactive --channel brave --profile data/browser_profile_brave_manual --max-comments 100 --max-rounds 20 --post-timeout 90
```

Nhập mã phim một lần, sau đó dán link vào prompt. Gõ `movie ma_moi` để đổi phim,
Enter trống để kết thúc; Ctrl+C checkpoint. URL dán vào prompt không bị shell cắt
ở `&`. Resume dùng `interactive --resume RUN_ID` cùng channel/profile; giới hạn
được lấy từ cấu hình run đã lưu.

Với danh sách bài đã chọn sẵn, tạo CSV local có `movie_id,post_url`, rồi chạy:

```powershell
.\.venv\Scripts\python.exe -m src.crawler crawl-batch --input data/posts.csv --channel brave --profile data/browser_profile_brave_manual --max-comments 100 --max-rounds 20 --post-timeout 90
.\.venv\Scripts\python.exe -m src.crawler validate --run RUN_ID
.\.venv\Scripts\python.exe -m src.crawler export --run RUN_ID
```

`RUN_ID` là mã in khi bắt đầu. Output export không được ghi đè. Chỉ dùng
`--allow-partial` sau khi xem lỗi DOM; raw/journal vẫn giữ nguyên.
Giới hạn 100 là cấu hình thu thập, không phải số mẫu ngẫu nhiên hay cam kết lấy đủ.
Không dùng các post test/reserved để phát triển crawler hoặc mô hình.

Chiến dịch V2 dùng lại batch CLI; audit gần nhất ghi nhận 12.795 câu. Lệnh cho các đợt thu thập tiếp theo:

```powershell
.\.venv\Scripts\python.exe -m src.crawler crawl-batch --campaign-v2 --input data/posts_v2.csv --channel brave --profile data/browser_profile_brave_manual --max-comments 300 --post-delay 5
.\.venv\Scripts\python.exe -m src.crawler crawl-batch --resume RUN_ID --channel brave --profile data/browser_profile_brave_manual
.\.venv\Scripts\python.exe -m src.crawler export --run RUN_ID --format xlsx
```

CSV có thể thêm `source_name,source_type,max_comments`; V2 tối đa 500/bài,
chống trùng ID với journal cũ trong cùng data-root và cập nhật thống kê sau mỗi bài.
Reaction/thời gian/tổng comment thiếu bằng chứng DOM để null. Excel duy nhất ở
`data/imports/RUN_ID/review.xlsx`, lọc được theo bài/phim/trạng thái; không phải
dữ liệu train hay nhãn đã duyệt. Kế hoạch 40–80 bài/15–20 phim và các giới hạn:
[hướng dẫn chiến dịch V2](docs/CRAWLER.md#chiến-dịch-v2--chuẩn-bị-công-cụ-chưa-chạy-thu-thập-lớn).

### Text được xuất như thế nào?

| Trường | Ý nghĩa |
|---|---|
| `text_raw` | Text gốc trong vùng nội dung comment/reply; giữ để đối chiếu |
| `text_without_mentions` | Chỉ bỏ mention tài khoản xác nhận qua DOM |
| `text_clean` | Bỏ thêm URL và anchor của link chia sẻ, giữ chữ ngoài link |
| `clean_status` | KEEP / REVIEW / EXCLUDE, chưa phải nhãn sentiment |
| `clean_evidence` | Loại/rule và vị trí đoạn bị loại trong raw, theo UTF-16 |

Giữ tiếng Việt, emoji Unicode/ảnh có alt emoji, emoticon, teencode, phủ định và dấu
câu. Không đoán tên từ chữ hoa; tên diễn viên/nhân vật viết thuần vẫn giữ. Không
thu thêm tên/ID tác giả. Rỗng hoặc chỉ còn dấu câu như `?` vào EXCLUDE; chỉ emoji/emoticon/điểm số vào
REVIEW kỹ thuật; có chữ vào KEEP dù kèm media. Đây không phải nhãn sentiment:
người gán vẫn quyết định theo guideline. Link không đủ bằng chứng không bị xóa mù.

**Không nhầm hai cột:** `clean_status=REVIEW` là cờ kiểm tra kỹ thuật của crawler;
`sentiment_label=REVIEW` là quyết định không đủ căn cứ gán sentiment theo guideline.
Không sao chép hoặc suy nhãn sentiment từ `clean_status`. Ví dụ, `😍` có thể mang
`clean_status=REVIEW` nhưng được gán POS theo guideline; `:))` đứng riêng có thể mang
cùng trạng thái kỹ thuật nhưng được gán NEU. Người gán chỉ đọc `text_clean` và áp
dụng guideline, không dùng cờ kỹ thuật làm gợi ý cực tính hay lý do loại câu.
Journal cũ không có clean/evidence sẽ không được điền suy đoán.

## Dữ liệu ở đâu?

| Dữ liệu local | Đường dẫn từ root repo |
|---|---|
| Raw và checkpoint từng run | `data/crawl_runs/RUN_ID/` |
| CSV raw + clean + metadata, import config | `data/imports/RUN_ID/` |
| Excel kiểm tra crawler và thống kê batch gần nhất | `outputs/crawler_review_20261114/` |
| Dataset V1 sau lọc để tham chiếu | `outputs/canonical/versions/filtered_20261112_final/` |
| Nhãn người/AI và kết quả cũ | Xem [chỉ mục local](outputs/README.md) |
| Output lịch sử đã gom ZIP | `data/archive/history_before_v2_20261113.zip` |

Dataset tham chiếu V1 có **25.810 dòng**: 7.146 Facebook và 18.664 legacy,
còn **425 nhãn sentiment người theo tiêu chí V1**. Bộ này khác định nghĩa cảm xúc chung.
Nhãn pilot hiện được lưu riêng; không nhập vào canonical V1.
Bộ legacy thiếu xác minh nguồn/quyền sử dụng và cách tạo nhãn `overall`;
**không dùng `overall` làm ground truth**.

Không nối các snapshot phase/cleaning vào nhau: chúng có thể chứa cùng ID.
Không tự nhập batch mới vào canonical hay sửa raw, human decisions, frozen split
hoặc test reservation. Clone Git chỉ có code/docs/fixture, không có corpus,
workbook, profile, checkpoint hoặc kết quả local.

## Code và kiểm thử

```text
src/crawler/        Selenium, DOM extraction, journal, resume, export
src/preprocessing/  Tiền xử lý tối thiểu và các view tùy chọn
src/data/           Import, schema, quality và grouped split
src/dataset/        Canonical/filter, provenance và bảo vệ test
src/annotation/     Pilot text-only V2; workflow V1 giữ để đối chiếu
src/models/         Baseline/evaluation và demo V1, chưa phải model V2
scripts/            Entry point build/filter hiện có
configs/            Cấu hình và fixture
requirements/       Dependencies đã pin và environment locks
tests/             Unit tests, HTML/data fixtures
```

Crawl/DOM tests dùng fixture; không đăng nhập Facebook. Muốn chạy toàn bộ test,
cài thêm môi trường classical và dùng lệnh dưới; test Transformer cần môi trường
optional tương ứng. Không tự nâng package hoặc cài lại venv nếu máy đã đủ deps.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/classical-base.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Các CLI annotation/models còn trong repo phục vụ lịch sử và tái lập; không chạy
`gold evaluate`, train hoặc silver-CV để chuẩn bị V2 khi chưa có protocol/nhãn mới.
Baseline dự kiến dùng BoW/TF-IDF, vectorizer chỉ fit trên train và chia nhóm theo
bài đăng. Chưa công bố kết quả V2; không dùng điểm V1 thay cho đánh giá V2.

## Git và tài liệu

Audit relevance phụ trợ cho batch mới (không đổi mục tiêu cảm xúc chung V2):
`python scripts/sample_audit.py sample` xuất 240 random + 60 hard KEEP vào
`outputs/semantic_audit_20261114/`. Người gán điền bốn cột theo hướng dẫn;
Excel `audit_sample.xlsx` có tab **Gán nhãn**, điền bốn cột vàng C–F;
`python scripts/sample_audit.py summarize` ưu tiên đọc Excel nếu có, kiểm ID/text
và metadata trước khi tổng hợp. CSV gốc được giữ nguyên.
Chỉ random có trọng số dùng ước lượng; chưa có nhãn người thì chưa có tỷ lệ relevance.

Audit relevance đã dừng ở **107/300** theo trao đổi với người dùng, không gán nốt
193 câu. [Tóm tắt để review](docs/SEMANTIC_AUDIT_SUMMARY.md) chỉ có thống kê,
không đăng corpus hoặc workbook.

### Pilot sentiment text-only (200 câu, hai người)

Chỉ đọc `text_clean` theo [guideline chính thức](docs/guidelines/SENTIMENT_GUIDELINE.md).
Đường dẫn được khai báo một lần tại `src/annotation/guidelines.py:GUIDELINE`.
Prepare chép nguyên byte thành `guideline_snapshot.md` trong batch và ghi SHA256
của bản chép vào manifest. Compare/import kiểm snapshot, không đọc lại file chính thức.
Đổi file chính thức cho lượt sau không làm mất khả năng kiểm lượt đã giao. Chỉ đổi guideline giữa các lượt và cập nhật changelog.
Không chạy prepare vào thư mục có dữ liệu. Tên output mới không chứa phiên bản guideline.

```powershell
# Thay PATH_TO_PREVIOUS_PILOT và bốn đường dẫn export; dùng thư mục lượt mới.
python -m src.annotation sentiment-pilot prepare --directory outputs/annotation_round_NEW --exclude-pilot PATH_TO_PREVIOUS_PILOT --sources EXPORT_1.csv EXPORT_2.csv EXPORT_3.csv EXPORT_4.csv
# Xuất Excel: Node bundled + @oai/artifact-tool, không cần API.
node scripts/export_sentiment_pilot.mjs outputs/annotation_round_NEW/batch_01
# Sau khi hai người điền xong (không chạy trên file trống):
python -m src.annotation sentiment-pilot compare --directory outputs/annotation_round_NEW/batch_01 --agreement-audit-count 20
# Excel đối soát cho người dùng, sau khi compare thành công:
node scripts/export_sentiment_pilot.mjs outputs/annotation_round_NEW/batch_01/comparison --adjudication
# Sau khi người kiểm duyệt điền final_label / adjudication_note:
python -m src.annotation sentiment-pilot adjudicate --directory outputs/annotation_round_NEW/batch_01 --decisions outputs/annotation_round_NEW/batch_01/comparison/adjudication.xlsx --adjudicator user
```

Lệnh export dùng runtime `@oai/artifact-tool` bundled của Codex, không phải npm deps
của crawler. Nếu chưa có module resolution, tạo junction tạm `scripts/node_modules`
tới `node_modules` do `load_workspace_dependencies` trả về rồi gỡ riêng link sau khi xuất;
không cài thêm thư viện vào venv và không xóa runtime đích. Python prepare/compare không cần Node.
Prepare từ chối ghi đè thư mục; export từ chối ghi đè Excel; compare xuất thư mục
`comparison/` mới. Có thể chỉ định `compare --output outputs/PILOT_COMPARISON_NEW` khi cần chạy lại.

Hai file `pilot_sentiment_annotator_A.xlsx` / `pilot_sentiment_annotator_B.xlsx`
ở output local: cùng 200 ID/thứ tự, **160 random + 40 hard (20%)**, không có nhãn
điền sẵn hoặc confidence bắt buộc. REVIEW cần note ngắn; báo lỗi ở `cleaning_issue`,
không sửa text. Manifest khóa nguồn/text SHA và đánh dấu post/ID đã exposure cho
development, không được dùng làm independent test tương lai. Bộ lọc reservation,
exact/near duplicate dùng guard hiện có; không đổi Gold hoặc split cũ.
Compare giữ nhãn A/B riêng, xuất Kappa chính 5 nhãn và Kappa phụ trên các cặp
POS/NEG/NEU kèm n/tỷ lệ giữ lại, ma trận 5×5, câu lệch và adjudication chưa điền.
Kappa suy biến trả null kèm lý do, không thay bằng 0/1. Kết quả lượt đã nhận được công bố riêng, không thay bằng kết quả sau đối soát.

**Thiết kế yêu cầu hai annotator độc lập A/B; người dùng là adjudicator**, được xem cả
nhãn/ghi chú A/B sau khi hai người gán xong, không phải người gán độc lập thứ ba.
Kappa luôn tính trên nhãn A/B gốc trước đối soát, không từ `final_label`.
`adjudication.local.csv` / Excel có đúng các cột `comment_id, text_clean, label_A,
label_B, note_A, note_B, final_label, adjudication_note`. Toàn bộ bất đồng được
đưa lên đầu và tô cam trong Excel; thêm mặc định tối đa 20 câu đồng thuận chọn
ngẫu nhiên bằng seed cố định để kiểm tra chất lượng (tô xanh). Có thể chỉnh số
câu đồng thuận qua `--agreement-audit-count`, không đổi mẫu pilot 200 câu.
`final_label` để trống ở cả hai nhóm. Chỉ nhập hai cột cuối; REVIEW cần note.
Importer từ chối sửa ID/text/nhãn hoặc note gốc A/B, thiếu/trùng dòng và nhãn cuối
không hợp lệ. Nhãn cuối trống trên câu bắt buộc kiểm tra được giữ `PENDING_REVIEW`;
không tự lấy nhãn A/B. Kết quả lưu riêng tại `comparison/adjudicated/`, có receipt/hash,
giữ nguyên A/B cùng Kappa. `pilot_final_decisions.local.csv` luôn đủ 200 ID:
đồng thuận **ngoài mẫu kiểm tra** lấy nhãn A=B (`AB_AGREE`); câu có nhãn do người dùng
chốt là `ADJUDICATED`. Đồng thuận thuộc mẫu kiểm tra vẫn phải được người dùng chốt. Riêng lượt đã nhận,
người dùng xác nhận tường minh rằng ô không sửa nghĩa là giữ A=B; xác nhận này được
lưu trong lịch sử riêng, không phải quy tắc tự điền mặc định cho lượt khác.
`pilot_trainable.local.csv` chỉ gồm POS/NEG/NEU đã có final, không REVIEW/EXCLUDE/pending;
đây chỉ là export, không tự đưa vào train hoặc Gold. `summary.json` báo số nguồn nhãn,
phân bố nhãn cuối, trainable, REVIEW/EXCLUDE và số đồng thuận bị sửa. Còn pending thì
`INCOMPLETE_ADJUDICATION`; chỉ đủ 200 final hợp lệ mới `PILOT_ADJUDICATION_COMPLETE`.
Workbook và mọi output chứa comment chỉ lưu local, không commit.

Chỉ commit code, tài liệu, config và fixture tổng hợp. `.gitignore` chặn dữ liệu,
outputs, venv, profile, secrets và model. Không dùng `git add -f` để đẩy các file này.
Ngừng track không xóa bản cũ trong Git history; không rewrite history.

```powershell
git status --short
git pull --ff-only
# Sau khi đã kiểm tra và test các thay đổi:
git add README.md
git commit -m "Update project documentation"
git push origin main
```

- [Crawler: cấu hình, export và lỗi thường gặp](docs/CRAWLER.md)
- [Chỉ mục dữ liệu và kết quả local](outputs/README.md)
- [Lịch sử dự án](docs/PROJECT_HISTORY.md)
- [Báo cáo lọc dataset V1](docs/DATASET_FILTER_REPORT.md)
- [Guideline V2.1 lịch sử của bài toán V1](docs/guidelines/history/MOVIE_SENTIMENT_V2_1.md) — không phải guideline cảm xúc chung mới.

## Audit sơ bộ dữ liệu crawl V2

[Báo cáo 12.795 bình luận](docs/V2_CRAWL_PRELIMINARY_AUDIT.md): thống kê kỹ thuật, nguồn, metadata và duplicate; chưa phải đánh giá sentiment.
Chạy lại bằng `python scripts/sample_audit.py inventory --output outputs/v2_audit_verify` trên bốn export gốc được ghi SHA trong báo cáo. Output chi tiết chứa ID chỉ lưu local; chọn thư mục output mới mỗi lần chạy.

## Lịch sử guideline và nhãn

- [Changelog](docs/guidelines/GUIDELINE_CHANGELOG.md) ghi các mốc V2.0/V2.1, V3.1/V3.2 và bản chính thức mới. Các byte cũ giữ tại `docs/guidelines/history/`.
- [Pilot bản PROPOSED](docs/SENTIMENT_PILOT_RESULTS.md): manifest pin SHA `f079ce7b5ecedd6242d99808ee0b010b28ea6f8b8afc4ba01f7cf86552d08433`, chưa duyệt; B ghi DRAFT. Có 200 quyết định, 178 nhãn sentiment sau đối soát. Kappa là kết quả trước đối soát của lượt bản đề xuất, không phải kết quả bản V3.1 chính thức hay quy tắc mới.
- Kết quả local đã chốt giữ nguyên ở `outputs/sentiment_pilot_v3_1/comparison_received_20261115/adjudicated/`. Tên và manifest cũ không đổi.
- Manifest có đường dẫn guideline cũ được tra sang `history/` rồi kiểm đúng SHA; không tự thay bằng guideline chính thức mới. Luồng V1 giữ tham chiếu lịch sử riêng để tái lập, không dùng làm mặc định cho lượt cảm xúc chung mới.

## Snapshot và chuẩn bị lượt gán chính thức

Trước khi sửa guideline chính thức, chạy đoạn dưới để lưu đúng byte hiện tại vào
history; sau đó thêm dòng changelog mô tả thay đổi và lượt áp dụng. Nếu tên SHA8
đã có, phải kiểm SHA đầy đủ, không ghi đè một file khác nội dung.

```powershell
$guidePath = 'docs/guidelines/SENTIMENT_GUIDELINE.md'
$guideHash = (Get-FileHash -LiteralPath $guidePath -Algorithm SHA256).Hash.ToLowerInvariant()
$archivePath = 'docs/guidelines/history/SENTIMENT_GUIDELINE_' + $guideHash.Substring(0,8) + '.md'
if (Test-Path -LiteralPath $archivePath) {
    if ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $guideHash) { throw 'Archive SHA collision' }
} else { Copy-Item -LiteralPath $guidePath -Destination $archivePath }
# Sau đó sửa guideline và thêm dòng docs/guidelines/GUIDELINE_CHANGELOG.md.
```

CLI hiện có hỗ trợ `sentiment-pilot prepare --sources` với đúng bốn export,
`--exclude-pilot` trỏ pilot cũ và `--directory` là thư mục lượt mới. Nó chọn
1.000 KEEP, cap 30/post, ưu tiên census nguồn nhỏ trong cap; loại post/ID pilot,
test/reserved và exact/near duplicates. Seed cố định, không chọn theo sentiment.
Chỉ batch 1 được prepare; các phần 2–5 giữ trong selection manifest, chưa giao.

Batch 1 đã giao tại `outputs/annotation_round_01/batch_01/`: A/B cùng 200 ID,
nhãn và note trống; snapshot guideline gửi kèm. Trang đầu ghi SHA và
**Không dùng AI quyết định nhãn hay viết note**. Phân bố theo nguồn/post/movie
nằm trong `outputs/annotation_round_01/README.md`; có 61 post, 49 movie_id.
Không dùng lại manifest pilot lịch sử hoặc gộp nhãn cũ vào lượt này.

### Bước dự phòng sau batch 1: bổ sung nguồn nhỏ

Chỉ là phương án dự phòng, **chưa chọn mẫu hoặc xuất thêm workbook**. Giữ nguyên
batch 1 đã giao và bốn phần còn lại đã niêm phong. Cap 30/post của lượt hiện tại
khiến mỗi nguồn nhỏ chỉ có một post còn phù hợp được chọn tối đa 30 câu; đây
không phải thực hiện ý định lấy hết nguồn nhỏ. Chưa có nhãn batch 1 nên **chưa biết
POS có thiếu hay không**; không suy tỷ lệ POS từ tên nguồn.

Sau khi gán và đối soát batch 1, báo cả POS/200 quyết định và
POS/(POS+NEG+NEU), cùng số REVIEW/EXCLUDE. Nếu tỷ lệ POS trong ba lớp sentiment
thấp hơn khoảng 20%, xem xét một batch bổ sung khoảng 150 câu từ phần còn lại
của KhenPhim, Cuồng Phim và XEM PHIM & BÌNH PHIM. Mốc 20% là tín hiệu xem xét,
không tự kích hoạt hoặc bảo đảm cân bằng nhãn.

Nếu thực hiện: manifest riêng ghi `sampling_type=purposeful`, mục đích tăng độ
phủ nguồn/tìm thêm ứng viên POS, số thực tế, quota nguồn/post và mọi thay đổi so
với cap 30/post của lượt trước. Không sửa manifest đã khóa. Chỉ lấy KEEP đủ điều
kiện, loại toàn bộ 1.000 ID đã chọn, pilot/cùng post pilot, dữ liệu test/reserved
và exact/near duplicates theo guard hiện có. Tổng 44/52 câu của một nguồn chưa
phải số còn đủ điều kiện; phải đếm lại sau lọc, không ép đủ 150.

Không gán sẵn POS theo nguồn: A/B vẫn gán độc lập theo snapshot guideline.
Nhãn được duyệt có thể dùng cho train sau kiểm leakage; batch purposeful không
dùng ước lượng phân bố nhãn toàn corpus hoặc làm test đại diện/độc lập. Khi chia
train/dev vẫn nhóm theo post và duplicate; không chia ngẫu nhiên từng comment.
