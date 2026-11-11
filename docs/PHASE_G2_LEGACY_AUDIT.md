# Phase G.2 — Legacy Dataset Audit & Gold Training Expansion

Ngày 11/11/2026. Kế thừa G.1 `490f01d`, nguồn khóa theo Phase G.

**Audit và task gán nhãn train đã sẵn sàng. Research release vẫn PARTIAL:**
nguồn/quyền sử dụng, ý nghĩa nhãn cũ và độ đa dạng phim chưa xác minh; chưa
có gold mới hoặc independent test. Không crawl thêm, gọi GPT/Claude, train
Transformer, thay guideline/nhãn người hoặc chạy lại E/E.1/E.2.

## 1. Trả lời bằng dữ liệu thật

Đã đọc trực tiếp `G:/dlvb/data_module1.csv`, đối chiếu từng dòng với master
`outputs/phase_g/master/`, SHA-256:
`4cfe4a00d7a95c46909755b3255e7bc504a7728f503f4b30a68abba7ff9b17b7`.
Giữ nguyên byte file nguồn và mọi giá trị `overall`.

| Câu hỏi | Kết quả audit |
| --- | --- |
| Bao nhiêu dòng/text khác nhau? | 29.688 dòng; 29.688 text khác nhau cả nguyên bản và NFC/whitespace/casefold |
| Có phải 29.688 comment Facebook độc nhất? | Không chứng minh được. File không có platform/comment/post identity |
| Bao nhiêu phim/bài xác minh được? | **0 phim, 0 bài, 0 comment ID được xác minh** |
| Nguồn thực có? | Một file người dùng nhận từ bạn; không biết nguồn website/người gán/guideline gốc |
| Có thể dùng bao nhiêu làm ứng viên train? | **28.042 ứng viên có thể đem gán nhãn**, sau chặn component đã tiếp xúc; chưa phải 28.042 nhãn sentiment hợp lệ |
| Đã xác nhận bao nhiêu câu sentiment đúng phạm vi? | Chưa xác định; cần người gán đánh giá. Không thay bằng số keyword match |
| Tạo được independent test từ legacy? | **0 ứng viên đủ bằng chứng** |
| Có cần crawl hàng loạt ngay? | Không để mở rộng train; đã đủ pool cho một task 250 câu. Test 180 vẫn cần chứng cứ nguồn độc lập hoặc nguồn mới sau này |

Không suy ra movie ID từ tên phim/diễn viên xuất hiện trong text. Không lấy
ID số trong cột `id` làm Facebook comment ID. Không khôi phục provenance
bằng text giống nhau rồi coi là cùng người/bài đăng.

## 2. Schema, nhãn cũ và tình trạng text

Schema đúng ba cột literal string: `id`, `comment`, `overall`.
Không missing/empty ở cả ba cột, không lặp source ID.

Giá trị nhãn **nguyên gốc viết thường**, không chuyển sang guideline V2.1:

| overall | Dòng |
| --- | ---: |
| pos | 6.794 |
| neg | 6.283 |
| neu | 16.611 |

Tên chuỗi có vẻ giống ba sentiment nhưng **không xác minh được ý nghĩa,
nguồn hoặc phương pháp gán**. Không biết có phải người, luật hay model.
Không nâng thành gold/silver đã xác nhận; không dùng overall để chọn task.
Chỉ cân nhắc weak-supervision experiment riêng sau khi rõ nguồn/định nghĩa.

| Chỉ tiêu text | Kết quả |
| --- | ---: |
| Ký tự min / median / p95 / max | 2 / 78 / khoảng 455 / 6.729 |
| Token khoảng trắng min / median / p95 / max | 1 / 18 / 100 / 1.505 |
| Có token nối `_` | 9.009 |
| Có literal emoji-alias signal theo regex đã khai báo | 220 |
| NFC làm thay đổi chuỗi | 1 |
| Có dấu tiếng Việt | 29.339 |
| Latin không có dấu tiếng Việt | 337 |
| Không có Latin hoặc tín hiệu khác | 12 |
| Có ít nhất một film/aspect cue | 15.914 |

Phân loại ngôn ngữ trên chỉ là tín hiệu Unicode, **không phải language-ID
đã kiểm định**. Không suy ra 337 câu đều tiếng Anh hoặc 12 câu đều rác.
9009 dòng có token `_` và 220 emoji-alias signal là dấu hiệu text có thể đã
qua xử lý; không khẳng định cột comment là nguyên văn Facebook. Không bỏ
underscore, sửa emoji hoặc thay Unicode ở text đưa người gán; mọi transform
chỉ dùng trong phép kiểm tra, giữ `text_view` đúng bằng literal source.

13.774 dòng thiếu keyword phim **không bị coi là unrelated**. Các câu ngắn,
phủ định, mỉa mai/cảm xúc không bị tự xóa. Không có provenance đủ để thống kê
phim hoặc kiểu reply/parent; các ô này để trống, không tự điền theo suy đoán.

## 3. Quality và mức tin cậy

| Nhóm kiểm toán | Dòng |
| --- | ---: |
| VERIFIED_HUMAN_GOLD | 0 |
| LEGACY_LABELED_UNVERIFIED | 29.688 |
| UNLABELED_USABLE | 0 |
| NEEDS_REVIEW | 0 |
| EXCLUDE | 0 |

Đây là trạng thái audit, **không phải sentiment**. Mọi dòng có overall nên
vẫn là legacy-labeled-unverified, dù có thể đem gán lại. UNLABELED_USABLE=0
không có nghĩa không có ứng viên annotation.

Rule chỉ EXCLUDE text rỗng, URL-only hoàn toàn hoặc UI string chính xác
không mơ hồ. Corruption, emoji-only/punctuation-only hoặc advertising cues
được giữ NEEDS_REVIEW; không tự kết luận sentiment/spam. Trên file thật,
**các rule hẹp này không đánh dấu dòng nào**. Điều đó không chứng minh corpus
không có spam, quảng cáo, ngoài miền hoặc thiếu ngữ cảnh; chất lượng ngữ nghĩa
chưa được người xác nhận. Không tuyên bố toàn bộ 29k hợp lệ để train.

Không xóa vật lý dòng nào. Bảng audit đủ 29.688 dòng có source row, source
ID, checksum, literal text, nhãn legacy và mọi cờ; giữ local.

## 4. Duplicate, exposure và tính độc lập

- Raw/exact normalized duplicate excess: **0**.
- Near-duplicate: **192 cặp**, token 3-gram Jaccard ≥ 0,9, tối thiểu 40 ký tự,
  đúng policy Phase G. Số cặp không phải số comment phải xóa.
- Sau nối cả nhóm master cũ và near/exact bắc cầu: 27.859 annotation components
  trên toàn legacy; pool sau chặn còn 27.856 components có ứng viên.
- **3 text trùng nội dung normalized với development**, đánh dấu
  `confirmed_exposed` ở cấp nội dung. **Không phải 3 identity đã ghép chắc**;
  không dùng chúng tính agreement giữa overall và nhãn người.
- **1.646 dòng** nằm trong connected groups master đã tiếp xúc, gồm cả bridge
  qua crawl/export/task/pool. Không có nghĩa mọi dòng đó đã được người đọc.
  Giữ chúng ngoài task mở rộng lần này để tránh lặp dữ liệu đã phát triển.
- Exposure còn lại: **29.685 unknown_exposure**; confirmed_unused_with_evidence=0.
  Thiếu log không được nâng thành unused.
- Không có legacy row thuộc test reservation/quarantine tại thời điểm audit.
  Registry và manifests được đọc, guard được kiểm lại trước xuất task.

Đối chiếu sử dụng 400 quyết định, toàn bộ group/variant graph master và nguồn
exposure đã lưu trong master từ crawl/export/selection histories. Những nguồn
ngoài workspace hoặc lịch sử không được ghi lại vẫn chưa biết. Không suy ra
nguồn từ nội dung câu hoặc tìm comment thật qua search/API.

**Agreement pairs chắc identity = 0**, vì legacy không có comment/post ID.
Không tính accuracy/Kappa dựa trên ghép text mơ hồ. Metadata khôi phục = 0.
Ngay cả các component không nối development cũng chưa đủ chứng minh độc lập
theo bài; không random lấy 180 câu cũ để gọi independent test.

## 5. Task train thật: 250 câu, mọi nhãn để trống

File giao người gán:
**`G:/dlvb/cmt-tag/outputs/phase_g2/annotation_task/legacy_train_candidates.xlsx`**.
SHA-256:
`bd9673c530dc2a5a7f873ed23a0abc958a11e979fc2f4975b2a85578b4ea891c`.

Sáu cột duy nhất: `id,text_view,status,label,review_reason,reason`.
Một sheet nhìn thấy, wrap text, cố định header, dropdown cho quyết định.
Không có nhãn legacy/model/prediction/confidence, source, movie, cohort hoặc
metadata ẩn. `text_view` là nguyên chuỗi comment trong file legacy, không
phải xác nhận nguyên văn mạng xã hội.

Seed **20261111**, mỗi connected/near-duplicate component chỉ một ứng viên.
Không dùng overall để stratify hoặc chọn mẫu:

| Phương pháp chỉ phục vụ train annotation | Câu |
| --- | ---: |
| Ngẫu nhiên từ component representatives | 125 |
| Tín hiệu từ vựng tích cực, chưa phải POS | 62 |
| Câu hỏi/thông tin, chưa phải NEU | 41 |
| Phủ định/mixed/sarcasm cues, chưa phải nhãn | 22 |

Các bucket là rule công khai có kiểm soát, không phải dự đoán/ground truth.
Ties xáo bằng seed. Không ép nhãn POS/NEG/NEU cuối cùng. Không thể target POS
ngoài Mưa Đỏ hoặc NEG trong Mưa Đỏ theo provenance vì không có movie ID.

**Không bảo đảm quota theo phim hoặc nguồn gốc:** chỉ biết một file và chưa
biết site/bài/phim. Không giả vờ đã lấy mẫu đa phim hoặc cân bằng nguồn. Đây
là hạn chế quan trọng; diversity phải được kiểm tra tiếp khi có provenance,
không sửa metadata bằng tên phim đoán từ text.

Mục tiêu 150–200 sentiment hợp lệ sau duyệt chỉ là kỳ vọng của task, chưa
phải kết quả. Dùng V2.1, người gán quyết định POS/NEG/NEU/REVIEW/EXCLUDE.
REVIEW/EXCLUDE là trạng thái, không ép thành NEU và không bỏ khỏi nguồn gốc.
Tại thời điểm tạo task có **0 nhãn người mới**; cập nhật gán/import bên dưới.
Không dùng các ứng viên hoặc nhãn legacy để tự tạo gold/train model.

Coordinator mapping, source row/label gốc, methods/selected IDs và checksum
nằm riêng tại `annotation_task/coordinator/`. Chỉ giao workbook cho người
gán để tránh nhìn nhãn legacy. Lịch sử nhập sau này tách riêng bất biến.

## 6. Tái lập và nhập sau khi người dùng gán

```powershell
python scripts/audit_legacy_dataset.py --config configs/legacy_audit.json --output <new_audit_dir>
```

Builder `scripts/build_legacy_train_workbook.mjs` dùng bundled
`@oai/artifact-tool`, nhận đúng JSON mù trong audit. Không dùng dependency
repo hoặc gửi text tới API. Sau export:

```powershell
python scripts/finalize_legacy_train_task.py --audit <audit_dir> --workbook <export_dir>/legacy_train_candidates.xlsx --output <new_task_dir>
python scripts/import_legacy_train_annotations.py --task <task_dir> --input <completed_xlsx> --output <new_import_dir> --annotator annotator_a
```

Các thư mục đã bàn giao hiện tồn tại; không chạy đè. Import chỉ sau gán đủ
mọi ID: kiểm literal text, nhãn/status/reason, guard quarantine, source/task
checksum; lưu history/receipt. Cho phép sửa trực tiếp workbook làm việc;
chỉ file đó được miễn so hash mẫu ban đầu lúc import, coordinator và mọi
file hợp đồng khác vẫn bất biến. Đổi ID/text vẫn bị từ chối.
Không lấy nhãn legacy điền ô trống. REVIEW
chưa giải quyết nằm ngoài sentiment dataset, EXCLUDE giữ quyết định. Không
tự gọi output gold hoặc tự train; nguồn/quyền sử dụng và release cần rõ.

Đầu ra thật, local/gitignored:

- `outputs/phase_g2/legacy_audit/legacy_quality_report.json`, `legacy_audit.csv`.
- `near_duplicates.json`, `coordinator_mapping.json`, `selection_manifest.json`,
  `manifest.json`, `workbook_input.json` trong cùng thư mục audit.
- `outputs/phase_g2/annotation_task/legacy_train_candidates.xlsx` và coordinator.
- `outputs/phase_g2/protected_audit/validation.json`.
- Preview và log authoring trong `outputs/phase_g2/workbook_export/` và support.

## 7. Validation và giới hạn thực thi

Đã chạy thật audit 29.688 dòng, nối từng observation với master nguồn đã khóa,
selection 250 câu, export workbook thật, round-trip kiểm đúng 250 ID/text và
mọi quyết định trống. ZIP CRC hợp lệ; không extra sheet/column/formula hoặc
metadata channel. Đã render và xem bố cục worksheet. Chưa có annotation mới
hoặc metric model thật trong phase này.

Bundled Node trên Windows trả native exit code `-1073740791` sau khi export
đã hoàn thành. Vì vậy không coi exit code đó là chứng minh thành công:
Python finalizer kiểm độc lập nội dung/ZIP/privacy, trả 0 và seal task READY.
Đây là hạn chế runtime authoring khi tái lập, không che bằng nhãn/test giả.

Toàn bộ unittest cuối: **235/235 pass**, 40,363 giây. Mốc `659987d` có
221 test; G.1 thêm 6, G.2 thêm 8, gồm cả gán trực tiếp trên workbook làm việc.
Fixture mới phủ quality rules, giữ câu ngắn, near/component dedup,
deterministic sampling không phụ thuộc overall, chặn nhóm không eligible,
không phục hồi identity từ text, header/view và import giữ REVIEW/EXCLUDE.
Fixture G.1 kiểm collection/namespace/quarantine, không browser Facebook thật.

Validator dữ liệu thật PASS: **400 quyết định, 19 review events, 96 tệp bảo
vệ**, raw và artifacts cũ không đổi. Không train/gọi API/crawl để kiểm thử.

## 8. Quyết định tiếp theo

Ưu tiên người dùng gán 250 câu này trước khi mở rộng thu thập train. Sau gán
mới biết số sentiment thực, tỷ lệ ngoài miền và sự nhất quán V2.1; chưa cần
crawl hàng nghìn câu mới hoặc train Transformer ngay.

Independent test vẫn **180 câu**, quota 10/bài, 20/phim không thay. Legacy
hiện có **0 ứng viên đủ bằng chứng**; giữ danh sách Facebook/MoMo làm dự
phòng, không crawler mới và không trộn MoMo vào test Facebook. Chỉ khi khôi
phục provenance thật hoặc chọn/khóa nguồn mới đúng protocol mới giải quyết
được test. Không thay exposure ledger để hợp thức hóa dữ liệu cũ.

## 9. Người dùng hoàn thành 250 quyết định và cho phép thiếu EXCLUDE reason

Ngày 11/11/2026, đã nhập workbook người dùng gán vào
`outputs/phase_g2/human_import_01/`, giữ nguyên toàn bộ lựa chọn:

| Quyết định | Dòng |
| --- | ---: |
| POS | 79 |
| NEG | 77 |
| NEU | 30 |
| EXCLUDE | 64 |
| REVIEW / chưa quyết định | 0 |

**186 sentiment**, 64 EXCLUDE. Người gán xác nhận rõ: “Giữ EXCLUDE, ghi thiếu
lý do”. Cả 64 `reason` vẫn là chuỗi trống, không gán lý do spam/unrelated
hoặc lý do suy đoán khác. History có cờ `exclude_reason_missing` và ghi chú
“Người gán không cung cấp lý do”. Receipt lưu nguyên phê duyệt và các ID
liên quan. Mặc định importer vẫn từ chối reason thiếu; ngoại lệ cần flag và
authorization note riêng. Không sửa guideline hoặc workbook để vượt kiểm tra.

Output giữ `decisions.csv` đủ 250 dòng, tách `sentiment.csv` (186) và
`excluded.csv` (64), có history, receipt, input snapshot và manifest checksum.
ID/text vẫn khớp hợp đồng task. SHA workbook người dùng và snapshot:
`3a50ac3f61f9e23bee0804ec4eafb056676a190dc5578bd8d135535b64063362`.
Không ghi đè file user hoặc snapshot cũ.

Kiểm tra thực tế: output manifest hợp lệ, đủ 64 reason rỗng và 64 audit
notes, phân phối sentiment đúng 79/77/30, hash workbook không đổi. Toàn bộ
tests sau thay đổi **236/236 pass**, 40,552 giây, log
`outputs/phase_g_support/tests_human_import.log`. Có regression test default
strict, từ chối flag khi chưa có authorization note, giữ reason trống và
snapshot nguyên vẹn khi ngoại lệ được duyệt.

Chưa train, merge vào release cũ hoặc tạo independent gold test. Nguồn và
quyền sử dụng legacy vẫn chưa xác minh; 400 quyết định/model artifacts cũ
giữ nguyên. Chỉ code/docs/tests được commit, mọi nhãn thật giữ local.
