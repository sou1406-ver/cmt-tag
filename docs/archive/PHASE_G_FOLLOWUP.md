# Phase G follow-up — exposure audit, text_view, new-post intake

Ngày 11/11/2026. Kế thừa `43795f3`. Master, 400 quyết định người gán,
guideline, split và các artifact E/E.1/E.2/G đã khóa giữ nguyên.

## File người dùng và 8 bài cũ

File mới thực tế là `G:/dlvb/cmt-tag/test_posts.csv`, không phải workbook
XLSX. Có 25 dòng P001–P025 và movie slot, nhưng movie ID, URL/post ID,
xác nhận lựa chọn và bằng chứng đều trống. Không sửa nội dung file.
Preflight: **BLOCKED 25/25**, READY 0; chưa gọi crawler hoặc browser.
`validation.csv` liệt kê lỗi theo số dòng nguồn. File input được gitignore
để tránh đưa URL/bằng chứng nguồn tương lai lên public repo.

Đã rà **đủ 8 post**, kiểm 584 file metadata trong inventory đã khóa,
exposure ledger và lịch sử pool/task. Không dùng label/score/text comment để
quyết định nguồn. Mỗi reference có tên file, checksum, JSON pointer hoặc vị
trí dòng, loại provenance và số lần xuất hiện; không xuất nội dung bình luận.

| Post ID | Movie ID theo nguồn | Bản ghi master | Kết luận |
| --- | --- | ---: | --- |
| 1299920137281261 | dem_toi_ruc_ro | 18 | Chưa xác minh unused |
| 1717805608826043 | nu_hon_bac_ty | 40 | Chưa xác minh unused |
| 1723699424903328 | nu_hon_bac_ty | 40 | Chưa xác minh unused |
| 2249677925212460 | black_adam | 40 | Chưa xác minh unused |
| 2607603242753258 | exhuma | 40 | Chưa xác minh unused |
| 2883108581869388 | nha_gia_tien | 40 | Chưa xác minh unused |
| 3086828458164065 | tu_chien_tren_khong | 40 | Chưa xác minh unused |
| 3480492918797615 | trai_buon_nguoi | 40 | Chưa xác minh unused |

Không tìm thấy positive attestation xác nhận chưa dùng cho guideline hoặc
chọn mô hình. Không thấy post trong các pool đã kiểm tra cũng **không chứng
minh unused**. Cả 8 giữ `test_eligible=false`, `confirmed_unused=false`;
không đưa vào test pool hoặc tự sửa ledger cũ. Không có evidence file không
đọc được trong lần audit này. Overlay mới không tạo unused attestation nào.

Đầu ra local bất biến:

- `outputs/phase_g/exposure_audit/post_audit.json`: bằng chứng từng bài.
- `post_audit.csv`, `exposure_overlay.json`, `manifest.json` cùng thư mục.
- `outputs/phase_g/test_posts_preflight_20261111/validation.csv`, `rows.json`,
  `manifest.json`: kiểm tra đúng file người dùng.

Có thể chạy audit lại bằng `scripts/audit_test_exposure.py --output <new_dir>`.
Phạm vi là các nguồn thực sự có trong sealed inventory; không chứng nhận
những thao tác của con người hoặc máy khác không có log.

## Schema annotation chính xác

File mù mới chỉ có:

```text
id,text_view,status,label,review_reason,reason
```

`text_view` dùng trường đã xóa mention có cấu trúc theo `dom_text_v2` khi có;
nếu nguồn không có view này thì giữ nội dung như raw. Master vẫn giữ nguyên
`text_raw`, các variant và chính sách mention riêng. Không đổi nhãn hoặc sửa
text nguồn để thích nghi với header mới.

Đồng bộ `BLIND_FIELDS`, CSV/JSON task, builder Excel, validator và importer.
Importer yêu cầu đúng `text_view` và so nguyên văn theo ID; không chấp nhận
file ghi `text_raw` nhưng chứa view đã làm sạch. Shared annotation reader chỉ
thêm tham số `text_field`; mặc định cũ vẫn là `text_raw` cho development.
Không tự đổi các workbook/snapshot đã khóa. Phải tạo task mới khi đủ nguồn.

## Nhập test_posts.csv

Giữ 8 cột của template:

```text
candidate_id,movie_slot,movie_id,post_url,post_id,selected_from_post_content_only,unused_exposure_evidence,notes
```

- `candidate_id`: ID duy nhất cho từng ứng viên.
- `movie_slot`: kế hoạch phân bổ, không thay thế movie ID; cùng slot không
  được gán hai movie ID khác nhau.
- `movie_id`: mã phim thật, dạng chữ/số/gạch dưới/gạch ngang.
- `post_url`: URL HTTPS Facebook chứa post identity nhận dạng được.
- `post_id`: có thể trống để trích từ chính URL; nếu có phải khớp URL.
- `selected_from_post_content_only`: true/yes/1 khi người chọn chỉ dùng bài
  viết, không xem comment để chọn nguồn, không dựa sentiment/keyword.
- `unused_exposure_evidence`: đường dẫn JSON receipt local, tương đối với
  CSV. Chuỗi ghi chú hoặc URL bất kỳ không thay cho evidence.
- `notes`: ghi chú nguồn, không dùng để xếp hạng/chọn comment.

Receipt phải do người phụ trách xác nhận bằng chứng thực tế, trước crawl.
Ví dụ cấu trúc sau **cố ý chưa hợp lệ**, không được coi là chứng nhận sẵn:

```json
{
  "post_id": "ID_TRICH_TU_URL_THAT",
  "post_url": "URL_BAI_THAT",
  "movie_id": "MA_PHIM_THAT",
  "selected_from_post_content_only": false,
  "comments_not_inspected": false,
  "not_used_for_guideline_or_model_selection": false,
  "attested_by": "",
  "evidence": "",
  "recorded_at": ""
}
```

Chỉ đổi các boolean sang true khi đúng thực tế, ghi người xác nhận, mô tả
bằng chứng cụ thể và timestamp có timezone. Identity phải trùng CSV; receipt
được pin SHA-256. Đây là **attestation người cung cấp**, không phải bằng chứng
được suy ra tự động từ việc không tìm thấy lịch sử. Mâu thuẫn với lịch sử
cũ vẫn bị chặn, dù receipt ghi true.

Preflight kiểm cả post ID và URL đã bỏ tracking, duplicate alias trong cùng
file, master cũ, pool/metadata history, post đã scheduled/visited trong run
config và những intake đã quarantine. Không đọc nội dung comment để chọn
bài. Validation URL là syntax/embedded ID + đối chiếu metadata local; chưa
chứng minh remote accessibility, group công khai hay phim được bàn đúng.
Những điều đó cần evidence post-only của người chuẩn bị nguồn.

Không bỏ qua dòng sai để crawl phần còn lại: khi còn lỗi, toàn plan BLOCKED,
không xuất `crawl_posts.csv`, không đăng ký quarantine, không mở browser.
File user và evidence không bị sửa.

## Crawl và reservation

```powershell
python scripts/collect_blind_test_posts.py preflight --input test_posts.csv --output outputs/phase_g/test_posts_preflight_v2
python scripts/collect_blind_test_posts.py crawl --plan outputs/phase_g/test_posts_preflight_v2 --channel brave --profile data/browser_profile_brave_manual
python scripts/collect_blind_test_posts.py reserve --plan outputs/phase_g/test_posts_preflight_v2 --run <fb_run_id> --output outputs/phase_g/post_collection_v2
```

Các đường dẫn là output mới. Không chạy crawl nếu preflight chưa READY.
Khi READY, post được quarantine trước crawl trong `data/test_reservations/`.
Guard baseline và silver đọc registry này, kể cả khi task mù mặc định vẫn
PARTIAL. Không dùng comment ứng viên cho train/validation/pseudo-label/
active learning/prompt/guideline/threshold tuning.

Lệnh crawl chỉ gọi lại CLI `src.crawler crawl-batch`, do đó vẫn dùng Store,
run_posts và Selenium hiện tại. Không tạo crawler khác, không gọi API AI.
URL nằm trong CSV, không ghép vào shell command. Terminal kế thừa để người
dùng tự đăng nhập. G.1 đã bỏ count cap, dùng `--max-comments all`; mặc định
50 vòng, 300 giây, thời gian settle 1500 ms và tối đa 20 action/vòng;
đây là thứ tự crawl DOM, không phải mẫu ngẫu nhiên toàn bộ Facebook.
`--resume` chỉ chấp nhận run có đúng source_dataset, danh sách bài/phim và
thời gian sau preflight, không có interactive post bổ sung ngoài kế hoạch.

Trước khi crawl lại kiểm post mới xuất hiện trong run config; nếu user sửa
CSV/receipt sau preflight thì chặn và yêu cầu lập plan mới. Trước reserve
khóa run bằng **RunLock hiện có**, không nhầm file lock còn tồn tại là run
đang chạy. Reserve hiện hỗ trợ data root chuẩn của repo; root khác cần
importer config rõ ràng, không âm thầm bỏ raw khỏi master.

Sau crawl, tạo master mới từ nguồn truy cập được, nối toàn bộ development,
post/comment ID, exact/near variants và bridge theo chính sách Phase G.
Chọn chỉ sau kiểm leakage, bằng seed 20261111, quota **10/bài, 20/phim**;
mục tiêu vẫn **180**, B lấy 50 câu. Thiếu quota → PARTIAL, selected=0,
không workbook/task nhỏ hơn và không đọc nhãn để bù quota. Khi đủ, khóa cả
component trước gán nhãn; registry giữ pointer/checksum reservation mới.

Master/child snapshot được ghi bất biến. Manifest ngoài và reservation
registry chỉ publish sau các bước kiểm tra; nếu có lỗi, output dang dở giữ
lại để chẩn đoán, không được coi là task sẵn sàng. Dùng đường dẫn mới khi
thử lại. File chứa bình luận, receipt và mapping luôn giữ local/gitignored.

## Validation thực hiện

- Mốc trước thay đổi: **210/210 tests pass**. Sau thay đổi:
  **221/221 tests pass**, `python -m unittest discover -s tests`, 39,293 giây.
- Audit 8 bài và preflight đúng file CSV user đã chạy; chưa crawl thực tế vì
  input chưa có URL/evidence, chưa tạo independent gold/test Excel thật.
- Unit fixture phủ đổi header, từ chối header raw sai nghĩa, preservation
  view, URL/ID mismatch, alias duplicate, receipt, evidence thay đổi,
  history cũ, recheck trước browser, resume/run sai, registry quarantine,
  reuse crawler CLI và reservation 180/50 hoặc PARTIAL không nới quota.
- Lịch sử master/nhãn/artifact cũ được kiểm lại bằng validator Phase G;
  không cần train hoặc gọi API để kiểm những thay đổi này.
  Kết quả thật: **PASS**, nguyên 400 quyết định, 19 review events và 96 tệp
  bảo vệ; CSV của user giữ nguyên SHA-256 so với lúc preflight.
  Log/audit local: `outputs/phase_g_support/tests_intake_after.log`,
  `outputs/phase_g/audit_intake_followup/validation.json`.

Phase G vẫn **PARTIAL** do chưa có nguồn test đủ bằng chứng và quota.
