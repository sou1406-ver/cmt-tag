# Phase I.4.1 — Hợp đồng normalization plain_text_v3_1

Patch tạo **đề xuất** từ `text_raw`, dùng lại thành phần I.3 và token roundtrip
offline đã khóa. Không dùng `overall` legacy để biến đổi hoặc chọn nhãn.
`text_clean`, `text_annotation`, human decisions và các artifact cũ được giữ nguyên.
`text_normalized` là field mới; chưa có lệnh tự kích hoạt nó làm annotation input.

## Quy tắc

1. Mask URL, email, mention, hashtag, code, số thập phân/ngày tháng và tên file
   kỹ thuật trước entity repair và thành phần I.3; khôi phục đúng chuỗi gốc.
2. Sửa entity bị tách chỉ với tên xác định `quot/amp/lt/gt/apos` hoặc numeric
   quote 39/34. Entity thiếu `;` chỉ nhận tên chính xác và ranh giới rõ.
   Decode tên HTML5 hợp lệ; numeric chỉ dùng whitelist ký tự định dạng.
   Tối đa bốn lượt/entity; chuỗi quá sâu giữ nguyên và flag. Unknown entity và
   dấu `&` thông thường được giữ; không dùng prefix match để đoán entity.
3. Dùng I.3 raw-to-plain: NFC, whitespace, lexical rules, alias đã biết và
   accepted roundtrip tokens. Không chạy segmenter mới hoặc thêm dictionary lớn.
4. Bổ sung `con_gái` được người dùng xác nhận, với ngữ cảnh tiếng Việt.
   Recovery theo function word chỉ áp dụng legacy, token có shape Vietnamese
   lowercase 2–4 phần, có thành phần chức năng rõ và bản ghi chứa ít nhất hai
   token segmentation khác nhau trong lexical/roundtrip inventory có sẵn.
   Đây là evidence định dạng, chưa phải xác nhận đúng nghĩa của từng dòng.
   Tên/shape mơ hồ được giữ; chữ hoa không là bằng chứng để tự tách tên.
5. Bảng `configs/abbreviations_v3_1.json`: lowercase whole-token
   `ko/khum/hok → không`, `đc → được`, `cx → cũng`, chỉ ở hai nguồn đã audit
   và có ngữ cảnh tiếng Việt. `k/dc/mn/j/z/bt` chỉ flag review. Giữ
   `t/m/vl/vcl/vch`. Có thể tắt nhóm auto hoặc review_flags trong bảng.
6. Chỉ bỏ whitespace trước dấu câu đơn. Bảo vệ quote, emoticon, dấu lặp,
   số/ngày, URL và code. Không đổi ký tự dấu câu, lowercase hay bỏ stopwords.
   Dấu nháy đôi/curly/angle không cân bằng làm các rule bổ sung ở bước 4–6
   abstain trên cả dòng. Thành phần I.3 vẫn được dùng và có event riêng.
7. Chạy tới fixed point tối đa bốn lượt toàn pipeline, từ chối output chưa
   ổn định. Entity quá sâu luôn giữ nguyên nên không vượt giới hạn bằng lượt sau.

Events gồm rule, before/after, stage, offset trong stage và pipeline_pass.
Offset sau khi rewrite không được diễn giải thành tọa độ raw. Flags và
`remaining_format_tokens` giữ những trường hợp chưa chứng minh được cách sửa.
`HIGH_CONFIDENCE_PROPOSAL` là mức evidence rule, không phải approval người.

## Chạy và tái lập

Từ root repo với môi trường Python hiện có:

```powershell
python scripts/prepare_final_normalization.py
python -m unittest discover -s tests
```

Config: `configs/phase_i4_1.json`. Mặc định output bất biến
`outputs/phase_i4_1/v2/`. Nếu tồn tại, chọn `--output` mới; không ghi đè.
Input là corpus I.3 v3 và accepted token file đã có local; checkout Git không
tự chứa dữ liệu. Manifest kiểm checksum input, code, bảng rule và config;
snapshot bảo vệ các phase trước, master, nhãn và guideline.

Workbook builder `scripts/build_final_normalization_workbook.mjs` cần bundled
`@oai/artifact-tool`, chạy trong authoring workspace có dependency này:

```powershell
node build.mjs outputs/phase_i4_1/v2/workbook_input.local.json outputs/phase_i4_1/workbook_v2
```

`build.mjs` là bản sao nguyên văn builder trong isolated authoring directory;
hai đường dẫn input/output phải được resolve từ root repo. Không chạy builder
vào folder đã tồn tại. Sheet chính chỉ một bản text; sheet phụ giữ raw/I.3/new
và events chia nhiều ô khi cần, không truncate. Text cell được ghi literal;
validator từ chối formula, ID lặp/thiếu, text/evidence bị đổi hoặc quyết định sai.

## Duyệt và import

Mở `outputs/phase_i4_1/workbook_v2/final_normalization_review_150.xlsx`.
Chỉ điền D/E trong Review: `ACCEPT`, `REJECT` hoặc `UNSURE` và note.
Đây là kiểm phép biến đổi, không gán sentiment/domain. Text dài giữ đủ;
dùng F2 hoặc mở thanh công thức để đọc phần vượt chiều cao hiển thị.

```powershell
python scripts/import_final_normalization_review.py --input outputs/phase_i4_1/workbook_v2/final_normalization_review_150.xlsx --output outputs/phase_i4_1/human_review_01
```

Importer yêu cầu đủ 150 quyết định, xác minh toàn bộ nội dung với coordinator
và chỉ lưu ledger bất biến `HUMAN_NORMALIZATION_REVIEW_IMPORTED_NOT_CORPUS_APPROVAL`.
Ngay cả 150 ACCEPT cũng không tự duyệt toàn corpus hoặc cập nhật pointer.
Mẫu targeted không dùng để ước lượng accuracy toàn population.

`PENDING_HUMAN_NORMALIZATION_APPROVAL` độc lập với format I.3 và domain I.4.
Không chuyển approval/checksum cũ; không tạo pilot chính thức, model adapter,
train input hoặc gọi dịch vụ bên ngoài trong patch này.
