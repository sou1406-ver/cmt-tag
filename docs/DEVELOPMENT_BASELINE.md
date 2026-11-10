# Chuẩn bị dữ liệu và baseline thăm dò

Dùng [guideline chính](guidelines/MOVIE_SENTIMENT.md). Nhãn được giữ theo task
ban đầu; việc cập nhật hướng dẫn không tự xác nhận lại 400 quyết định cũ.

## Bộ dữ liệu làm việc

Một thư mục chính: `outputs/development/`. Excel `annotations.xlsx` có ba sheet:

- `Duyet nhan`: 18 đề xuất rà nhãn và một dòng REVIEW thiếu mã. Điền `decision`
  bằng KEEP / CHANGE / DEFER. CHANGE cần quyết định mới và lý do; REVIEW cần mã.
  Đề xuất và nhãn hiện tại nằm ở các cột riêng. Sau khi lưu, cần nhập các quyết
  định theo ID, kiểm tra lịch sử và tạo lại bản chuẩn bị trước khi chạy model.
- `400 binh luan`: toàn bộ quyết định đã chuẩn hóa, giữ nguyên văn bản task,
  emoji, phủ định, ID và nguồn vòng gán. Không sửa trực tiếp sheet này để duyệt.
- `Thong ke`: nhãn đã nhập theo chủ đề phim nguồn, trước khi duyệt đề xuất.

CSV `annotations.csv` giữ đủ provenance gồm comment/post/parent ID, URL,
crawl run, cohort, checksum workbook và guideline của task gốc. `manifest.json`
khóa checksum đầu vào/đầu ra. `provenance/` giữ snapshot và log từng thao tác,
phân vùng sentiment / REVIEW / EXCLUDE. Không xóa vật lý dòng nào.

| Đợt | POS | NEG | NEU | REVIEW | EXCLUDE | Tổng |
|---|---:|---:|---:|---:|---:|---:|
| Pilot Mưa Đỏ | 88 | 8 | 71 | 4 | 29 | 200 |
| Đa phim | 20 | 137 | 22 | 1 | 20 | 200 |
| Tổng | 108 | 145 | 93 | 5 | 49 | 400 |

Đây là nhãn một người đã nhập, chưa phải tập gold độc lập. Có **346** dòng mang
nhãn sentiment. Trong đó **17** dòng đang chờ rà nhãn; kế hoạch tạm dùng **329**
ứng viên không bị đánh dấu, nhưng vẫn chặn huấn luyện toàn bộ đến khi người gán
duyệt. Dòng EXCLUDE được đề nghị xem lại cũng chưa tự chuyển thành NEU.

Các xác nhận trước trong chat được áp dụng theo ID với expected/set/evidence:
pilot dòng 19 NEU, 196 POS, dòng 3 và 11 thêm REV_CONTEXT. Chỉ phục hồi một dấu
cách cuối văn bản ở pilot dòng 34 và đa phim dòng 58/59/80/180 theo task gốc.
Workbook nguồn không đổi. Đa phim dòng **155** (`spoil =))`) vẫn thiếu mã REVIEW.

Giữ POS cảm xúc ở dòng 87 đã xác nhận, cùng dòng 55/195 theo hướng dẫn hiện hành;
không tự đưa các dòng này sang REVIEW vì chỉ không có từ khen nghệ thuật.
Các đề xuất còn lại ở dòng 6, 26, 40, 49, 62, 74, 77, 91, 112, 124, 139, 150,
161, 165, 178, 180, 181, 190 là câu hỏi để người gán quyết định, không phải đáp án.
Những ghi chú audit tùy chọn của pilot vẫn giữ ở báo cáo cũ, chưa tự sửa nhãn.

## Phụ thuộc phim và nhãn

Theo `statistics.json`, Mưa Đỏ là chủ đề nguồn của **205/400** dòng; trong đó
90 POS, 10 NEG, 71 NEU, 4 REVIEW, 30 EXCLUDE. Các bảng theo bài, vòng gán,
fanpage/group và cohort được xuất cùng thống kê theo phim.

Trên 346 nhãn sentiment hiện tại, Cramér's V không hiệu chỉnh là **0,5601**,
mutual information **0,3883 nat** giữa chủ đề phim nguồn và nhãn. Có 59 ô chéo
ít hơn 5 mẫu. Đây chỉ là mô tả tập đã chọn: vòng pilot một phim và vòng đa phim
ưu tiên phê bình có cách lấy mẫu khác nhau. Không suy ra quan hệ nhân quả hoặc
khẳng định model đã học shortcut; chưa có model trên dữ liệu này.
Thống kê tách theo vòng và cohort cũng có trong JSON.

`movie_id` là chủ đề bài nguồn; comment có thể nói phim khác hoặc so sánh nhiều
phim. Chưa coi việc giữ riêng movie_id là đánh giá khái quát sang phim chưa thấy.

## Cấu hình và kiểm tra đã thực hiện

```powershell
python scripts/prepare_development.py
python scripts/development_baseline.py
```

Lệnh chuẩn bị từ chối ghi đè output đang có và từ chối input khác checksum;
đầu ra chỉ được đặt vào thư mục đích sau khi chuẩn bị thành công. Các input
workbook nằm local; checkout Git mới cần người vận hành cung cấp đúng hai bản.
Builder Excel là công cụ tạo tài liệu local; hai lệnh trên tạo CSV, JSON và plan.

`configs/baseline_development.json` cố định TF-IDF unigram+bigram, NB (alpha=1),
LR và LinearSVC (C=1, balanced), seed 42, 3-fold StratifiedGroupKFold.
Các nhóm nối bắc cầu theo bài, comment ID, trùng văn bản chuẩn hóa NFC/khoảng
trắng/không phân biệt hoa thường và gần trùng token-3gram Jaccard ≥0,9.
Dùng lại nhóm/trích xuất đặc trưng/model/metrics hiện có; không sửa Phase B
hoặc nới điều kiện independent gold của Phase D.

Kế hoạch tạm có 36 cụm bài/duplicate trên 400 dòng, không thấy ID trùng,
trùng văn bản hoặc cặp gần trùng theo ngưỡng này. Sau khi bỏ các dòng chờ duyệt,
fold validation tạm có 144 / 103 / 82 dòng; mọi fold train đều có đủ ba lớp.
Hai biến thể dùng đúng cùng ID/fold, TF-IDF chỉ fit trên phần train mỗi fold:

- `original`: nguyên văn comment.
- `masked`: thay alias phim/nhân vật xác định trong `configs/entity_mask.json`
  bằng TEN_PHIM / TEN_NHAN_VAT; không cắt tên bằng regex chữ hoa. Từ đơn mơ hồ
  như “Mai”, “Sen”, “Cường”, “Quang” không bị che toàn cục. Lexicon có giới hạn,
  cần kiểm tra độ phủ trước khi diễn giải so sánh và khóa trước test độc lập.

`--run` là hành động fit rõ ràng và hiện bị chặn bởi 19 quyết định chưa chốt.
Sau khi nhập quyết định người gán và kiểm tra lại manifest, lệnh này sẽ xuất
OOF metrics, recall từng lớp, confusion matrix, dự đoán sai và hệ số SVM theo
fold. Accuracy trong metrics chỉ mô tả mẫu phát triển đã chọn, không phải hiệu
năng theo phân phối thực tế. Không tạo hoặc mở test độc lập.

**Đã chạy:** chuẩn hóa local, kiểm checksum/ID/provenance, thống kê, kế hoạch
chia nhóm; fixture kiểm NB/LR/LinearSVC, cả hai biến thể, metrics và chống rò
vocabulary. **Chưa chạy:** train/CV trên 400 dòng thật, so sánh che tên, phân
tích hệ số/dự đoán sai trên nhãn thật, đánh giá phim mới hoặc gold test độc lập.

Kiểm tra cuối: `python -m unittest discover -s tests` **138/138 pass**;
`git diff --check` sạch. Đã đối chiếu 400 dòng Excel với CSV, 19 ô quyết định
chưa điền, native dropdown/filter, không có formula trong dữ liệu comment và
checksum các input/task không thay đổi.
