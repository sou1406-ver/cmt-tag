# Pilot chất lượng nguồn: 70 fanpage + 130 group

Hai người gán **độc lập**, mỗi người 200 dòng:

- Người A chỉ dùng `annotator_a.csv` hoặc bản `.xlsx` tương ứng nếu đã tạo.
- Người B chỉ dùng `annotator_b.csv` hoặc bản `.xlsx` tương ứng nếu đã tạo.
- Không trao đổi nhãn, xem file của người còn lại, nhãn luật hoặc dự đoán máy trước khi nộp.
- Thư mục `coordinator/` dành cho người điều phối; không đưa cho người gán trước khi hoàn tất.

Theo [guideline V2.0](../../../docs/guidelines/MOVIE_SENTIMENT_V2_0.md).
Giữ nguyên `id`, `movie_id`, `text_raw`; chỉ điền bốn cột cuối:

Có một comment bắt đầu bằng emoticon `=))`. Sửa CSV trong VS Code, hoặc nhập
vào Excel với kiểu Text để giữ nguyên chuỗi này; không sửa text để né việc Excel
tự hiểu dấu `=` là công thức. CLI sẽ từ chối text bị thay đổi.

| status | label | review_reason | reason |
|---|---|---|---|
| LABELED | POS / NEG / NEU | để trống | căn cứ ngắn từ comment |
| REVIEW | để trống | REV_MIXED / REV_SARCASM / REV_TARGET / REV_CONTEXT / REV_OTHER | lý do cần xem xét |
| EXCLUDE | để trống | để trống | lý do ngoài phạm vi/rác/không đọc được |

CLI hiện hỗ trợ năm mã REVIEW trong bảng. Nếu cần lý do chi tiết khác trong
guideline, dùng `REV_OTHER` và ghi chi tiết vào `reason`. Không coi REVIEW hoặc
EXCLUDE là lớp sentiment. Không mặc định khóc/buồn là NEG. Thiếu ngữ cảnh trả
lời thì dùng REVIEW phù hợp, không tự tìm thêm bài trên mạng.

Tất cả mẫu thuộc phim Mưa Đỏ; file gán không có nguồn, URL, tên tác giả hoặc
gợi ý nhãn. Nội dung tự do có thể tự tiết lộ nguồn; phần mềm không chứng minh
được rằng người gán thực sự làm độc lập. Thứ tự A/B khác nhau; luôn ghép theo ID.

## Chuẩn hóa file gán trước khi import

Sau khi gán xong, có thể dùng bước chuẩn hóa độc lập; importer Phase C giữ nguyên:

```powershell
python scripts/normalize_annotations.py --input data/tasks/source_quality_pilot_20261110/annotator_a.csv --task data/tasks/source_quality_pilot_20261110/coordinator/task.json --output data/annotations/source_quality_pilot_20261110/a_normalized_v1
```

`--input` nhận CSV hoặc XLSX; nếu gán trong Excel, trỏ tới chính workbook đã lưu.
Script điền `LABELED` khi đã có POS/NEG/NEU, hoặc chuyển REVIEW/EXCLUDE từ cột
`label` sang `status` và để `label` trống. Không suy ra sentiment từ comment,
không viết hộ lý do, không mặc định mã REVIEW khi người gán chưa chọn.

`normalized.csv` giữ toàn bộ ID, text và quyết định, dùng làm đầu vào
`import-human` với **task đầy đủ**. `sentiment_candidates.csv` chỉ chứa các dòng
LABELED có POS/NEG/NEU hợp lệ. `review.csv` và `exclude.csv` giữ riêng hai trạng
thái ngoài ba lớp; `pending.csv` chỉ xuất khi còn dòng chưa xác định hợp lệ.
Không đưa file subset vào `import-human` với task 200 ID vì importer kiểm đủ ID.

`original_input.csv` và `normalization_report.json` lưu đầu vào, checksum, mọi
thay đổi chuẩn hóa và lỗi. Thiếu nhãn, thiếu mã REVIEW, trường mâu thuẫn hoặc
text bị sửa làm `import_ready=false`, CLI trả mã 2; không xóa dòng để né lỗi.
Lý do tự do `reason` được giữ nguyên; importer hiện không bắt buộc trường này.

`--restore-task-whitespace` chỉ khôi phục text từ task khi các token cách nhau
bởi khoảng trắng giống hệt nhau, và ghi lại từng thay đổi. Thay đổi từ ngữ vẫn
bị chặn. `--overrides` nhận JSON bổ sung do người gán xác nhận, ghép theo ID,
có giá trị trước/sau và bằng chứng; không dùng để tự đoán nhãn còn thiếu.

Mỗi lần chạy phải dùng thư mục output mới, không ghi đè file gán gốc hoặc kết
quả cũ. Output nhãn người giữ local. Bước này không tạo gold, không chạy train,
không thay đổi split; vẫn cần người B để tính agreement/Kappa cho pilot.

## Lấy mẫu và phạm vi kết luận

Seed 42, chọn không hoàn lại 70/1.538 dòng fanpage và 130/141 dòng group.
Pool group là snapshot mới sau bản vá link `/groups/<số>/user/<số>/`, gồm hai
bài Mưa Đỏ. Cả hai pool giữ cùng điều kiện export: có ID, văn bản đầy đủ và
không rỗng sau bỏ node mention; không lọc theo sentiment, độ dài hoặc nhãn luật,
không loại trùng text trước khi lấy mẫu. Emoji còn nguyên.

`coordinator/selection_manifest.json` ghi pool checksum, ID được chọn, strata,
quota và seed. `coordinator/task.json` dùng đúng định dạng import/agreement
Phase C và data_version thật `6cdc0e41154d05c1ff86` từ prepare-data. Bản chuẩn bị
riêng nằm local dưới `outputs/source_quality_pilot_20261110/prepared/`; chỉ có
reservation train để làm audit, không tạo holdout hoặc đổi split hiện có.
Mọi mẫu đã chọn đều được gán để đánh giá chất lượng, kể cả khi chuẩn bị dữ liệu
đánh dấu trùng text. Đây chưa phải release gold để huấn luyện/đánh giá.

So sánh này mô tả các bài đã chọn, cùng một phim; một bài fanpage và hai bài
group chưa đủ để kết luận nhân quả cho toàn bộ loại nguồn. Tỷ lệ usable được
tính trên các bản export văn bản, không bao gồm dòng rỗng/không đầy đủ bị loại
trước export. Không gộp hai tỷ lệ nguồn thành ước lượng phân phối thực tế.

Các ID pilot và các nhóm bài/trùng lặp liên thông của chúng phải được xem là
đã dùng cho phát triển, loại khỏi test độc lập tương lai theo quy tắc group
isolation hiện có. Chưa sửa hoặc đóng băng manifest train/dev/test chính thức.

## Import và agreement bằng CLI hiện có

Chạy từ thư mục gốc repo, **sau khi hai người gán xong**:

```powershell
New-Item -ItemType Directory -Force data/annotations/source_quality_pilot_20261110 | Out-Null
python -m src.annotation import-human --task data/tasks/source_quality_pilot_20261110/coordinator/task.json --csv data/tasks/source_quality_pilot_20261110/annotator_a.csv --annotator person_a --blind --output data/annotations/source_quality_pilot_20261110/a.jsonl
python -m src.annotation import-human --task data/tasks/source_quality_pilot_20261110/coordinator/task.json --csv data/tasks/source_quality_pilot_20261110/annotator_b.csv --annotator person_b --blind --output data/annotations/source_quality_pilot_20261110/b.jsonl
python -m src.annotation agreement --left data/annotations/source_quality_pilot_20261110/a.jsonl --right data/annotations/source_quality_pilot_20261110/b.jsonl --output data/agreement/source_quality_pilot_20261110
```

Dùng hai ID người gán khác nhau. `--blind` là xác nhận của người vận hành.
CSV trống hiện tại bị CLI từ chối; không có nhãn người, gold hoặc Kappa thật.
Output `agreement.json` chia riêng cohort `fanpage` và `group`, gồm agreement,
Cohen's Kappa trên POS/NEG/NEU/REVIEW/EXCLUDE và số cặp sentiment. Kappa null
khi marginals suy biến, không diễn giải thành 1.

## Adjudication và tỷ lệ dùng trực tiếp

Người điều phối xem `disagreements.jsonl`, phân xử bất đồng và giải quyết REVIEW
theo guideline. Chuẩn bị `adjudicated.csv` đủ 200 ID, giữ nguyên text; các dòng
đã thống nhất chỉ giữ nhãn khi người phân xử đã kiểm tra. Ghi lý do quyết định.

```powershell
python -m src.annotation import-human --task data/tasks/source_quality_pilot_20261110/coordinator/task.json --csv adjudicated.csv --annotator adjudicator --blind --adjudication --output data/annotations/source_quality_pilot_20261110/adjudicated.jsonl
```

Không gọi `release` để mở Phase D trong nhiệm vụ pilot này. Khi đã phân xử,
báo cáo **riêng từng nguồn**: N, số POS/NEG/NEU/EXCLUDE/REVIEW, số bất đồng,
agreement/Kappa trước phân xử, và số REVIEW còn lại. Công thức usable:

- Fanpage: `(POS + NEG + NEU sau phân xử) / 70`.
- Group: `(POS + NEG + NEU sau phân xử) / 130`.

Nếu còn REVIEW, ghi rõ đây là tỷ lệ dùng được hiện tại, chưa phải tỷ lệ cuối
cùng sau xử lý toàn bộ. Không thay kết quả người gán bằng nhãn luật hoặc LLM.
