# Facebook crawler — Selenium CLI

Crawl comment/reply có thể truy xuất hợp lệ, giữ `comment_id`, `post_id`,
`parent_comment_id`, `movie_id`, nguồn và provenance. Không thu thêm tên/ID tác giả.
Account mention chỉ xóa khi DOM nhận dạng được; không đoán tên từ chữ hoa.
Emoji/emoticon giữ trong text. Không có cam kết lấy đủ tổng bình luận Facebook.

Run mới dùng `dom_text_v3`: `text_raw` giữ chữ gốc trong vùng comment,
`text_without_mentions` chỉ bỏ account link, còn `text_clean` bỏ thêm URL/link
chia sẻ. Không đọc toàn bộ article để lấy text. Link profile, people và
`/groups/<id hoặc slug>/user/<id>/` là bằng chứng mention; tên viết thuần giữ nguyên.
Link ngoài Facebook/redirect/link bài chia sẻ bỏ phần anchor; chữ ngoài anchor
vẫn giữ. Hashtag giữ; link không xác định giữ text và gắn `REVIEW`.
`clean_status` là đề xuất kỹ thuật: `KEEP`, `EXCLUDE` khi chỉ còn trắng/tag/URL,
`REVIEW` khi link mơ hồ hoặc có media không chuyển được thành chữ. Emoji-only
được giữ, không tự gán sentiment. `url_count` và `clean_review_reasons` ghi lý do.
Chỉ còn dấu câu (ví dụ `?`) cũng là `REVIEW`; không áp dụng cho emoji/emoticon.
`clean_evidence` lưu loại/rule và `raw_start`/`raw_end` của từng đoạn bị bỏ,
theo đơn vị UTF-16 của JavaScript, không lưu href hay danh tính tài khoản mới.
URL bị chia cắt qua nhiều text node mà không thể xóa chắc chắn được giữ để review.
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
