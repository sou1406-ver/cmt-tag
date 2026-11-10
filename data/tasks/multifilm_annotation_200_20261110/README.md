# Đợt gán chính: 200 bình luận đa phim

Đợt này gồm **200 câu, 25 phim theo chủ đề bài nguồn, 36 bài viết**. Một phim
chiếm nhiều nhất 14 câu, một bài nhiều nhất 14 câu. Đây là dữ liệu gán nhãn
để phát triển và bổ sung train sau khi được kiểm tra, chưa phải gold/test.

## Hai đợt có mục đích khác nhau

| Đợt | Mục đích | Xử lý hiện tại |
|---|---|---|
| [200 Mưa Đỏ vòng đầu](../source_quality_pilot_20261110/README.md) | Pilot kiểm tra nguồn, guideline và cách gán | Giữ nguyên file gốc và lịch sử; kết quả chuẩn hóa giữ local |
| 200 đa phim này | Bổ sung cách diễn đạt và đánh giá từ nhiều phim/bài | Gán mới bằng một người; không tự gộp vào train hoặc test |

Không mặc định 400 dòng là 400 mẫu sentiment dùng được. Chỉ LABELED có
POS/NEG/NEU hợp lệ mới là ứng viên train. REVIEW chưa giải quyết và EXCLUDE
vẫn giữ để audit, nằm ngoài train sentiment ba lớp.

## Cách chọn mẫu đã chốt

- **120 mẫu ưu tiên:** đọc và chọn các câu có dấu hiệu phê bình về nội dung,
  nhân vật, diễn xuất, nhịp kể, hình ảnh/âm thanh và trải nghiệm xem. Có cả
  cách nói không dùng các từ “dở/tệ/chán”, trường hợp phủ định, phản bác hoặc
  tường thuật lời chê. Đây là tiêu chí truy hồi, không phải nhãn NEG.
- **80 mẫu ngẫu nhiên:** lấy không hoàn lại từ phần dữ liệu group công khai
  còn lại, phân tầng theo chủ đề phim và bài viết. Phân bổ gần đều giữa phim,
  rồi giữa các bài trong phim; phần dư theo thứ tự xáo bằng seed `20261110`.
  Không lọc 80 mẫu này theo từ khóa sentiment, điểm luật, độ dài hoặc nhãn dự
  kiến; không đổi mẫu sau khi xem nhãn để có tỷ lệ đẹp hơn.
- Hai nhóm loại trừ nhau. Trước khi lấy mẫu, loại ID/trùng text chính xác với
  pilot cũ và các mẫu đã chọn. Chỉ dùng text đầy đủ, không rỗng; giữ nguyên
  dấu câu, emoji, chính tả và xuống dòng. Không cắt tên bằng heuristic.
- Trộn thứ tự 200 dòng với seed `20261111`. File người gán không có cohort,
  điểm truy hồi, nhãn máy, nguồn bài hoặc gợi ý riêng cho từng dòng.

Đây là lấy mẫu có chủ đích kết hợp ngẫu nhiên có phân tầng, **không phải mẫu
ngẫu nhiên đều của toàn bộ Facebook**, không đại diện phân phối ngoài thực tế.
Không ép tỷ lệ POS/NEG/NEU. Mẫu ngẫu nhiên có thể ngoài lề, thiếu ngữ cảnh hoặc
chỉ có emoji; người gán sử dụng REVIEW/EXCLUDE khi phù hợp, không xóa dòng.

`coordinator/selection_manifest.json` ghi quota, seed, pool checksum, nguồn,
parent/post/comment ID và cohort. `random_pool_manifest.json` chứa danh sách
ID/tầng trước khi lấy 80 mẫu. Có thể kiểm lại lựa chọn mà không đọc nhãn:

```powershell
python data/tasks/multifilm_annotation_200_20261110/coordinator/replay_random.py
```

Snapshot text đầy đủ của pool và journal raw giữ local; các `input_*.csv`
chứa đúng 200 text đã chọn để chuẩn bị lại task bằng pipeline hiện có.
`movie_id` là **chủ đề bài nguồn**, không bảo đảm mọi bình luận chỉ nói về phim
đó: có câu so sánh phim/phần khác. Cần tính cả liên hệ này khi thiết kế holdout
theo phim sau này; không diễn giải số phim như 25 đối tượng đánh giá độc lập.

## File để gán

Dùng `annotator_a.xlsx` được tạo local, hoặc template `annotator_a.csv`.
Chỉ cần một người (`person_a`), không có file B bắt buộc và không tính Kappa
giữa hai người khi chưa thực sự có người thứ hai gán độc lập.

Giữ nguyên `id`, `movie_id`, `text_raw`. Bốn cột vàng là phần được điền:

| status | label | review_reason | reason |
|---|---|---|---|
| LABELED | POS / NEG / NEU | trống | Căn cứ ngắn nếu cần |
| REVIEW | trống | REV_MIXED / REV_SARCASM / REV_TARGET / REV_CONTEXT / REV_OTHER | Lý do chưa chốt |
| EXCLUDE | trống | trống | Lý do ngoài phạm vi/rác nếu cần |

Có thể chỉ điền POS/NEG/NEU/REVIEW/EXCLUDE trong cột `label` như đợt trước;
script chuẩn hóa sẽ chuyển đúng trạng thái. REVIEW vẫn phải có mã. Theo
[guideline V2.0](../../../docs/guidelines/MOVIE_SENTIMENT_V2_0.md), không lấy từ
“khóc/buồn”, tên phim, ý kiến người khác hoặc emoji làm nhãn mặc định.
Nếu thiếu ngữ cảnh, dùng REVIEW; không đoán hoặc tự tìm thêm trên mạng.

Workbook có wrap text, filter, cố định hàng tiêu đề/cột định danh và dropdown.
Comment được lưu như text, kể cả chuỗi bắt đầu bằng `=`. CSV nhập vào Excel
phải chọn kiểu Text để không làm biến dạng ID hoặc nội dung.

Sau khi lưu workbook:

```powershell
python scripts/normalize_annotations.py --input data/tasks/multifilm_annotation_200_20261110/annotator_a.xlsx --task data/tasks/multifilm_annotation_200_20261110/coordinator/task.json --output data/annotations/multifilm_annotation_200_20261110/a_normalized_v1
```

Khi `import_ready=true`, dùng **normalized.csv đủ 200 ID** với importer hiện có:

```powershell
New-Item -ItemType Directory -Force data/annotations/multifilm_annotation_200_20261110 | Out-Null
python -m src.annotation import-human --task data/tasks/multifilm_annotation_200_20261110/coordinator/task.json --csv data/annotations/multifilm_annotation_200_20261110/a_normalized_v1/normalized.csv --annotator person_a --output data/annotations/multifilm_annotation_200_20261110/a.jsonl
```

Lệnh trên không tự khẳng định gán mù. Chỉ thêm `--blind` nếu người vận hành
thực sự xác nhận quy trình đó; một cờ không tạo ra người gán thứ hai. Nhãn
người và workbook đang gán giữ local. Mỗi lần chuẩn hóa dùng output mới.

## Sau khi gán xong

Đếm nhãn thật, REVIEW/EXCLUDE, tỷ lệ dùng được và độ phủ theo phim/bài/cohort.
Chưa cắt POS, giảm mẫu Mưa Đỏ hoặc tự đặt hạn ngạch train trước khi có kết quả.
Không gọi 200 mẫu pilot dùng phát triển guideline là gold test độc lập.

Nếu mở thực nghiệm sau này: giữ comment cùng bài và nhóm gần trùng trong một
split; test độc lập không được chọn theo dấu hiệu NEG. Có thể thêm test cân
bằng riêng để phân tích lớp, nhưng phải ghi rõ cách lấy mẫu và giới hạn.
Thêm đánh giá giữ riêng phim chưa có trong train nếu đủ phim và số mẫu.

So sánh TF-IDF + SVM với text gốc và bản che tên phim/nhân vật là một thực
nghiệm dự kiến, không mặc định che tên tốt hơn. Từ điển/quy tắc che tên phải
được thiết kế trước khi xem test; không đổi text gốc. Báo Macro-F1, per-class
precision/recall/F1, recall NEG và phân bố/số mẫu hỗ trợ của từng test. Kiểm
tra đổi tên phim trong cùng một câu là phép thử shortcut bổ sung, không thay
thế đánh giá trên dữ liệu thật. Class weight và Macro-F1 không tự khử thiên lệch.

Đợt này không train, không tạo release gold, không sửa guideline, importer,
pipeline ML, dữ liệu pilot hoặc split/Phase B hiện có. Mọi nguồn đã dùng cho
truy hồi/đọc chọn được ghi là đã tiếp xúc để phát triển; cần tách khỏi test
độc lập tương lai theo bài và nhóm trùng liên thông.
