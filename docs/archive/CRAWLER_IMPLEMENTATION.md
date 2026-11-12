# Kết quả triển khai crawler — 09/11/2026

## Thay đổi

- Tạo `src/crawler/{__init__.py,__main__.py,parser.py,dom.js,browser.py,store.py}`:
  CLI single/batch, parser DOM hẹp, state machine có giới hạn, Playwright có giao
  diện, journal raw bất biến, checkpoint/resume, validator/report và export CSV.
- Tạo `requirements-crawler.txt` (Playwright 1.64.1), CSV mẫu URL bài,
  fixture HTML và `tests/test_crawler.py`.
- README nối hướng dẫn `docs/CRAWLER.md`; `.gitignore` bảo vệ browser binaries
  local; profile mặc định nằm trong `data/` đã được ignore.
- Không sửa `crawl/crawl.js`, `crawl/tien_xu_ly.py`, Phase B code/config/tests,
  guideline, handoff hoặc dữ liệu thật. Không tái dùng dữ liệu/nhãn legacy.
  Không xóa file trong nhiệm vụ crawler; các deletion MMR thuộc audit trước đó.

## Kiểm chứng thực tế

Mốc trước crawler: 39/39 test PASS. Sau triển khai: 54/54 PASS, không skip,
gồm 15 test mới. Chạy bằng CPython 3.12.14 bundled có pandas/numpy, thêm
Playwright từ venv riêng qua PYTHONPATH để kiểm tra đủ cả legacy lẫn DOM.
Chromium tải riêng ở `.playwright-browsers`, không dùng profile người dùng.
Compileall `src scripts tests` PASS. CLI `--help`, validate/export và subprocess
prepare-data được kiểm thử. `git diff --check` và cached check sạch trước commit.

Test bao phủ comment/reply, body không lẫn bài/author, mở nội dung dài, truncated,
text giống khác ID, thiếu comment/post ID, emoji/newline, DOM rỗng/access barrier,
budget comment, retry/batch tiếp tục, Ctrl+C/resume, tail write bị ngắt, metadata
hỏng, exporter không sửa raw, CLI export → Phase B và split cùng post.

Phase B không thay thuật toán: ID/text/post group vẫn được kiểm bằng các test
cũ và test tích hợp mới. `fingerprint_code()` hiện hash cả Python trong `src`,
nên thêm package crawler làm data_version của các run mới thay đổi; đây là hành
vi provenance sẵn có, không phải thay đổi kết quả xử lý hoặc quy tắc split.

## Chưa được xác nhận

Không có URL bài thật hoặc phiên đăng nhập Facebook được cung cấp; chưa smoke
test live, không tuyên bố DOM adapter hoạt động trên mọi giao diện Facebook hoặc
đã thu đủ bình luận. Cần làm smoke test giới hạn và đối chiếu mẫu như hướng dẫn.
Metadata chỉ lấy nếu có bằng chứng trong URL/DOM, thiếu để null. Comment creation
time thường thiếu vì DOM dùng thời gian tương đối. Không có author/profile data.
Run raw độc lập, dedup ID trong run; thiếu ID và lặp giữa run cần review/provenance.
Chưa triển khai labeling, train, gold, active learning hoặc dashboard.

## Git

Người dùng đã yêu cầu push sau khi hoàn tất. Đợt bàn giao gồm crawler mới và
thay đổi dọn MMR từ yêu cầu trước, không có thay đổi chưa commit nào khác của
người dùng ở mốc audit. Chỉ stage code/config/docs/fixtures rõ ràng, không data,
profile, binaries, venv hoặc artifacts test. Push thường, không force/history rewrite.
