# Baseline thăm dò trên nhãn người đã duyệt

Cập nhật 11/11/2026. Đã nhập 19 quyết định: 11 CHANGE và 8 KEEP, không còn
pending. Dùng [V2.1](guidelines/MOVIE_SENTIMENT_V2_1.md) cho đợt duyệt mới;
metadata của task gốc vẫn theo [V2.0](guidelines/MOVIE_SENTIMENT_V2_0.md).
Hai guideline bất biến và các workbook nguồn giữ nguyên checksum.

## Dữ liệu sau duyệt

| Đợt | POS | NEG | NEU | REVIEW | EXCLUDE | Tổng |
|---|---:|---:|---:|---:|---:|---:|
| Pilot Mưa Đỏ | 88 | 8 | 71 | 4 | 29 | 200 |
| Đa phim | 22 | 136 | 21 | 0 | 21 | 200 |
| Tổng | 110 | 144 | 92 | 4 | 50 | 400 |

Có 346 ứng viên sentiment; 4 REVIEW và 50 EXCLUDE ngoài train. Đây là nhãn
một người trên dữ liệu phát triển đã tiếp xúc và được chọn có chủ đích, không
phải gold test độc lập. Không tự thay lựa chọn của người gán bằng đề xuất máy.
Dòng 155 đã được người gán chuyển từ REVIEW sang EXCLUDE. POS cảm xúc đã xác
nhận được giữ nguyên. Không xóa vật lý dòng nào.

Người gán xác nhận nhập 11 CHANGE dù không cung cấp lý do. Lịch sử lưu đúng
nhãn đã chọn, human_note rỗng, reason_provided=false và dấu vết cho phép rõ
ràng; không tạo giải thích giả. Một REVIEW cũ có REV_OTHER nhưng thiếu giải
thích được giữ nguyên, liệt kê trong QA và ngoài train.

Một workbook làm việc ở `outputs/development/annotations.xlsx`; sheet
`Duyet nhan` có quyết định đã nhập. Sheet `400 binh luan` và `Thong ke` là
snapshot trước duyệt. Dữ liệu hiện tại cho pipeline ở:

- `outputs/development/reviewed/annotations.csv`: đủ 400 dòng và provenance.
- `reviewed/manifest.json`, `reviewed/review_history.json`: checksum, 19 sự
  kiện trước/sau, actor/time, guideline/hash, nguồn file duyệt và chuỗi hash.
- `reviewed/statistics.json`: thống kê theo phim/bài/cohort/nguồn/vòng gán.
- `reviewed/provenance/`: parent snapshot, file duyệt nguyên byte và phân vùng
  sentiment / REVIEW / EXCLUDE / DEFER. Không ghi đè workbook đã điền.

## Nhập quyết định và kiểm tra

```powershell
python scripts/import_development_review.py --annotator annotator_a --restore-trailing-spaces --allow-missing-change-reason
python scripts/development_baseline.py --dataset outputs/development/reviewed --output outputs/development/baseline_reviewed --run
```

Lần chạy này đã hoàn tất. Import lại cùng input/actor/options là idempotent;
run model hoặc snapshot khác cần output mới, không ghi đè kết quả hiện có.
Mặc định importer vẫn từ chối CHANGE thiếu lý do. Chỉ bật
`--allow-missing-change-reason` khi người gán cho phép rõ ràng, như đợt này.
DEFER luôn cần lý do; REVIEW mới với REV_OTHER luôn cần giải thích.

Importer đọc sheet `Duyet nhan`, header dòng 5, hoặc CSV cùng cấu trúc. Nối
đúng ID, kiểm mọi quyết định; không dựa vào vị trí dòng để áp nhãn. Cột E dòng
6–24 là KEEP/CHANGE/DEFER, F là nhãn mới, G mã REVIEW, H lý do.

Workbook ban đầu không hiển thị source_round trong sheet duyệt; importer
phục hồi metadata đó từ ánh xạ ID đã khóa và ghi log từng dòng. Với flag
khôi phục khoảng trắng, chỉ chấp nhận chênh lệch dấu cách ASCII cuối text:
5 ô sheet snapshot và 1 ô sheet duyệt đã phục hồi từ parent. Không cho sửa
nội dung, khoảng trắng bên trong, ID hoặc nhãn snapshot. Workbook gốc không
bị chỉnh để lách kiểm tra; snapshot input lưu nguyên byte.

KEEP giữ nhãn/trạng thái; CHANGE dùng đúng nhãn người nhập; DEFER giữ quyết
định gốc nhưng không huấn luyện. Baseline kiểm checksum và phát lại quyết định
để đối chiếu dataset/history trước khi fit. Chỉ đổi cờ manifest không mở được.
Không có quyết định hợp lệ thì không tạo output dở dang.

## Cấu hình và chia nhóm

TF-IDF unigram+bigram, NB alpha=1, LR/LinearSVC C=1 và class_weight=balanced,
seed 42, 3-fold StratifiedGroupKFold. Có 36 cụm post/duplicate trên cả 400 dòng;
346 dòng tham gia CV thuộc 35 bài. Không phát hiện trùng ID, trùng text hoặc
cặp gần trùng theo ngưỡng đã dùng.

Nhóm nối bắc cầu theo bài, source ID, text NFC/khoảng trắng/casefold và gần
trùng token-3gram Jaccard ≥0,9; tính trên cả các dòng ngoài train. Các nhóm
không xuất hiện ở cả train và validation. TF-IDF chỉ fit trong train của mỗi
fold. Hai biến thể dùng đúng cùng fold và ID, không thêm tuning sau xem OOF.

| Fold | Train | Validation | POS validation | NEG validation | NEU validation |
|---|---:|---:|---:|---:|---:|
| 1 | 194 | 152 | 58 | 47 | 47 |
| 2 | 242 | 104 | 29 | 48 | 27 |
| 3 | 256 | 90 | 23 | 49 | 18 |

Mọi fold train đủ ba lớp. `original` giữ nguyên text; `masked` dùng lexicon
`configs/entity_mask.json` cho TEN_PHIM / TEN_NHAN_VAT. Có 44/346 text thay
đổi do mask. Không đoán tên từ chữ hoa; tên đơn mơ hồ không che toàn cục.
Lexicon chưa bao phủ đầy đủ nên đây chỉ là một phép thử có giới hạn.

## Kết quả OOF trên dữ liệu phát triển

Macro-F1 được tính gộp từ 346 dự đoán ngoài fold, không phải trung bình ba
Macro-F1 của fold. Đã chạy sáu tổ hợp, tổng 18 lần fit.

| Model | Văn bản | Macro-F1 | Recall POS | Recall NEG | Recall NEU |
|---|---|---:|---:|---:|---:|
| Naive Bayes | original | 0.2946 | 0.1727 | 0.9514 | 0.0109 |
| Logistic Regression | original | 0.4575 | 0.3000 | 0.9167 | 0.2174 |
| LinearSVC | original | 0.4561 | 0.3182 | 0.9236 | 0.1957 |
| Naive Bayes | masked | 0.3024 | 0.1818 | 0.9653 | 0.0109 |
| Logistic Regression | masked | 0.4828 | 0.3364 | 0.9375 | 0.2283 |
| LinearSVC | masked | 0.4727 | 0.3364 | 0.9375 | 0.2065 |

Giá trị cao nhất quan sát được là LR masked, Macro-F1 0,4828; cao hơn LR
original khoảng 0,0253 trong đúng phép thử này. Chưa thể kết luận mask luôn
tốt hơn hoặc model đã hết phụ thuộc tên phim. Không có test độc lập, kiểm
định chênh lệch hoặc đánh giá phim chưa thấy.

Confusion matrix của LR masked, hàng là nhãn người, cột là dự đoán:

| Nhãn người / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 37 | 64 | 9 |
| NEG | 6 | 135 | 3 |
| NEU | 21 | 50 | 21 |

Model còn nghiêng NEG: dự đoán NEG cho 64/110 POS và 50/92 NEU. Recall NEG
0,9375 đi cùng precision NEG khoảng 0,5422; không nên diễn giải riêng recall
cao là mô hình tốt. Recall POS khoảng 0,3364, NEU 0,2283 còn thấp. Chưa có cơ
sở triển khai hoặc báo cáo đây là hiệu năng theo phân phối thực tế.

Mưa Đỏ chiếm 205/400 dòng theo chủ đề nguồn; các cohort lấy mẫu khác nhau.
Cramér's V mô tả phim–nhãn sau duyệt là 0.5640, mutual information
0.3938 nat; 60 ô chéo có ít hơn 5 mẫu. Đây là mô tả
mẫu đã chọn, không chứng minh quan hệ nhân quả hay shortcut của model.
movie_id chỉ là chủ đề bài nguồn, không luôn là phim được đánh giá trong câu.

## Kết quả và kiểm tra

`outputs/development/baseline_reviewed/` giữ metrics.json, plan.json,
predictions.csv và svm_features.csv. Dự đoán/feature coefficients đã xuất để
phân tích lỗi tiếp; chưa tự sửa nhãn theo model. Trạng thái run:
models_trained=true, provisional=false, independent_test=false.

- metrics.json SHA-256: `7b33a30c2c9b78230781342ac588d1dd84cbe64e05231ed723245da34dd9cd2b`.
- reviewed manifest SHA-256: `a4dba6c15c28455661ea84992ad4a19478e90b5dde62abe8acbe5533d2f91d64`.
- Workbook duyệt SHA-256: `78974825d72e3f559047463a3cf2fd5bb9cb7556928302092d682d88c3369788`.

`python -m unittest discover -s tests`: **149/149 pass** (24,959 giây).
Fixture kiểm Excel/CSV, quyết định thiếu/sai, KEEP/CHANGE/DEFER, nhập lặp,
log phục hồi khoảng trắng/metadata, thiếu giải thích có phép rõ ràng, REVIEW
legacy, chống sửa cờ/checksum để bỏ qua lịch sử, split/duplicate/vocabulary và
cả sáu tổ hợp model/variant. Checksum nguồn/task và workbook không đổi sau
import/run. Guideline bất biến; Phase B, silver API và independent gold gate
không bị nới. Chưa tạo test độc lập, chưa gọi API gán nhãn hoặc crawl thêm.
