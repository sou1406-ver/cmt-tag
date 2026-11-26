# cmt-tag — Phân loại cảm xúc bình luận tiếng Việt

Bài tập lớn Xử lý dữ liệu văn bản, sử dụng **Python CLI** và bình luận phim
làm nguồn dữ liệu. Ba lớp sentiment: **POS / NEG / NEU**.

**Crawl → Lọc dữ liệu → Tiền xử lý tối thiểu → Kiểm tra chất lượng → Gán nhãn → Train → Đánh giá.**

[Báo cáo bài tập lớn](docs/BAO_CAO_BTL.md) dùng **T2** làm tập test chính. Xem [chỉ mục local](outputs/README.md) để tìm bộ nhãn, lô chờ gán và manifest.

Crawl bằng [Python CLI](docs/CRAWLER.md). Script [chuẩn hóa bình luận](scripts/chuan_hoa_binh_luan_v2.py) nhận một câu hoặc file Excel và xuất lại Excel. [Báo cáo BTL](docs/BAO_CAO_BTL.md#chuẩn-hóa-bản-đọc-v2) có lệnh CMD cho cả hai chế độ.

## Hướng hiện tại

V2 phân loại **cảm xúc chung mà người viết thể hiện trong chính bình luận**,
chỉ dùng `text_clean`. Đối tượng cảm xúc có thể là phim, diễn viên, người bình luận,
group hoặc sự việc khác. Không suy sentiment từ comment cha/bài viết; không loại
câu chỉ vì ngoài lề phim. POS / NEG / NEU là ba lớp mô hình; REVIEW / EXCLUDE là
trạng thái xử lý, không phải hai lớp sentiment bổ sung.

- Chỉ dùng [guideline chính thức](docs/guidelines/SENTIMENT_GUIDELINE.md) và [changelog](docs/guidelines/GUIDELINE_CHANGELOG.md). Mỗi lượt prepare ghi SHA256 của bản được giao; không đổi luật giữa lượt gán.
- V1 xét thái độ đối với phim theo guideline V2.0/V2.1. Nhãn người, AI, model và Gold V1 chỉ giữ làm lịch sử, **không gộp hoặc đổi tên thành nhãn cảm xúc chung V2**. Muốn dùng lại phải gán lại theo định nghĩa mới và kiểm tra leakage.
- Gold V1 đã đánh giá một lần và chỉ dùng để tham chiếu lịch sử. T2 là tập chấm chính của V2, gồm 613 câu thuộc ba lớp sentiment.
- Pilot lịch sử đã đối soát 200 quyết định, có 178 nhãn sentiment. Nhãn thuộc về SHA đã giao, chưa tự chuyển sang quy tắc mới; xem phần lịch sử bên dưới.
- Quy trình đang áp dụng: [AI gán trên web + người dùng duyệt](docs/annotation/QUY_TRINH_GAN_NHAN.md). Kế hoạch năm batch người gán đã thay thế; không giao thêm cho A/B.
- ChatGPT, Claude và Gemini được dùng để gán nhãn qua web. T2 đã gộp T gốc với phần test mở rộng đã duyệt. Hàng chờ hiện có 1.731 câu. Không cần cài Transformer để crawl.

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
| Workbook V2 chính và nhãn nguồn | `outputs/02_Du_lieu_va_nhan/` |
| T2 và các lô còn chờ gán | `outputs/01_T2_va_cho_gan/` |
| Train, T2 và cấu hình đã đóng băng | `outputs/03_Dau_vao_chinh_thuc/` |
| Kết quả các thử nghiệm phát triển | [Báo cáo BTL](docs/BAO_CAO_BTL.md) |

Dataset tham chiếu V1 có **25.810 dòng**: 7.146 Facebook và 18.664 legacy,
còn **425 nhãn sentiment người theo tiêu chí V1**. Bộ này khác định nghĩa cảm xúc chung.
Kết quả pilot V1 nằm trong báo cáo lịch sử.
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

Audit relevance lấy 240 câu ngẫu nhiên và 60 câu KEEP khó. Người gán đã rà **107/300** câu. [Báo cáo audit](docs/SEMANTIC_AUDIT_SUMMARY.md) lưu thống kê của lượt này.

### Gán nhãn: quy trình đang áp dụng

Chỉ dùng [QUY_TRINH_GAN_NHAN.md](docs/annotation/QUY_TRINH_GAN_NHAN.md),
[guideline chính thức](docs/guidelines/SENTIMENT_GUIDELINE.md) và
[changelog](docs/guidelines/GUIDELINE_CHANGELOG.md). Không tự thêm bước hoặc đổi thứ tự.
Quy trình dùng selection 1.000 ID để chia T/U. Nhãn E, C, U, T gốc và phiếu AI chunk 01–50 chuyển vào `outputs/02_Du_lieu_va_nhan/Nguon_V2/`. T2 và các lô đang chờ gán nằm trong `outputs/01_T2_va_cho_gan/T2_da_khoa/`.
Prompt người dùng đã cung cấp được lưu **local, không commit** tại
`docs/annotation/AI_LABEL_PROMPT.md`, SHA `528021b7b88bfacbc5eaba24b2e1bc4762248396ac2f7264acebddf558f77a17`. Manifest pin SHA;
prompt snapshot trong thư mục chunk. Không sửa prompt hoặc dùng nhãn gợi ý thay nhãn người dùng.

Kế hoạch năm batch A/B đã thay thế khi chuyển sang AI gán và người dùng duyệt. Các lượt pilot và CV trước đó nêu trong báo cáo.

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
- Báo cáo pilot lưu thống kê sau đối soát. Thư mục kết quả thử nghiệm đã được dọn.
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

### Mốc chia và rà nhãn V2

Split theo seed `20261115` tạo T gốc 202 quyết định trên 12 bài và U 798 câu trên 49 bài. E có 41 nhãn người, C có 159 quyết định, gồm 17 dòng được nối lại ID bằng văn bản khớp duy nhất, nhãn cũ và giá trị ID làm tròn. [Báo cáo gán nhãn V2](docs/annotation/BAO_CAO_GAN_NHAN_V2.md) ghi các mốc và phép thử.
