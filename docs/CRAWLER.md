# Facebook crawler — Selenium CLI

Crawl comment/reply có thể truy xuất hợp lệ, giữ `comment_id`, `post_id`,
`parent_comment_id`, `movie_id`, nguồn và provenance. Không thu thêm tên/ID tác giả.
Account mention chỉ xóa khi DOM nhận dạng được; không đoán tên từ chữ hoa.
Emoji/emoticon giữ trong text. Không có cam kết lấy đủ tổng bình luận Facebook.

Run mới dùng `dom_text_v3`: `text_raw` giữ chữ gốc trong vùng comment,
`text_without_mentions` chỉ bỏ account link, còn `text_clean` bỏ thêm URL/link
chia sẻ. Không đọc toàn bộ article để lấy text. Link profile, people và
`/groups/<id hoặc slug>/user/<id>/` là bằng chứng mention; tên viết thuần giữ nguyên.
Chỉ bỏ anchor có nhãn URL hoặc cấu trúc media-card của link chia sẻ. Địa chỉ
đích ngoài Facebook/redirect/post không tự chứng minh chữ trong anchor là preview.
Anchor ngôn ngữ chưa rõ giữ chữ và gắn `REVIEW`; URL hiện trong chữ vẫn bỏ.
Chữ ngoài anchor và hashtag giữ nguyên.
`clean_status` là đề xuất kỹ thuật: có chữ Unicode → KEEP; rỗng hoặc chỉ dấu câu
→ EXCLUDE; chỉ emoji/emoticon/điểm số → REVIEW. Link mơ hồ vẫn giữ REVIEW.
Có media không tự gây REVIEW khi còn chữ; media-only không text → EXCLUDE.
`non_text_media_count` vẫn giữ; không OCR hoặc đọc caption tự sinh. KEEP là trạng
thái kỹ thuật, không khẳng định câu độc lập với ảnh hoặc có sentiment rõ ràng.
Người gán chọn REVIEW nếu cần ảnh mới hiểu. Metadata cũng nhận lý do tường minh
`media_context_required` khi có media; crawler không tự suy diễn bằng từ khóa.
Journal cũ dùng lý do `non_text_media` vẫn được đọc nguyên trạng.
`url_count` và `clean_review_reasons` ghi số lượng/lý do, không tự gán sentiment.
Chỉ dấu câu như `?`, `...`, `!!!` → EXCLUDE; `😂`, `:))`, `10/10` → REVIEW.
`clean_evidence` lưu loại/rule và `raw_start`/`raw_end` của từng đoạn bị bỏ,
theo đơn vị UTF-16 của JavaScript, không lưu href hay danh tính tài khoản mới.
URL text được nhận diện trên chuỗi hiển thị nối từ các node, kể cả nhiều span;
offset giữ liên hệ với raw. Chuỗi giống URL nhưng không phân tích được giữ REVIEW.
Run cũ không có evidence vẫn đọc được; không bổ sung bằng chứng giả cho journal cũ.
View sạch dành cho task gán nhãn/huấn luyện mới sau kiểm tra; import config cũ vẫn
giữ `text_raw`, không tự đổi dataset hoặc protocol. Journal v2 vẫn đọc được và
export hỗn hợp để trống view mới cho dòng cũ; không suy diễn text sạch từ raw cũ.

## Setup và đăng nhập Brave

```powershell
python -m pip install -r requirements/crawler.txt
python -m src.crawler login --channel brave --profile data/browser_profile_brave_manual
```

Đăng nhập/xác minh thủ công trong cửa sổ mở ra. Đóng cửa sổ dùng profile đó
trước khi crawl; không dùng chung profile với một tiến trình Brave khác.
Không chia sẻ profile/cookies lên Git. Crawler không vượt CAPTCHA hay authentication.

## Dán link tương tác

```powershell
python -m src.crawler interactive --channel brave --profile data/browser_profile_brave_manual --max-comments 200 --max-rounds 30 --post-timeout 180
```

Làm theo prompt đăng nhập rồi Enter. Nhập mã phim, ví dụ `mua_do` (không phải URL),
sau đó dán link bài Facebook nguyên dòng. URL chứa `&`/`?` không đi qua shell.
`movie ma_moi` đổi phim; Enter rỗng kết thúc. Link invalid được hỏi lại;
bài đã success trong run được bỏ qua. Ctrl+C checkpoint và dừng, journal không mất.

```powershell
python -m src.crawler interactive --channel brave --profile data/browser_profile_brave_manual --resume RUN_ID
```

Các link cùng phiên dùng một run. Resume dùng config/input đã lưu, không tự
thay giới hạn hay ghi đè journal. Run đã hoàn thành không được resume như run đang dở.

## Batch và giới hạn

CSV UTF-8 có `movie_id,post_url`; một dòng cho mỗi bài:

```powershell
python -m src.crawler crawl-batch --channel brave --profile data/browser_profile_brave_manual --input configs/post_urls.example.csv --max-comments 200 --max-rounds 30 --post-timeout 180
```

Thay URL fixture bằng bài thật trong một input local mới. `crawl-post --url URL
--movie-id MA_PHIM` dùng chung collector. `--max-comments all` bỏ giới hạn số dòng,
nhưng timeout, rounds, idle và action budgets vẫn áp dụng. Timeout không có nghĩa
đã lấy hết. Không tuyên bố lấy mẫu ngẫu nhiên: thứ tự phụ thuộc DOM/thread hiển thị.

## Kết quả, validate và export

Journal/checkpoint/diagnostics ở `data/crawl_runs/RUN_ID/`:

```powershell
python -m src.crawler validate --run RUN_ID
python -m src.crawler export --run RUN_ID
```

Export ở `data/imports/RUN_ID/`, gồm text và metadata/provenance, import config,
manifest. Kiểm `total_records`, `parse_errors`, status/reason, metadata completeness
và warnings. Output export đã tồn tại không được ghi đè. Export partial cần
`--allow-partial`, giữ rõ coverage warnings. `success/visible_dom_exhausted` chỉ
nói DOM không còn dữ liệu tải được theo collector; không xác minh coverage tổng.
Import prepared records dùng chung build CLI:

```powershell
python scripts/build_master_dataset.py --config data/imports/RUN_ID/import_config.json --output-root NEW_DATA_ROOT
```

Không tự thêm dữ liệu crawl vào filtered candidate/test reservations đã khóa.

## Chiến dịch V2 — chuẩn bị công cụ, chưa chạy thu thập lớn

CSV local `data/posts_v2.csv`: hai cột bắt buộc `movie_id,post_url`; nên bổ sung
`source_name,source_type,max_comments` như `configs/post_urls.example.csv`.
File example chỉ có URL giả, phải thay bằng danh sách nguồn đã được chọn.
`source_type` nhận `page/group`; group suy ra được từ URL, còn page phải khai báo.
Tên nguồn lấy từ CSV, không lấy tên tác giả hoặc đoán từ nội dung comment.

```powershell
python -m src.crawler crawl-batch --campaign-v2 --input data/posts_v2.csv --channel brave --profile data/browser_profile_brave_manual --max-comments 300 --post-delay 5
python -m src.crawler crawl-batch --resume RUN_ID --channel brave --profile data/browser_profile_brave_manual
python -m src.crawler validate --run RUN_ID
python -m src.crawler export --run RUN_ID
python -m src.crawler export --run RUN_ID --format xlsx
```

Mặc định run mới là 300 comment/bài; cột `max_comments` ghi đè theo bài.
V2 chỉ chấp nhận 1–500, không nhận `all`; run cũ giữ cấu hình đã lưu và không
đổi sang V2 qua resume. Mặc định nghỉ 5 giây giữa bài/retry. Bị chặn truy cập
thì dừng batch; không tự tìm cách vượt bảo vệ. Ctrl+C ghi reason `interrupted`.
`comment_limit` trong V2 là hoàn tất mục tiêu giới hạn, `visible_dom_exhausted`
là hết phần DOM tải được. Timeout/round limit/truncated vẫn được báo riêng.
Mọi trạng thái đều `coverage_verified=false`.

Raw fsync sau mỗi dòng; checkpoint và `crawl_report.json` cập nhật sau mỗi bài.
`per_post_quality` có số comment/reply, clean_status, thiếu metadata/tỷ lệ thiếu,
trùng ID/bản ghi bỏ qua, lỗi DOM/raw và truncated. Chỉ dùng journal/checkpoint cũ.
V2 đọc ID từ toàn bộ journal cùng `data-root` để chống trùng giữa run; không
xóa/sửa journal trước. `.campaign-v2.lock` dùng lại OS lock để ngăn hai chiến dịch
V2 chạy cùng lúc. Không chạy một crawler legacy song song với V2 trên cùng root.
Không có ID thì giữ `possible_duplicate`, không đoán ID hoặc xóa chỉ vì text giống.

`comment_created_at` chỉ có khi DOM cho ISO datetime có timezone. `reaction_count`
chỉ nhận nhãn số tuyệt đối rõ ràng của đúng comment; số viết tắt/không nhất quán
để null. `displayed_count` ở journal bài/report và Excel chỉ nhận tổng dạng số
rõ ràng ngoài vùng comment. Không lấy reaction làm tổng comment. Không bảo đảm DOM
Facebook luôn cung cấp các trường này. `crawl_run_id` hiện có là run_id của JSONL/CSV;
Excel hiển thị alias `run_id`. Nguồn/thời gian/reaction không đọc được là null.

CSV export vẫn gồm các quan sát complete để import; Excel là **một file**
`data/imports/RUN_ID/review.xlsx`, chứa cả truncated để kiểm tra, freeze header,
wrap text và AutoFilter theo phim/bài/trạng thái. Không tự tính lại status cho raw
cũ. Excel không phải nguồn nhãn/train; text quá giới hạn ô Excel sẽ báo lỗi,
không cắt nội dung hoặc sửa raw. Không thêm dependency để export Excel.

Kế hoạch đề xuất: 60 bài × 200–250 câu ≈ 12–15k tối đa theo cấu hình, ít nhất
20 phim/chủ đề, khoảng 3 bài/phim từ nhiều page/group và loại thảo luận/thời điểm.
Phương án 40 bài × 300 hoặc 80 bài × 150 đều có ngân sách 12k. Đây là ngân sách,
không cam kết thu đủ KEEP. Xem chất lượng nguồn qua mẫu trước; không bù số lượng
bằng nguồn kém, không để bài viral chi phối. Chọn danh sách trước khi chạy;
giữ riêng các bài dành cho test, không dùng chúng để phát triển preprocessing.

## Khi bị kẹt

- `SessionNotCreatedException`: kiểm đúng browser/driver và profile riêng; đóng
  cửa sổ đang dùng cùng profile. Có thể chỉ định `--browser-path`/`--driver-path`.
- `FileExistsError`/`.browser.lock`: kiểm tiến trình dùng run/profile; không xóa
  lock khi run còn sống. Run hoàn thành/export tồn tại phải dùng run/output mới.
  Không xóa journal hoặc profile để thử sửa lỗi.
- `post_scope_not_found`, `no_recognized_comments`, `partial`: kiểm bài có truy
  cập được, đăng nhập đúng và comment đã hiển thị; đọc diagnostics trước khi sửa DOM.
- Có thể attach browser mở thủ công bằng `--cdp-url http://127.0.0.1:9222` với
  profile riêng và driver tương thích; crawler không đóng browser attach khi thoát.

Test dùng fixture HTML, fake collector và profile tạm, không đăng nhập Facebook.
Tests cần Selenium sẽ skip rõ ràng nếu dependency không có. Lịch sử patch/test
counts cũ nằm tại tag `before-cleanup-20261112`, không phải hướng dẫn hiện hành.
