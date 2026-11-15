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
- Quy trình đang áp dụng: [AI gán trên web + người dùng duyệt](docs/annotation/QUY_TRINH_GAN_NHAN.md). Kế hoạch năm batch người gán đã thay thế; không giao thêm cho A/B.
- ChatGPT, Claude và Gemini chỉ chạy trên web do người dùng thao tác; không gọi API. Đã chia T/U và xuất 50 câu T gán mù; E/C chờ ID từ người dùng, chưa làm bước 3 trở đi. Không cần cài Transformer để crawl.

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

### Gán nhãn: quy trình đang áp dụng

Chỉ dùng [QUY_TRINH_GAN_NHAN.md](docs/annotation/QUY_TRINH_GAN_NHAN.md),
[guideline chính thức](docs/guidelines/SENTIMENT_GUIDELINE.md) và
[changelog](docs/guidelines/GUIDELINE_CHANGELOG.md). Không tự thêm bước hoặc đổi thứ tự.
Quy trình mới dùng lại **selection 1.000 ID** trong `outputs/annotation_round_01/`;
đã chia T/U theo nguyên post và xuất workbook 50 câu T gán mù. E/C chờ danh sách
ID từ người dùng; chưa có nhãn mù được import, chưa xuất chunk cho AI hoặc train.
Prompt `docs/annotation/AI_LABEL_PROMPT.md` chưa được người dùng cung cấp;
không tạo prompt thay người dùng, chưa pin SHA prompt.

**Kế hoạch năm batch A/B đã thay thế. Batch 1 đã prepare, không giao**; workbook
cũ không dùng tiếp và không giao thêm batch cho annotator A/B. Selection, manifest,
snapshot và nhãn pilot lịch sử giữ nguyên. Các CLI `sentiment-pilot` hiện có phục vụ
tái lập luồng cũ và hai thao tác mới `split-tu`, `blind-review`. Chưa có implementation
đầy đủ cho bước 3 trở đi; không chạy prepare/compare/import cũ để thay các bước đó.

Mỗi tập sẽ giữ snapshot nguyên byte của guideline và ghi SHA vào manifest.
Compare/import kiểm snapshot, không đọc lại file chính thức. Một lượt cũ không tự
đổi guideline khi file chính thức đổi; lịch sử pilot có lệch manifest/bộ giao được
mô tả tại [báo cáo pilot](docs/SENTIMENT_PILOT_RESULTS.md).

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
- [Pilot lịch sử và lệch provenance](docs/SENTIMENT_PILOT_RESULTS.md): manifest pin PROPOSED `f079ce7b…`, nhưng bộ giao A/B kèm file `2ba9f0…`; người dùng xác nhận người gán đọc file kèm. Có 200 quyết định, 178 nhãn sentiment sau đối soát. Kappa không xác nhận riêng một bản guideline hoặc độ độc lập người gán.
- Kết quả local đã chốt giữ nguyên ở `outputs/sentiment_pilot_v3_1/comparison_received_20261115/adjudicated/`. Tên và manifest cũ không đổi.
- Manifest có đường dẫn guideline cũ được tra sang `history/` rồi kiểm đúng SHA; không tự thay bằng guideline chính thức mới. Luồng V1 giữ tham chiếu lịch sử riêng để tái lập, không dùng làm mặc định cho lượt cảm xúc chung mới.

## Lưu lịch sử guideline

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

Bản trước khi thay hiện tại được giữ nguyên byte tại
`docs/guidelines/history/SENTIMENT_GUIDELINE_b2548267.md`. Guideline chính thức
mới bỏ mục workbook/quy trình và ví dụ “nổi da gà”, thêm quy tắc điểm số;
quy trình vận hành nằm riêng trong tài liệu annotation.

### Kế hoạch cũ đã thay thế

Kế hoạch năm batch người gán và bước dự phòng bổ sung nguồn nhỏ theo tỷ lệ POS
**đã thay thế**, không còn là bước tiếp theo. Batch 1 đã prepare, không giao;
không lấy mẫu bổ sung hoặc sửa selection 1.000 ID. Thực hiện về sau chỉ theo
[quy trình AI gán + người dùng duyệt](docs/annotation/QUY_TRINH_GAN_NHAN.md),
việc chốt tài liệu trước đó không chạy workflow. Theo yêu cầu tiếp theo, đã làm
riêng chia T/U và xuất 50 câu mù; chưa làm bước 3 trở đi.

### Trạng thái bước 1–2 (15/11/2026)

- T: **200 câu / 10 post / 10 movie_id**; U: **800 câu / 51 post / 42 movie_id**.
- Seed `20261115`; phân tầng nguồn, xáo post rồi giữ nguyên từng post. T ưu tiên có đủ năm nguồn. Ba nguồn nhỏ chỉ có một post/nguồn nên nằm trọn ở T, U không có chúng; tỷ lệ nguồn T không phản ánh phân phối tự nhiên.
- Không giao nhau theo ID/post; exact/near theo guard hiện có cũng bằng 0. Ba movie_id xuất hiện ở cả T/U; đây là chia theo post, không phải holdout theo phim.
- Workbook mù: `outputs/annotation_blind_50_01/T_blind_50.xlsx`, 50 ID ngẫu nhiên thuộc T, chỉ bốn cột `comment_id,text_clean,label,note`, chưa có nhãn. Dùng `guideline_snapshot.md` bên cạnh; khi gán không xem AI hoặc metadata T/U.
- Báo phân bố local: `outputs/annotation_tu_01/REPORT.md`. Chưa import/khóa nhãn người dùng; E/C đang chờ ID, chưa làm bước 3 trở đi.

```powershell
# Chỉ tái lập khi cần, với thư mục output mới; không ghi đè kết quả đã giao.
python -m src.annotation sentiment-pilot split-tu --round outputs/annotation_round_01 --directory outputs/NEW_TU
python -m src.annotation sentiment-pilot blind-review --split outputs/NEW_TU --directory outputs/NEW_BLIND_50
node scripts/export_sentiment_pilot.mjs outputs/NEW_BLIND_50 --blind-review
```
