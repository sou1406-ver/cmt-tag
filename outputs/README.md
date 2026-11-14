# Dữ liệu local sau dọn

| Cần xem | Đường dẫn | Ý nghĩa |
|---|---|---|
| Một dataset tham chiếu | [comments.csv](canonical/versions/filtered_20261112_final/comments.csv) | 25.810 dòng, Facebook/legacy phân biệt bằng source; raw và minimal riêng |
| Manifest dataset | [manifest.json](canonical/versions/filtered_20261112_final/manifest.json) | 11 artifact bất biến; SHA manifest 602d98e0ee184c8c01f7bd89e2e129918341a367fcfcf862e7b9f56d3352d0f6 |
| Quality view lịch sử | [thư mục](canonical/versions/filtered_20261113_quality_v1/) | View/flags cũ, chưa approved |
| Nhãn người phát triển V1 | [thư mục](development/) | 425 sentiment trong dataset sau lọc; không tự chuyển sang nhãn V2 |
| AI và human audit V1 | [thư mục](ai_labeling/) | Quyết định nguồn giữ riêng; 350 task cũ đã trả UNLABELED, silver chưa approved |
| Gold V1 | [thư mục](gold/) | Đã khóa và evaluate một lần; giữ lịch sử, không train/tune lại |
| Crawl kiểm tra text sạch | [thư mục](crawler_review_20261114/) | Excel 65 dòng đầu; batch tiếp 95 dòng/3 phim, xem batch_summary.json để đến CSV export; không nhập canonical/train |
| Thực nghiệm gần nhất V1 | [REPORT.md](development_silver_cv_20261113_partial_03/REPORT.md) | Kết quả tạm thời với silver chưa approved |
| Output lịch sử đã gom | [history_before_v2_20261113.zip](../data/archive/history_before_v2_20261113.zip) | Bản sao nguyên byte; ARCHIVE_INDEX.json chứa đường dẫn/SHA từng file |
| Biên bản dọn local | [thư mục](local_cleanup_20261113_v2/) | Plan, SHA trước/sau, receipt xóa và unittest log |

## Cách dùng

Dùng dataset sau lọc ở dòng đầu để tham chiếu. Không nối các snapshot cleaning/phase
vào nó: chúng thường là các phiên bản của cùng ID, nối sẽ nhân đôi dữ liệu.
Không đổi active pointer, raw hoặc nhãn; không tạo một ground truth mới từ AI.

V2 đã chọn **cảm xúc chung của toàn bình luận**. Nhãn và kết quả V1 theo mục tiêu
sentiment về phim chỉ là lịch sử; chưa phải nhãn/metric V2. Chưa crawl, gán hoặc
train lại trong lần dọn này.

Các phase cũ đã được lưu ZIP rồi xóa bản rời sau khi kiểm SHA từng file. Khi cần
replay một bước lịch sử, đọc ARCHIVE_INDEX.json, khôi phục đúng prefix cần thiết
về root repo và không ghi đè file hiện có. Không phải giải nén tất cả để chạy
workflow hiện tại. ZIP là backup nghiên cứu local, không được push.

Giữ phase_g/master và blind_test, phase_g1/phase_g2 vì code gold/exposure còn đọc
chúng; giữ rebuild_20261112 để đối chiếu provenance/bộ lọc. Các đường dẫn này cùng
raw/journal, labels, test reservations và evaluation receipts không bị chuyển.
Một log trong development_support chưa đọc được nên giữ nguyên thư mục này.

Cache pretrained đã xóa; demo checkpoint đã fine-tune vẫn còn. Chạy lại huấn luyện
Transformer cần tải pretrained theo revision/checksum cũ. Không khởi động lại run
đã hủy. Code WIP của run hủy vẫn được bảo toàn và chưa nằm trong commit dọn.

Mọi data/import/task/comment chỉ lưu local và bị .gitignore chặn. Ngừng track không
xóa các bản trong Git history; không rewrite history trong nhiệm vụ này.
