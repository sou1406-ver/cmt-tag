# Phase G.1 — Tách collection khỏi test sampling

Điều chỉnh sau `659987d`, trước khi chuyển ưu tiên sang audit G.2.
Không crawl mới trong lượt thực hiện này.

- Luồng intake dùng crawler cũ với `--max-comments all`, lưu JSON null cho
  count cap. Không dùng số giả rất lớn, không còn cap cứng 100. Crawler CLI
  thường vẫn giữ default cũ nếu người dùng không chọn `all`.
- Collector giữ mọi comment/reply hợp lệ truy xuất được cho đến khi DOM
  không đổi hoặc chạm timeout/số vòng/access barrier/lỗi. Các giới hạn an toàn
  vẫn được lưu trong run; resume tiếp tục từ journal, không reset dữ liệu.
- Mặc định intake: 300 giây/bài, 50 vòng, settle 1500 ms, 20 action/vòng;
  CLI cho phép cấu hình các budget dương. Run capped cũ không được âm thầm
  chuyển cấu hình khi resume; giữ nguyên và dùng run mới không có count cap.
- Mỗi lần hoàn tất attempt ghi số mới, tổng comment/reply của bài, thời gian,
  status và reason. Báo cáo luôn `coverage_verified=false`, kể cả
  `success/visible_dom_exhausted`; đó không chứng minh đã lấy hết Facebook.
- Master giữ mọi record/observation; sampler mới chọn tối đa 10/bài, 20/phim,
  seed 20261111, mục tiêu 180. Không lọc master xuống bằng kích thước test.
- Quarantine đăng ký post trước crawl và lưu toàn bộ connected components
  sau rebuild master, cả ID/alias/duplicate và comment không được chọn.
  Registry vẫn bảo vệ component khi chưa đủ 180 và task là PARTIAL.
- Master mới xuất `platform`, `source`, `source_platform`, giữ source_dataset
  và provenance. Facebook/MoMo có namespace ID riêng; trùng numeric ID không
  tự merge. Exact/near text có thể nối component cross-platform để chống
  leakage. MoMo không được chọn vào independent test Facebook; chưa có
  protocol đánh giá cross-platform hoặc crawler MoMo mới.

## Hai file người dùng đặt vào repo

File thật là CSV, không phải XLSX:

- `review_source_inventory.csv`: 30 nguồn, 17 Facebook + 13 MoMo. Có một
  nguồn Facebook đã nằm trong master; đây là danh sách nguồn, không phải
  30 review hoặc 30 bài đủ điều kiện test. Chưa xác minh remote accessibility.
- `test_posts_draft.csv`: 25 dòng, 16 URL Facebook đã điền, 9 dòng trống;
  thiếu movie ID và evidence. Preflight local **BLOCKED 25/25**, chưa mở
  browser, không tự điền phim hoặc attestation. Log từng dòng tại
  `outputs/phase_g1/draft_preflight/validation.csv`.

Hai file giữ nguyên byte và gitignored. MoMo chỉ là 13 candidate URL; chưa
thu review, không nhập catalog URL thành comment master. Master G cũ đã
khóa không ghi đè; những field namespace mới áp dụng cho snapshot mới.

Fixture G.1 kiểm collector lưu >100 record khi cap=null, cap số cũ vẫn hoạt
động, scope coverage không được nâng thành all-comments, namespace Facebook/
MoMo không merge sai, MoMo bị loại khỏi Facebook test và quarantine mọi
member/alias của post. Không có browser Facebook thật trong các fixture.

Theo yêu cầu ưu tiên mới, dừng mở rộng thu thập ở đây và dùng 29k legacy
cho audit/annotation G.2. Danh sách link giữ làm nguồn dự phòng.
