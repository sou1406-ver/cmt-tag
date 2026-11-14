# cmt-tag — Phân loại cảm xúc bình luận tiếng Việt

Bài tập lớn Xử lý dữ liệu văn bản, sử dụng **Python CLI** và bình luận phim
làm nguồn dữ liệu. Ba lớp sentiment: **POS / NEG / NEU**.

**Crawl → Lọc dữ liệu → Tiền xử lý tối thiểu → Kiểm tra chất lượng → Gán nhãn → Train → Đánh giá.**

## Hướng hiện tại

V2 chuyển sang **cảm xúc chung của toàn bình luận**, thay cho tiêu chí V1 chỉ
đánh giá thái độ đối với phim. Hiện đang thu thập và kiểm tra chất lượng text.
Quy tắc gán nhãn V2 cần chốt trước khi gán lại và huấn luyện.

- Nhãn người, nhãn AI, model và Gold V1 giữ làm lịch sử, **không tự chuyển thành nhãn V2**.
- Gold V1 đã được đánh giá một lần; không dùng lại để chọn preprocessing hoặc tune model.
- Pilot đang chuẩn bị cho hai người gán độc lập; chưa có sentiment Gold V2.
- Nhãn AI chỉ là đề xuất; kiểm tra chất lượng bằng mẫu ngẫu nhiên trước khi quyết định sử dụng.
- Không có API gán nhãn tự động trong workflow đang chạy. Không cần cài Transformer để crawl.

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

Chiến dịch V2 dùng lại batch CLI, chưa tự thu thập 10–15k câu:

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
thu thêm tên/ID tác giả. Link mơ hồ và phần chỉ còn dấu câu như `?` vào REVIEW;
chỉ tag/URL hoặc trắng vào EXCLUDE. Emoji-only không bị tự gán POS/NEG.
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
còn **425 nhãn sentiment người theo tiêu chí cũ**. Chưa có bộ nhãn V2 được duyệt.
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

Chỉ đọc `text_clean`, cảm xúc chung có thể hướng tới bất kỳ đối tượng nào.
**Guideline chưa được chốt**: đã nhận bản V3.1 ở local, nhưng người dùng giữ trạng
thái rà soát và đang yêu cầu đối chiếu SHA với bản gốc. Không chuyển READY hoặc
đổi guideline/manifest pilot lúc này. [Bổ sung PROPOSED cũ](docs/guidelines/SENTIMENT_GUIDELINE_V3_1_PROPOSED.md)
chỉ giữ để tham chiếu lịch sử; không tự coi là bản chính thức. Không thay V2.1 lịch sử.

```powershell
python -m src.annotation sentiment-pilot prepare --directory outputs/sentiment_pilot_v3_1
# Xuất Excel: Node bundled + @oai/artifact-tool, không cần API.
node scripts/export_sentiment_pilot.mjs outputs/sentiment_pilot_v3_1
# Sau khi hai người điền xong (không chạy trên file trống):
python -m src.annotation sentiment-pilot compare --directory outputs/sentiment_pilot_v3_1 --agreement-audit-count 20
# Excel đối soát cho người dùng, sau khi compare thành công:
node scripts/export_sentiment_pilot.mjs outputs/sentiment_pilot_v3_1/comparison --adjudication
# Sau khi người kiểm duyệt điền final_label / adjudication_note:
python -m src.annotation sentiment-pilot adjudicate --directory outputs/sentiment_pilot_v3_1 --decisions outputs/sentiment_pilot_v3_1/comparison/adjudication.xlsx --adjudicator user
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
Kappa suy biến trả null kèm lý do, không thay bằng 0/1. Chưa có nhãn thật thì chưa có kết quả.

**A/B là đúng hai annotator độc lập; người dùng là adjudicator**, được xem cả
nhãn/ghi chú A/B sau khi hai người gán xong, không phải người gán độc lập thứ ba.
Kappa luôn tính trên nhãn A/B gốc trước đối soát, không từ `final_label`.
`adjudication.local.csv` / Excel có đúng các cột `comment_id, text_clean, label_A,
label_B, note_A, note_B, final_label, adjudication_note`. Toàn bộ bất đồng được
đưa lên đầu và tô cam trong Excel; thêm mặc định tối đa 20 câu đồng thuận chọn
ngẫu nhiên bằng seed cố định để kiểm tra chất lượng (tô xanh). Có thể chỉnh số
câu đồng thuận qua `--agreement-audit-count`, không đổi mẫu pilot 200 câu.
`final_label` để trống ở cả hai nhóm. Chỉ nhập hai cột cuối; REVIEW cần note.
Importer từ chối sửa ID/text/nhãn hoặc note gốc A/B, thiếu/trùng dòng, nhãn cuối
trống/sai. Kết quả lưu riêng tại `comparison/adjudicated/`, có receipt/hash và
giữ nguyên A/B cùng Kappa. Các câu đồng thuận chưa được kiểm tra không tự được
điền nhãn cuối; không tự tạo Gold hoặc ghi canonical. Workbook chứa comment chỉ local.

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
- [Guideline V2.1 lịch sử của bài toán V1](docs/guidelines/MOVIE_SENTIMENT_V2_1.md) — không phải guideline cảm xúc chung mới.
