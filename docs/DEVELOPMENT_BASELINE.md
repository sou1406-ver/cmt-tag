# Chuẩn bị dữ liệu và baseline thăm dò

Duyệt mới dùng [V2.1](guidelines/MOVIE_SENTIMENT_V2_1.md); nhãn task ban đầu giữ
hợp đồng [V2.0](guidelines/MOVIE_SENTIMENT_V2_0.md). Hai file khóa checksum bất
biến. Cập nhật hướng dẫn không tự xác nhận lại 400 quyết định cũ.

## Bộ dữ liệu làm việc

Một thư mục chính: `outputs/development/`. Excel `annotations.xlsx` có ba sheet:

- `Duyet nhan`: 18 đề xuất rà nhãn và một dòng REVIEW thiếu mã. Điền `decision`
  bằng KEEP / CHANGE / DEFER. CHANGE cần quyết định mới và lý do; REVIEW cần mã.
  Đề xuất và nhãn hiện tại nằm ở các cột riêng. Cột E dòng 6–24 là quyết định;
  F là nhãn mới, G là mã REVIEW, H là lý do. Cột A là dòng trong workbook gốc.
  Nhập bằng `scripts/import_development_review.py` sau khi lưu workbook.
- `400 binh luan`: toàn bộ quyết định đã chuẩn hóa, giữ nguyên văn bản task,
  emoji, phủ định, ID và nguồn vòng gán tại thời điểm tạo task. Không sửa trực
  tiếp sheet này; dữ liệu sau duyệt ở `reviewed/annotations.csv`.
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

## Nhập quyết định và mở baseline

```powershell
python scripts/import_development_review.py --annotator annotator_a
python scripts/development_baseline.py --dataset outputs/development/reviewed --output outputs/development/baseline_reviewed --run
```

Importer mặc định đọc sheet `Duyet nhan`, header ở dòng 5 của workbook chung.
Có thể dùng `--input <file.csv>` với cùng cấu trúc cột. Phải có đúng các ID
đang chờ một lần; thứ tự dòng không quan trọng. Các cột nguồn và sheet snapshot
được đối chiếu chính xác, không cho sửa text/ID/nhãn gốc để lách bước duyệt.
Formula không được dùng làm quyết định.

- KEEP giữ status/label. Cho phép điền mã REVIEW còn thiếu; đổi mã đã có cần
  CHANGE. KEEP không tự chấp nhận nhãn mà Codex đề xuất.
- CHANGE cần POS/NEG/NEU/REVIEW/EXCLUDE và lý do người gán; REVIEW cần mã hợp lệ.
  REV_OTHER cần giải thích. Các mã không phù hợp với trạng thái bị từ chối.
- DEFER cần lý do, để trống nhãn mới và mã REVIEW. Giữ nguyên nhãn/trạng thái
  gốc và lỗi kỹ thuật còn lại; metadata đánh dấu không được huấn luyện.

Nếu còn ô decision trống hoặc quyết định không hợp lệ, không tạo output dở
dang. Khi đủ, `reviewed/` là snapshot mới đủ 400 dòng với lịch sử 19 sự kiện,
actor/time, guideline/hash, checksum input, giá trị trước/sau và ghi chú.
Snapshot cha và file duyệt được giữ trong provenance. Bản gốc và workbook không
bị ghi đè. Cùng input/actor nhập lại trả về cùng kết quả; input khác phải chọn
output mới bằng `--output`, không ghi đè lịch sử đã có.

`all_human_review_resolved` chỉ được đặt sau khi nhập đủ quyết định hợp lệ.
DEFER là hoàn tất quyết định hoãn, không phải gold sentiment. Baseline kiểm
checksum và phát lại toàn bộ quyết định để đối chiếu dataset/history trước
khi fit; chỉ đổi cờ manifest không mở được. Mọi dòng DEFER, REVIEW hoặc EXCLUDE
đều ngoài supervised train. Các nhóm post/duplicate được tính trên cả 400 dòng,
kể cả dòng ngoài train, để giữ liên kết bắc cầu. Fold được tính lại sau duyệt.

`--run` là hành động fit rõ ràng; file hiện vẫn còn 19 ô trống nên chưa chạy
baseline thật. Sau khi nhập quyết định hợp lệ, lệnh này sẽ xuất
OOF metrics, recall từng lớp, confusion matrix, dự đoán sai và hệ số SVM theo
fold. Accuracy trong metrics chỉ mô tả mẫu phát triển đã chọn, không phải hiệu
năng theo phân phối thực tế. Không tạo hoặc mở test độc lập.

**Đã chạy:** chuẩn hóa local, kiểm checksum/ID/provenance, thống kê, kế hoạch
chia nhóm; fixture kiểm NB/LR/LinearSVC, cả hai biến thể, metrics và chống rò
vocabulary. **Chưa chạy:** train/CV trên 400 dòng thật, so sánh che tên, phân
tích hệ số/dự đoán sai trên nhãn thật, đánh giá phim mới hoặc gold test độc lập.

Lượt chuẩn bị trước: 138/138 test pass; đã đối chiếu 400 dòng Excel/CSV và
checksum nguồn. Lượt hoàn thiện importer bổ sung fixture Excel/CSV, KEEP /
CHANGE / DEFER, thiếu quyết định/mã, dữ liệu bị sửa, tính lặp an toàn, journal
và receipt, checksum guideline bất biến, cùng chạy baseline đủ sáu tổ hợp bằng
fixture sau khi mở khóa hợp lệ. Lượt cuối `python -m unittest discover -s tests`
**145/145 pass** (22,624 giây); `git diff --check` sạch. Workbook local và toàn
bộ input/task giữ nguyên checksum; chưa có quyết định thật mới hoặc model thật.
