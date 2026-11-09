# Thu thập Facebook bằng Python CLI

## Phạm vi, audit và lựa chọn công nghệ

Đọc crawler JS, tiền xử lý legacy, importer/schema/pipeline/split, configs,
tests và README trước khi triển khai. Crawler JS cũ lấy text bằng selector rộng,
có thể lẫn UI, dedup prefix 50 ký tự và không giữ metadata. Không tái dùng thuật
toán đó. Giữ nguyên JS và preprocessing legacy để đối chiếu; không chạy chúng
trên corpus mới. Không đưa CSV legacy hoặc nguồn 29k vào crawl mới.

Backend hiện tại là **Selenium Python + ChromeDriver**, thay cho Playwright
theo yêu cầu người dùng. Giữ nguyên CLI tương tác, Store, run_posts, parser DOM,
raw/resume/export. Dùng WebDriverWait để chờ DOM và JavaScript DOM adapter hiện
có để chỉ lấy body comment. Tham khảo chính thức:
[Selenium Manager](https://www.selenium.dev/documentation/selenium_manager/),
[Chrome options/debugger_address](https://www.selenium.dev/selenium/docs/api/py/selenium_webdriver_chromium/selenium.webdriver.chromium.options.html).
Không có web app/API/dashboard, API Facebook riêng, chặn request để lấy token,
mật khẩu tự động, proxy hay vượt CAPTCHA.

## Bắt đầu trên Windows

### Đăng nhập bình thường trước, Selenium dùng lại profile

```powershell
.\.venv-crawler\Scripts\python.exe -m src.crawler login --channel brave --profile data/browser_profile_brave_manual
```

Đóng cửa sổ crawler cũ nếu nó đang dùng profile này. Lệnh login chỉ chạy Brave
thường, không Selenium, không remote debugging, không đọc cookie/mật khẩu. Bạn
tự đăng nhập và hoàn tất xác thực Facebook, sau đó **đóng cửa sổ Brave này** để
nhả profile trước khi chạy:

```powershell
.\.venv-crawler\Scripts\python.exe -m src.crawler interactive --channel brave --profile data/browser_profile_brave_manual --max-comments 30 --max-rounds 5 --post-timeout 60
```

Selenium mở lại đúng profile đã đăng nhập; tại lời nhắc đăng nhập trong terminal,
chỉ nhấn Enter khi Facebook đã dùng được. Các lần sau vẫn giữ profile này. Không
cần sao chép session từ Brave cá nhân; không tự xử lý 2FA/CAPTCHA.

Parser hiện nhận /groups/.../permalink/ và /groups/.../posts/ cùng ID; DOM adapter
khoanh dialog/article theo bài, hỗ trợ comment aria-label không có role article
và body dir=auto không phụ thuộc style text-align. Nó thử chọn và xác nhận
“Tất cả bình luận”, click thêm bình luận/phản hồi trong đúng vùng, cuộn dialog
thay vì feed phía sau. Khi không xác minh được scope/body, vẫn báo partial hoặc
parse error, không lấy toàn trang để thay thế. Chưa đủ để khẳng định tương thích
mọi DOM Facebook thật; sort unavailable được ghi trong state_trace.

Tham khảo cách tổ chức login/scope của
[repo PTIT tại commit 020fd25](https://github.com/namPh06/Toxic_Detection_PTIT_Student_Comments/tree/020fd25b2c3fbde81c487711060ac87d0d48b793).
Không đưa web app, nhãn toxic, dữ liệu, hash tác giả hoặc cơ chế sửa raw của repo
đó vào cmt-tag. ID thiếu vẫn null, text không bị clean/collapse whitespace trong
raw. Các dòng cũ có post_id null vẫn validate được, không sửa raw để bổ sung ID.

Kiểm chứng patch login/DOM: **90 tests PASS, không skip** bằng Selenium/Brave
trên fixture local. Test mới phủ URL nhóm, aria-label không role, body không
style text-align, bài nằm trong dialog, loại author/post/feed khác, xác nhận
filter, mở nội dung dài, parent reply và bảo toàn raw cũ thiếu post_id.

### Dùng Brave mở thủ công, giữ phiên đăng nhập

Crawler không thể tự gắn vào Brave đang mở bình thường khi chưa bật remote
debugging. Mở một cửa sổ Brave thủ công với profile dành cho thu thập:

```powershell
& "$env:ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe" --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 "--user-data-dir=$PWD\data\brave_manual_profile" "https://www.facebook.com/"
```

Đăng nhập và hoàn tất 2FA thủ công trong cửa sổ này trước. Profile được giữ
cho các lần sau, không phải ẩn danh, nhưng không có sẵn cookie từ profile Brave
hằng ngày. Không copy cookie/profile đang dùng. Nếu vẫn kẹt trang 2FA, cần xử
lý đăng nhập hợp lệ trên Facebook; CDP không phải cách vượt xác thực hay cam
kết sửa trang trắng. Cửa sổ crawler cũ có thể đóng bằng tay nếu không dùng nữa.

Trong terminal ở repo (có thể mở terminal thứ hai), chạy:

```powershell
.\.venv-crawler\Scripts\python.exe -m src.crawler interactive --cdp-url http://127.0.0.1:9222 --max-comments 30 --max-rounds 5 --post-timeout 60
```

Script dùng default context và tab Facebook đầu tiên, không điều hướng tab
đã mở về trang chủ; nếu chưa có thì tạo tab Facebook. Sau lời nhắc, nhấn Enter
để bắt đầu phiên. Kết thúc/Ctrl+C chỉ ngắt kết nối, không tự đóng browser/tab.
Trong lúc crawl tab Facebook đó sẽ được điều hướng đến link bạn nhập; không
dùng tab ấy để làm việc khác đồng thời. --cdp-url bỏ qua --channel và không đi
kèm --profile/--browser-path. Chỉ chấp nhận HTTP localhost/127.0.0.1/::1 có port,
không endpoint ngoài máy, token hay credential trong URL. Đóng browser thủ công
khi xong; không mở cổng điều khiển ra mạng.

Profile mặc định của Chrome mới không hỗ trợ remote debugging như trước;
dùng user-data-dir riêng cũng tránh tranh chấp profile Brave đang mở. Xem
[remote debugging changes](https://developer.chrome.com/blog/remote-debugging-port),
[Selenium debugger_address](https://www.selenium.dev/selenium/docs/api/py/selenium_webdriver_chromium/selenium.webdriver.chromium.options.html).
Không bảo đảm mọi phiên bản Brave có hành vi giống Chrome; CDP cần browser
hỗ trợ. Thay đổi CDP kiểm thử 80 tests pass, gồm test giả không đóng browser/
không thay tab và giới hạn endpoint local. Smoke test Brave thật với profile
tạm/HTML local xác nhận tab còn mở sau ngắt kết nối; chưa xác nhận live login
Facebook. Không dùng profile/tài khoản cá nhân trong smoke test.

### Phiên tương tác: dán nhiều link, cùng một run

```powershell
.\.venv-crawler\Scripts\python.exe -m src.crawler interactive --channel brave --max-comments 30 --max-rounds 5 --post-timeout 60
```

Không cần đặt URL trong dòng lệnh. Script mở Brave riêng cho crawler để bạn
tự đăng nhập; nhấn Enter ở terminal. Nhập mã phim một lần, sau đó dán nguyên
link tại prompt `Dán link (Enter để kết thúc):`. URL có `&`/`?` được đọc qua
input(), không qua shell. Khoảng trắng/dấu nháy ngoài link được bỏ trước validate.
Link sai báo lý do và hỏi lại. Gõ `movie phim_b` để đổi mã cho những bài mới;
bài đã có trong run giữ movie_id đã ghi. Bài đã success được bỏ qua.

Sau mỗi bài in status/reason, số comment mới và tổng run. Enter rỗng kết thúc,
ghi báo cáo, in run ID, thư mục và hai lệnh validate/export để copy. Giới hạn
max_comments/rounds/time vẫn tính từng bài như crawl-post, max_posts cho cả run.

```powershell
.\.venv-crawler\Scripts\python.exe -m src.crawler interactive --channel brave --resume fb_RUN_ID
```

Ctrl+C checkpoint và thoát; resume nhớ movie gần nhất (Enter để giữ tại prompt
mã phim). Có thể resume cả run crawl-post/batch trước đó để bổ sung link, kể cả
run đã success: đây là thao tác mở lại được yêu cầu rõ bằng interactive, không
sửa/xóa raw đã ghi. Chế độ thường vẫn từ chối mở lại run complete như trước.
Inputs thêm được fsync trong interactive_inputs.jsonl, chế độ/mã phim lưu riêng;
config.json ban đầu giữ nguyên. Validator/exporter dựng cấu hình hiệu lực từ
config ban đầu + input journal, nên tất cả link export trong cùng một run.
Browser profile vẫn riêng, không đọc hoặc nhập profile Brave cá nhân đang mở.

Brave tự dò tại Program Files/Program Files (x86)/LocalAppData. Cài nơi khác:

```powershell
.\.venv-crawler\Scripts\python.exe -m src.crawler interactive --channel brave --browser-path "D:\Apps\Brave\Application\brave.exe"
```

Profile mặc định Brave là data/browser_profile_brave; Chrome vẫn dùng
data/browser_profile. Brave dùng ChromeOptions.binary_location; Selenium Manager
tìm ChromeDriver phù hợp. --channel chromium giữ làm alias auto-discovery Chrome
để tương thích lệnh cũ; nếu dùng Chromium riêng, khai báo --browser-path.
Đổi trình duyệt không tự sửa lỗi nhận dạng DOM/no_recognized_comments.

Kiểm chứng thay đổi này: `python -m unittest discover -s tests` có 77 tests
PASS, không skip. Tests interactive inject reader/collector giả, không mở browser;
bao phủ URL có query `&`/`?`, link sai/trùng, đổi phim, Enter, Ctrl+C và resume/
export cùng run. Smoke Brave chỉ mở HTML local bằng profile tạm, không truy cập
Facebook hoặc profile cá nhân. Không sửa annotation/baseline/data hoặc artifacts Phase B.

Tại thư mục gốc repository, dùng Python 3.10+:

```powershell
python -m venv .venv-crawler
.\.venv-crawler\Scripts\python.exe -m pip install -r requirements-crawler.txt
.\.venv-crawler\Scripts\python.exe -m src.crawler --help
```

Không cần cài Playwright hoặc đặt PLAYWRIGHT_BROWSERS_PATH nữa. Lần đầu Selenium
Manager có thể cần mạng để lấy ChromeDriver, cache ở data/selenium_cache (hoặc
SE_CACHE_PATH nếu bạn đã đặt). Có thể dùng --driver-path đường dẫn chromedriver.exe
phù hợp major version Chromium bên trong Brave/Chrome nếu máy không tải được.
Ở chế độ --cdp-url, đọc phiên bản từ endpoint local và chỉ tìm driver cùng major,
không cố tải browser Chrome có patch-version giống Brave. Browser bạn tự mở
được giữ nguyên khi crawler ngắt kết nối.
Không dùng profile Chrome/Brave hằng ngày cho chế độ browser do script mở.

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

`crawl-batch --resume` không cần CSV đầu vào. `crawl-post` hỏi URL/movie khi thiếu
ở run mới; resume không hỏi lại vì dùng config đã lưu. Run thường tất cả bài
success không resume/ghi đè (interactive có cơ chế mở lại tường minh như trên);
partial/failed/blocked hoặc còn bài chưa xử lý được giữ resumable.
Các bài `success` được bỏ qua khi resume, bài partial/failed hoặc bị ngắt sẽ
được thử lại. Khóa run mới dùng OS lock: tự nhả khi tiến trình thoát/VS Code bị
đóng; file .browser.lock còn lại không có nghĩa run đang bị chiếm. Không tự xóa
file khóa kiểu mới vì có thể ảnh hưởng phiên khác. LegacyRunLockError chỉ file
khóa rỗng của bản cũ: chỉ gỡ đúng file đó sau khi xác minh crawler cũ không còn
chạy. RunBusyError là phiên khác vẫn giữ khóa. Không xóa profile/raw để sửa lock.

## Tham số

Tất cả lệnh có `--help`; các giới hạn phải là số dương:

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--url`, `--movie-id` | Hỏi khi thiếu | crawl-post hỏi link/mã; interactive chỉ hỏi mã một lần, URL luôn dán tại prompt |
| `--input` | Bắt buộc với batch mới | CSV UTF-8 hoặc UTF-8-SIG, cột movie_id/post_url |
| `--source-dataset` | Run ID | Provenance đợt thu thập, không phải tên phim suy đoán |
| `--data-root` | data | Thư mục local chứa runs/imports |
| `--profile` | data/browser_profile | Profile trình duyệt riêng; không commit/chia sẻ |
| `--channel` | chromium | chromium, chrome hoặc brave |
| `--browser-path` | Tự dò | Đường dẫn browser executable nếu cài nơi khác |
| `--driver-path` | Selenium Manager | ChromeDriver phù hợp, tùy chọn khi cài sẵn/offline |
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

Chuyển Selenium: **83 tests PASS, không skip**, với Brave 157.0.8103.39 và
ChromeDriver 157.0.8103.38 trên fixture local. Smoke riêng xác minh attach/detach
giữ Brave và tab do người dùng mở; không gọi Facebook hay đọc profile cá nhân.
Các con số 77/80 ở phần mô tả thay đổi trước là mốc kiểm thử lịch sử.

```powershell
.\.venv-crawler\Scripts\python.exe -m unittest discover -s tests -v
```

DOM tests thực sự dùng Selenium/ChromeDriver trên HTML fixture qua data URL, không
gửi request Facebook. Có thể đặt CRAWLER_TEST_BROWSER tới Brave/Chrome executable
và CRAWLER_TEST_DRIVER tới ChromeDriver local để tránh auto-download trong test.
Nếu thiếu Selenium thì DOM/browser lifecycle tests skip có lý do; nếu package
có mà browser/driver thiếu thì test lỗi để chỉ ra môi trường chưa đủ. Các data tests
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
