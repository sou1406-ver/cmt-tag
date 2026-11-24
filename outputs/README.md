# Dữ liệu local sau dọn

## T2 · Tập test chính V2

- [Nhãn người T2](cmt_v2_20261125/T2_nhan_nguoi.local.csv) gồm 652 quyết định. [T2 dùng để chấm](cmt_v2_20261125/T2_cham_3_nhan.local.jsonl) gồm 613 câu, giữ nguồn từng câu để báo điểm riêng T gốc và test bổ sung.
- [Chunk chờ ba AI gán](cmt_v2_20261125/ai_pending/) gồm 1.731 câu, chia thành 18 file từ `cmt_cho_gan_01.csv` đến `cmt_cho_gan_18.csv`. [Chỉ mục cục bộ](cmt_v2_20261125/cmt_cho_gan_chi_muc.local.csv) ghi nguồn và trạng thái giữ riêng. Toàn bộ 1.731 câu cùng bài với test, chỉ dùng để bổ sung test sau khi duyệt nhãn người.
- [Manifest](cmt_v2_20261125/manifest.json) ghi nguồn và SHA-256. Các kết quả cũ vẫn tham chiếu đúng snapshot ban đầu.

## Test bổ sung 25/11/2026

- [Sheet nhập link Facebook và mã phim](../test_posts.xlsx) có 42 link, gồm 26 link đã có mã và 16 link chờ mã.
- [Bình luận crawl đã gộp](test_extra_crawl_20261125_final/comments_top80.csv) và [độ phủ theo phim](test_extra_crawl_20261125_final/coverage_by_movie.csv).
- [Workbook nhãn người đã khôi phục](test_extra_label_20261125/Gan_nhan_test_bo_sung_450.xlsx) lưu 450 quyết định, trong đó 424 câu có nhãn POS/NEG/NEU.
- [Báo cáo chấm 424 câu](../docs/annotation/BAO_CAO_TEST_BO_SUNG_V2.md) và [bảng kết quả sáu mô hình](test_extra_label_20261125/evaluation/results/comparison.csv).
- [Kho lưu trữ các lượt crawl, smoke test và log cũ](../data/archive/outputs_history_20261125.zip) giữ nguyên đường dẫn cũ và SHA-256 từng tệp trong `ARCHIVE_INDEX.json`.

## V2 đang kiểm tra

Quy trình hiện hành: [AI gán trên web + người dùng duyệt](../docs/annotation/QUY_TRINH_GAN_NHAN.md).
Kế hoạch năm batch A/B và bổ sung nguồn nhỏ đã thay thế; batch 1 cũ không giao.
Giữ nguyên selection 1.000 ID tại `annotation_round_01/`. Split/blind _01 đã SUPERSEDED, không xóa hoặc sửa manifest.
- [Workbook mù MỚI](annotation_blind_50_02/T_blind_50.xlsx) · [Guideline snapshot](annotation_blind_50_02/guideline_snapshot.md).
- [Phân bố T/U MỚI nguồn/post/movie](annotation_tu_02/REPORT.md): T 202/12 post, U 798/49 post.
- Chunk C/T/U tại `annotation_chunks_01/`, E/C coordinator và recheck mapping ở `annotation_ec_01/`. Prompt local-only tại `../docs/annotation/AI_LABEL_PROMPT.md`.
- T chunk chưa được gửi AI trước khi blind 50 MỚI đã gán/import/khóa; chưa làm bước 4 trở đi.


- **Hai batch crawl mới nhất đã gộp:** [Excel](crawl_merged_20261115/review.xlsx) · [CSV đủ metadata](crawl_merged_20261115/comments.csv) · [nguồn và checksum](crawl_merged_20261115/README.md). Có 7.202 câu từ 49 bài: 6.863 KEEP, 70 REVIEW, 269 EXCLUDE; không trùng ID.
- Bản gộp 7.202 câu không gồm batch 2.521 câu ngày 14/11 hoặc batch mới bên dưới. CSV export gốc và raw/journal của từng run vẫn ở `../data/`, không xóa hay thay canonical.
- **Batch mới tiếp theo (3.072 câu/12 bài):** [Excel](../data/imports/fb_a767303a5ad8426d8fad5accb8a313cb/review.xlsx) · [CSV](../data/imports/fb_a767303a5ad8426d8fad5accb8a313cb/comments.csv). 2.819 KEEP, 53 REVIEW, 200 EXCLUDE. Tổng bốn batch V2 là **12.795 câu**, 12.066 KEEP, 148 REVIEW, 581 EXCLUDE; 89 bài, 67 movie_id. KEEP là trạng thái kỹ thuật, chưa phải nhãn sentiment.
- [Pilot đã đối soát](sentiment_pilot_v3_1/comparison_received_20261115/adjudicated/pilot_final_decisions.local.csv): giữ đúng guideline/SHA lịch sử. Lượt mới dùng [guideline chính thức](../docs/guidelines/SENTIMENT_GUIDELINE.md), không dùng lại bộ giao cũ hoặc tự chuyển nhãn V1.
- Lần dọn 15/11 loại cache Chrome cũ, fixture thử nghiệm và file authoring/log/preview trùng; giữ Chrome cache mới nhất, driver, nhãn người, Gold, checkpoint và backup lịch sử. Biên bản local: `local_cleanup_20261113_v2/cleanup_20261115.json`.

## V1 và lịch sử giữ để tham chiếu

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
| Biên bản dọn local | [thư mục](local_cleanup_20261113_v2/) | Plan, SHA trước/sau, receipt xóa và unittest log |

## Cách dùng

Dùng dataset sau lọc ở dòng đầu để tham chiếu. Không nối các snapshot cleaning/phase
vào nó: chúng thường là các phiên bản của cùng ID, nối sẽ nhân đôi dữ liệu.
Không đổi active pointer, raw hoặc nhãn; không tạo một ground truth mới từ AI.

V2 đã chọn **cảm xúc chung của toàn bình luận**. Nhãn và kết quả V1 theo mục tiêu
sentiment về phim chỉ là lịch sử; chưa phải nhãn/metric V2. Chưa crawl, gán hoặc
train lại trong lần dọn này.

Ba ZIP backup trước V2 đã được xóa ngày 25/11/2026. Kho `outputs_history_20261125.zip`
lưu các lượt crawl test bổ sung và log trung gian của V2.

Giữ phase_g/master và blind_test, phase_g1/phase_g2 vì code gold/exposure còn đọc
chúng; giữ rebuild_20261112 để đối chiếu provenance/bộ lọc. Các đường dẫn này cùng
raw/journal, labels, test reservations và evaluation receipts không bị chuyển.
Một log trong development_support chưa đọc được nên giữ nguyên thư mục này.

Demo checkpoint cũ và cache pretrained được liệt kê riêng trong `outputs/demo_transformers_425/`
và `data/local_models/`. Lượt fine-tune V2 ghim revision và checksum của model gốc.

Mọi data/import/task/comment chỉ lưu local và bị .gitignore chặn. Ngừng track không
xóa các bản trong Git history; không rewrite history trong nhiệm vụ này.
