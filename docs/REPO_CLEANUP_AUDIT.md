# Audit dọn repository — 09/11/2026

## Phạm vi và hiện trạng trước thay đổi

Chỉ phục vụ phân loại sắc thái bình luận phim POS/NEG/NEU bằng Python CLI.
Không refactor thuật toán, thay guideline, cấu hình dữ liệu hoặc dependencies.
`git status --short --untracked-files=all` ban đầu sạch. Có 30 file tracked;
không có media, virtualenv, cache, log, checkpoint, model hoặc dữ liệu thật
trong bản clone trước khi kiểm thử. Không có AGENTS.md áp dụng trong workspace.
Không đọc secrets, credential hoặc Chrome profile. Không reset/clean/history rewrite.

Đã đọc cấu trúc, code Python/JS, tài liệu, configs, fixtures và tests; kiểm tra
imports, CLI, các đường dẫn đọc/ghi và tham chiếu bằng tìm kiếm toàn repo.
Phân loại dựa cả chức năng và quan hệ sử dụng, không chỉ tên hoặc import.

## Danh sách quyết định trước khi xóa

| File/nhóm | Phân loại | Bằng chứng và lý do |
|---|---|---|
| `mmr_core.py` | REMOVE | Demo tóm tắt đa văn bản: sentence TF-IDF, centroid, Sim1/Sim2, MMR, Top-K và NLI giả lập. Chỉ `mmr_manim.py` import; không có caller từ sentiment, configs hoặc tests. Không xuất dataset, labels, split hay model sentiment. |
| `mmr_manim.py` | REMOVE | Import Manim và `mmr_core`; các Scene chỉ minh họa MMR với preset tin tức, MathTex, animation. Không có consumer trong pipeline sentiment. |
| `test.py` | REMOVE | Toàn bộ nội dung là `print("Hello world")`; không có test/assert/import và không được script/config nào gọi. Bộ unittest thật nằm trong `tests/`. |
| `crawl/crawl.js` | KEEP | Công cụ thu thập comment xuất CSV; bảng điều khiển DOM phục vụ thu thập legacy, không phải ứng dụng web sentiment. Được người dùng yêu cầu bảo vệ. |
| `crawl/tien_xu_ly.py` | KEEP | Tiền xử lý legacy, có CLI và dữ liệu chuyển tiếp sang labeling; giữ để đối chiếu, không chạy lại trên raw. |
| `gan_nhan.py` | KEEP | CLI gán nhãn luật bán tự động; test tích hợp bảo vệ nhãn người/metadata và chống ghi đè. |
| `trich_dac_trung.py` | KEEP | Helper đặc trưng và CLI yêu cầu manifest/near-duplicates, fit train pool; phục vụ Phase D dù môi trường hiện thiếu dependency numerical. |
| `src/__init__.py`, `src/data/*.py` | KEEP | Package marker, importer, schema/provenance, quality, dedup, group split, preparation và validator; được CLI/tests gọi. |
| `scripts/*.py` | KEEP | Hai CLI prepare/validate; gọi `src.data`, được kiểm thử end-to-end. |
| `configs/data_fixture.json`, `tests/**` | KEEP | Nguồn CSV/JSON tổng hợp, config kiểm thử, 39 tests và package marker; không phải dữ liệu rác/trùng thừa. |
| `configs/data_legacy.json` | KEEP / REVIEW khi chạy | Map raw và annotation sidecar cũ, provenance và seed/split; không có ba CSV được tham chiếu trong clone. Thiếu input local không chứng minh config thừa. |
| `README.md`, `.gitignore`, `requirements-data.txt` | KEEP | Setup, bảo vệ artifacts và mô tả Phase B standard library. Không có dependency Manim/MMR trong manifest để gỡ. |
| Handoff, schema, báo cáo Phase A/B | KEEP | Đặc tả và bằng chứng nghiên cứu. Tham chiếu MMR trong báo cáo là lịch sử; thêm ghi chú thay vì xóa lịch sử. |
| `media/` | KEEP nếu có local về sau | Không tồn tại trong clone hiện tại; không xóa hoặc kết luận theo inventory lịch sử. Giữ ignore để tránh vô tình commit media local. |

Trước khi thực hiện xóa, đã xác nhận tất cả REMOVE là tracked, không có
thay đổi chưa commit và nằm trong repository. Không có artifacts MMR local
nào khác được xác nhận để xóa. Việc xóa ba file không tác động inputs/config/code
được `fingerprint_code()` dùng: hàm này chỉ hash `src/**/*.py`, `scripts/*.py`.

## Thay đổi tài liệu và cấu hình

- README: phạm vi CLI, trạng thái triển khai thật, dependencies legacy, phân biệt
  kiểm kê dữ liệu lịch sử với clone hiện tại và nguồn 29.688 dòng mới nằm ngoài repo.
- `.gitignore`: giữ toàn bộ quy tắc bảo vệ dữ liệu/model/media; thêm `.env` và
  `.env.*`, cho phép template `.env.example`/`.env.sample`. Ignore không phải lệnh xóa.
- Phase A/B: chỉ thêm liên kết tới audit này, giữ nguyên nội dung/kết quả lịch sử.
- `requirements-data.txt` không đổi: chỉ standard library, không có Manim/MMR.
  Không tạo manifest mới hoặc cài dependency trong nhiệm vụ dọn repo.
- Không sửa configs, source sentiment, tests, fixtures hoặc handoff.

## Kiểm chứng

Runtime: CPython 3.12.14 bundled trên Windows, numpy/pandas có sẵn.

| Kiểm tra | Trước | Sau |
|---|---|---|
| `python -m unittest discover -s tests -v` | 39 PASS, 0 skip | 39 PASS, 0 skip |
| Fixture CSV + JSON prepare/validate | PASS, 14 raw, 10 representatives; train/dev/test = 6/2/2 | PASS, cùng counts/version; validator CLI trả valid |
| Import data modules, labeling, preprocessing | PASS | PASS |
| `--help`: prepare, validate, labeling, preprocessing | PASS | PASS |
| Feature extraction import / `--help` | Không chạy được: thiếu scipy; sklearn cũng chưa cài | Cùng lỗi dependency như trước, không do cleanup |
| Compile toàn bộ Python sentiment/tests | Không chạy riêng trước dọn | PASS |

Baseline fixture version: `d04c7820afcd138b30e3`. So sánh trước/sau byte của
records, quality decisions, near duplicates, manifest, blind exports; đồng thời
đối chiếu counts/version và checksum nguồn 29.688 dòng ngoài repo: tất cả trùng
hoàn toàn. Không thay quy tắc nhãn hoặc split. Report/run có
đường dẫn snapshot và timestamp riêng nên không dùng chúng để so byte giữa hai run.
Artifacts kiểm chứng mới được giữ riêng tại `outputs/cleanup_audit_20261109/`
(gitignored), không ghi đè kết quả cũ. Cache phát sinh do test được giữ, không
xóa cache local theo cảm tính.

Các lệnh kiểm chứng chính (dùng Python bundled ghi trong README):

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src scripts tests crawl/tien_xu_ly.py gan_nhan.py trich_dac_trung.py
python scripts/validate_data.py --data-root outputs/cleanup_audit_20261109/after --version d04c7820afcd138b30e3
git diff HEAD --stat
git diff --check
git diff --cached --check
git status --short
```

`git diff --check` và `git diff --cached --check` sạch. Các file Python/config/
fixture còn lại không đổi so với HEAD. `git rm` stage đúng ba deletion; tài liệu
và ignore là thay đổi working tree. Không có thay đổi của người dùng bị ghi đè.

## REVIEW — cần xác nhận trước công việc tiếp theo

- Nguồn local `../data_module1.csv` có 29.688 dòng đã có nhãn: cần xác nhận nguồn,
  cách tạo nhãn, guideline và điều kiện sử dụng trước khi nhập hoặc coi là gold.
  Giữ nguyên file ngoài repo; không nhập/gán lại/split trong nhiệm vụ này.
- Ba CSV legacy được báo cáo trong Phase A/B không đi kèm clone. Cần vị trí
  bản gốc nếu muốn chạy `data_legacy.json`; không xóa config hoặc giả tạo dữ liệu.
- Giữ các numerical helpers legacy dù thiếu scipy/sklearn/gensim/pyvi; nghiệm thu
  numerical features và thiết lập dependencies thuộc công việc riêng.
- Không có file còn nghi ngờ cần người dùng quyết định xóa trong bản clone này.

Không tự commit hoặc push; giữ diff để người dùng review.
