# Thu thập Facebook bằng Python CLI

## Phạm vi, audit và lựa chọn công nghệ

Đọc crawler JS, tiền xử lý legacy, importer/schema/pipeline/split, configs,
tests và README trước khi triển khai. Crawler JS cũ lấy text bằng selector rộng,
có thể lẫn UI, dedup prefix 50 ký tự và không giữ metadata. Không tái dùng thuật
toán đó. Giữ nguyên JS và preprocessing legacy để đối chiếu; không chạy chúng
trên corpus mới. Không đưa CSV legacy hoặc nguồn 29k vào crawl mới.

Playwright Python được chọn vì hỗ trợ locator, explicit waits và Chromium có
giao diện, dễ kiểm thử cùng adapter DOM trên HTML fixture. Tham khảo chính thức:
[locators](https://playwright.dev/python/docs/locators),
[persistent context](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context).
Không có web app/API/dashboard, API Facebook riêng, chặn request để lấy token,
mật khẩu tự động, proxy hay vượt CAPTCHA.

## Bắt đầu trên Windows

Tại thư mục gốc repository, dùng Python 3.10+:

```powershell
python -m venv .venv-crawler
.\.venv-crawler\Scripts\python.exe -m pip install -r requirements-crawler.txt
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.playwright-browsers"
.\.venv-crawler\Scripts\python.exe -m playwright install chromium
.\.venv-crawler\Scripts\python.exe -m src.crawler --help
```

Giữ biến `PLAYWRIGHT_BROWSERS_PATH` khi chạy trong terminal mới nếu đã cài
Chromium ở đường dẫn trên. Có thể dùng `--channel chrome` với Chrome đã cài
thay vì tải Chromium. Không dùng profile Chrome hằng ngày.

```powershell
.\.venv-crawler\Scripts\python.exe -m src.crawler crawl-post --url "https://www.facebook.com/PAGE/posts/POST_ID" --movie-id ma_phim
.\.venv-crawler\Scripts\python.exe -m src.crawler crawl-batch --input configs/post_urls.csv --source-dataset film_batch_01
```

Tự tạo `configs/post_urls.csv` từ `configs/post_urls.example.csv` và thay URL
ví dụ bằng bài thực tế được phép truy cập. Mỗi URL một dòng, có `movie_id`.
Crawler in run ID, mở Facebook bằng profile riêng, chờ bạn đăng nhập thủ công
rồi nhấn Enter tại terminal. Có thể tự chọn chế độ hiển thị comment phù hợp
trong Facebook; crawler không hứa mở được chế độ “tất cả bình luận”. Nếu gặp
checkpoint/CAPTCHA hoặc hạn chế truy cập, dừng; không tự vượt qua.

```powershell
# Ctrl+C để ngừng; dùng run ID đã in ra. Config/inputs của run cũ được dùng lại.
.\.venv-crawler\Scripts\python.exe -m src.crawler crawl-batch --resume fb_RUN_ID
.\.venv-crawler\Scripts\python.exe -m src.crawler validate --run fb_RUN_ID
.\.venv-crawler\Scripts\python.exe -m src.crawler export --run fb_RUN_ID --format csv
.\.venv-crawler\Scripts\python.exe scripts/prepare_data.py --config data/imports/fb_RUN_ID/import_config.json
```

`crawl-batch --resume` không cần CSV đầu vào. `crawl-post --resume` vẫn yêu cầu
hai tham số URL/movie của argparse nhưng dùng config lưu trong run; nên dùng
lệnh batch-resume thống nhất ở trên. Run tất cả bài success không resume/ghi đè;
partial/failed/blocked hoặc còn bài chưa xử lý được giữ resumable.
Các bài `success` được bỏ qua khi resume, bài partial/failed hoặc bị ngắt sẽ
được thử lại. Nếu kill cứng để lại `.browser.lock`, chỉ gỡ file lock riêng của
run sau khi xác minh không còn tiến trình crawler dùng run đó. Không xóa profile/raw.

## Tham số

Tất cả lệnh có `--help`; các giới hạn phải là số dương:

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--url`, `--movie-id` | Bắt buộc với crawl-post | Bài nguồn HTTPS và mã phim do bạn cung cấp |
| `--input` | Bắt buộc với batch mới | CSV UTF-8 hoặc UTF-8-SIG, cột movie_id/post_url |
| `--source-dataset` | Run ID | Provenance đợt thu thập, không phải tên phim suy đoán |
| `--data-root` | data | Thư mục local chứa runs/imports |
| `--profile` | data/browser_profile | Profile trình duyệt riêng; không commit/chia sẻ |
| `--channel` | chromium | chromium hoặc chrome |
| `--resume` | Không | ID run chưa hoàn tất; dùng lại input/settings đã lưu |
| `--max-posts` | 100 | Chỉ xử lý tối đa số bài này; phần còn lại báo posts_without_result |
| `--max-comments` | 5000 | Giới hạn observation lưu trên mỗi bài, kể cả khi resume |
| `--post-timeout` | 300 | Giây mỗi lần thử bài; login thủ công nằm ngoài giới hạn này |
| `--max-rounds` | 100 | Giới hạn vòng mở rộng/đọc/cuộn |
| `--max-actions` | 20 | Giới hạn click nút trong mỗi vòng |
| `--wait-ms` | 10000 | Timeout navigation/action; một thao tác đang chạy có thể kết thúc sau deadline bài |
| `--settle-ms` | 1500 | Explicit poll sau cuộn để chờ DOM thay đổi |
| `--idle-rounds` | 3 | Số vòng không thêm dữ liệu/click trước khi dừng |
| `--retries` | 2 | 0–5 lần thử lại exception tạm thời; không retry để né access barrier |
| `--run` | Bắt buộc | Run cần validate/export |
| `--format` | csv | CSV UTF-8-SIG, không cần pandas |
| `--output` | data/imports/RUN_ID | Thư mục export mới; từ chối ghi đè |

Thời gian batch bị chặn bởi số bài × số attempt × timeout/giới hạn thao tác;
không có vòng lặp vô hạn. User login có thể chờ tới khi nhấn Enter hoặc Ctrl+C.

## Schema, bảo toàn dữ liệu và chất lượng

```text
data/crawl_runs/<run_id>/
  raw_comments.jsonl     # append + flush/fsync, không chuẩn hóa text
  posts.jsonl            # lịch sử kết quả/attempt của từng bài
  errors.jsonl           # code/type và URL đã bỏ query tracking, không exception text
  checkpoint.json        # cập nhật atomic, resume dựng lại ID từ raw journal
  config.json            # input/settings bất biến
  crawl_report.json      # kết quả cuối, không sửa khi validate
data/imports/<run_id>/
  comments.csv
  import_config.json
  export_manifest.json
```

Các field raw: text_raw, comment_id, post_id, post_url, parent_comment_id,
movie_id, collected_at, comment_created_at, source_dataset, crawl_run_id,
record_type, extraction_status, internal_record_id; bổ sung comment_permalink
và possible_duplicate. Không lưu tác giả, profile URL hoặc toàn HTML trang.
Text được lấy từ node nội dung riêng: giữ emoji/alt ảnh, dấu câu, BR/xuống dòng,
phủ định, teencode; không hứa khôi phục nguyên văn trước khi Facebook render DOM.

ID chỉ đọc từ permalink thuộc bài nguồn; post ID chỉ từ URL có mẫu nhận dạng
posts/videos/reel/story_fbid/fbid/v. URL dạng share chưa resolve được ID để null.
Thời gian đăng chỉ nhận `time[datetime]` ISO có timezone; thời gian tương đối
để null. Reply lồng nhau có parent ID nếu permalink cha xác minh được, không
biến internal UUID thành ID Facebook. collected_at luôn là thời điểm thu thập UTC.

Dedup raw trong cùng run bằng ID Facebook hoặc permalink thật. Nội dung giống
nhau có ID khác vẫn giữ. Thiếu ID: giữ theo observation DOM; cùng node không
ghi lặp mỗi vòng nhưng node mới/resume có thể tạo thêm observation, gắn
possible_duplicate để review. Không tự xóa theo text. Chưa có kho dedup toàn cục
qua nhiều run: mỗi run giữ provenance riêng; Phase B gom ID/post/text xuyên nguồn.

Comment bị cắt được thử click mở rộng; bản chưa mở được có trạng thái truncated.
Truncated tạm được đợi đến cuối bài trước khi ghi để ưu tiên bản đầy đủ.
Nếu Ctrl+C trước cuối bài, comment đầy đủ đã fsync vẫn còn; phần truncated đang
đợi sẽ được đọc lại khi resume. Truncated đã ghi không bị sửa thành bản khác
trong run đó; muốn đọc lại bản đầy đủ, tạo run mới. Khi write bị ngắt giữa JSON,
resume giữ tail chưa commit trong file `.tail_<id>` trước khi cắt tail để tiếp tục;
mọi dòng đã commit nguyên vẹn. Dòng malformed kết thúc bằng newline không bị tự sửa.
Raw vẫn flush/fsync từng dòng; checkpoint chỉ ghi mỗi 25 comment, tại kết thúc
bài hoặc khi dừng/finish. Resume dựng lại ID và Counter từng bài từ raw, không
tin số dòng checkpoint có thể chậm. Giữ raw fsync là lựa chọn bảo toàn dữ liệu,
không đánh đổi thêm comment đã xác nhận để lấy throughput; giảm checkpoint
giúp bớt atomic replace/fsync phụ mà không giảm durability journal.

Validate báo từng field metadata, số comment/reply, truncated, duplicate ID,
nghi trùng chưa xác nhận, lỗi parse, trạng thái bài, phân phối bài/phim và mẫu
ngẫu nhiên seed 42 tối đa 10 comment để đối chiếu thủ công. Parent ID thường
không áp dụng cho comment gốc nên tỷ lệ đó phải được đọc cùng record_types.
`success` chỉ nghĩa DOM được nhận dạng đã hết thay đổi trong budget; không
chứng minh thu đủ 100%. Không có DOM phù hợp là partial, không coi là zero comment
đã được xác nhận. Mọi báo cáo có cảnh báo hạn chế metadata/coverage.

Exporter không sửa raw. Chỉ observation complete đi vào CSV, số truncated bị
giữ lại raw được báo trong export_manifest. Raw checksum liên kết ngược tới run.
Config import dùng namespace `facebook`, source_dataset của run và không khai
báo nhãn. Metadata phụ vẫn ở raw/CSV; schema Phase B giữ metadata đang hỗ trợ
và provenance snapshot. Phase B giữ các dòng text trùng nhưng có thể đánh dấu
non-independent, không tự đưa vào gold/train. Không thay schema/thuật toán Phase B.

## Kiểm thử và smoke test thủ công

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD\.playwright-browsers"
.\.venv-crawler\Scripts\python.exe -m unittest discover -s tests -v
```

DOM tests thực sự dùng Playwright Chromium trên HTML fixture, route local không
gửi request Facebook. Nếu thiếu package, 4 DOM tests skip có lý do; nếu package
có mà browser thiếu thì test lỗi để chỉ ra môi trường chưa đủ. Các data tests
không cần tài khoản. Test pandas legacy có thể skip trong venv tối thiểu; để
chạy đủ như môi trường audit cần pandas (không phải dependency crawler).

Chưa có smoke test Facebook thật được xác nhận. Dùng bài bạn có quyền xem,
chạy giới hạn `--max-comments 20 --max-rounds 5 --post-timeout 60`, tự đăng nhập,
đối chiếu mẫu trong `crawl_report.json` với trang nguồn: body/emoji/xuống dòng,
comment/reply, parent ID và truncated; kiểm tra không có nội dung bài/tên tác giả.
Validate rồi export/import vào thư mục thử mới, chưa sử dụng cho annotation/gold.
Nếu DOM khác fixture và không nhận dạng được, báo partial/parse errors; cần
điều chỉnh adapter `src/crawler/dom.js` từ DOM đã kiểm tra. Không mở rộng selector
thành toàn bộ `innerText` của article để làm test pass.

Giới hạn: chỉ selector vi/en và body xác định hẹp, chưa chứng minh phù hợp mọi
DOM Facebook; comment không phải role article hoặc nhiều body ứng viên sẽ không
được tự nhận. Bài ở feed khác, virtualized comments, nút có nhãn khác, chế độ
lọc comment và quyền truy cập có thể làm thiếu dữ liệu. Link share/permalink
khác dạng và thời gian tương đối có thể không có metadata. Hãy kiểm tra mẫu và
report trước khi coi run dùng được cho nghiên cứu.
