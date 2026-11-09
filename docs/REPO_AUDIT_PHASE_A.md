# Phase A — Repo audit (07/11/2026)

> Báo cáo lịch sử, giữ nguyên kết quả tại thời điểm Phase A. Quyết định giữ
> MMR/Hello World đã được thay thế bởi [audit dọn repo ngày 09/11/2026](REPO_CLEANUP_AUDIT.md).

Đặc tả: `CODEX_HANDOFF_MOVIE_SENTIMENT.md` v1.0. Chỉ bắt đầu A → B;
chưa huấn luyện, chỉnh mô hình, gán lại sentiment hay chạy crawler.

## Hiện trạng đã kiểm tra

- `git status --short`: **fatal: not a git repository**. Thư mục chưa có `.git`;
  ở thời điểm audit chưa khởi tạo Git hoặc commit dữ liệu. Sau đó người dùng
  yêu cầu push lên `sou1406-ver/cmt-tag`, cho phép khởi tạo Git phục vụ bàn giao.
- Đã kiểm kê toàn bộ file ngoài `.venv`/cache; đọc mã nguồn crawler,
  preprocessing, labeling, features, MMR; kiểm tra artifacts trong `media`.
- Không có `AGENTS.md`, README, requirements, config, notebook hoặc bộ test.
  `test.py` chỉ in Hello world.
- `crawl/dataset.csv`: **3.471** dòng, cột `text`, không rỗng/trùng raw chính xác.
- `crawl/dataset_daxuly.csv`: **3.430** dòng, `text,clean`.
- `crawl/dataset_daxuly_gannhan.csv`: **3.430** dòng; `nhan_nguoi` **đều trống**.
  Nhãn luật máy: positive 870, negative 151, neutral 1.637, hard 109,
  unrelated 663. Đây **không phải phân phối nhãn gold**, chưa đo độ đúng.
- Không có dữ liệu 29k. Tên phim/nguồn gốc từng dòng, post/comment IDs,
  thời điểm thu thập, license và privacy chưa được xác minh từ file.
- `.venv` Python 3.14.2 trỏ tới tài khoản `sou` trên máy khác, không chạy được.
  Python bundled 3.12.14 chạy được; có pandas/numpy nhưng thiếu
  sklearn/scipy/torch/pyvi/pytest/manim. Không sửa `.venv` cũ.
- GPU hiển thị Intel UHD Graphics; không thấy `nvidia-smi`, chưa có torch.
  Không có môi trường CUDA đã xác nhận. Không chặn Phase B.
- `media`: 101 MP4, 330 SVG, 15 TeX, 1 TXT từ MMR; giữ nguyên.

## Giữ / sửa / tạo

| Thành phần | Quyết định | Lý do |
|---|---|---|
| Ba CSV hiện có | Giữ byte nguyên vẹn | Nguồn/derived cũ cần đối chiếu; snapshot riêng khi import |
| `crawl/crawl.js` | Giữ, hoãn Phase G | Chỉ xuất text; dedup prefix 50 ký tự có thể mất comment; không khôi phục metadata giả |
| `crawl/tien_xu_ly.py` | Giữ cho đối chiếu | Có NFC/teencode tái dùng ý tưởng; pipeline mới chỉ NFC + whitespace, giữ emoji/dấu/phủ định |
| `gan_nhan.py` | Vá bảo vệ dữ liệu | Không xóa nhãn người khi chạy lại, không ghi đè đầu ra; luật cũ chỉ là nguồn máy chưa kiểm định |
| `trich_dac_trung.py` | Chặn CLI fit corpus chưa chia | `fit_transform(docs)`/Word2Vec/PPMI/IDF hiện dùng toàn bộ file, gây leakage nếu chia sau đó |
| Helpers vectorizer cũ | Giữ để Phase D tái sử dụng | Chỉ được fit trên train, không dùng matrices fit toàn corpus |
| `mmr_core.py`, `mmr_manim.py`, `media`, `test.py` | Giữ | Demo khác bài toán; không nhập vào sentiment pipeline |
| `src/data`, `configs`, `scripts`, `tests`, README | Tạo Phase B | Import/snapshot/schema/provenance/quality/dedup/group split và kiểm thử |

## Các lỗi/rủi ro phải xử lý trong Phase B

1. Không coi nhãn luật hay confidence tự chế `do_tin` là gold/xác suất.
2. `hard` → trạng thái REVIEW; `unrelated` → đề xuất EXCLUDE. Không phải sentiment.
   `neutral` cũ chỉ là đề xuất máy, không xác nhận NEU.
3. Tiền xử lý cũ bỏ emoji, dấu câu, số, stopwords gồm “nhưng”, và loại câu
   <= 1 từ; các thao tác có thể mất nghĩa. Không chạy lại lên raw.
4. Gom post và duplicate xuyên nguồn trước split; near-duplicate chỉ gắn cờ
   và gom nhóm bảo thủ, chưa tự xóa khi chưa có người xác nhận.
5. Thiếu metadata bài viết: chỉ ngăn trùng text/nhóm trùng đã phát hiện;
   **không thể cam kết độc lập bài viết**. Split B là pool phục vụ annotation,
   chưa phải gold validation/test khóa sẵn, chưa được huấn luyện/đánh giá.
6. Phải lưu report, seed, config, checksum code/input/output để tái lập khi chưa có Git.

## Kiểm tra Phase A

Đã chạy Git status, inventory `rg --files`, đọc toàn bộ Python/JS liên quan,
CSV qua `csv.DictReader`, SHA-256, kiểm tra runtime và GPU. Chưa có bộ test
trước thay đổi; không chạy các script có thể ghi đè CSV/fit toàn corpus.

SHA-256 ban đầu:

| File | SHA-256 |
|---|---|
| `crawl/dataset.csv` | `0d349815ddd974d1a102316ddb9cc4fb180ad1bfa9e4688f19f8c7156bde953a` |
| `crawl/dataset_daxuly.csv` | `1c38d2ba13a4cd1f25a3a689a65c661ee77817bba56b27d9bd033378fc645834` |
| `crawl/dataset_daxuly_gannhan.csv` | `b430b53522dbd71b6bd759b669bb578e03a3c72b8f1cdc01da5de269e71d54b5` |

Bước tiếp theo: triển khai Phase B và chạy pipeline trên nguồn 3.471 raw;
nhãn luật 3.430 dòng nhập riêng với provenance chưa được kiểm định.
