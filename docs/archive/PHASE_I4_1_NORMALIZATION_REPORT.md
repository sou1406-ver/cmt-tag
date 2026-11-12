# Phase I.4.1 — Final Vietnamese Text Normalization Patch

## Kết quả và trạng thái

Đã tạo đề xuất `plain_text_v3_1` từ **39.842 raw records**, gồm 10.154 Facebook
và 29.688 legacy chưa xác minh. **13.804 dòng khác I.3** (Facebook 1.763,
legacy 12.041). Không ghi đè raw, `text_clean`, `text_annotation`, 650 human
decisions hoặc 532 sentiment labels. Không crawl, train, gọi LLM, tạo sentiment
hay phát hành pilot. Kết thúc ở **PENDING_HUMAN_NORMALIZATION_APPROVAL**.

Bản dùng để duyệt là `outputs/phase_i4_1/v2/` và
`outputs/phase_i4_1/workbook_v2/final_normalization_review_150.xlsx`.
Bản v1 là draft audit trước guard quote không cân bằng, được giữ để truy xuất;
không dùng số liệu draft thay cho kết quả dưới đây.

## Truy nguyên lỗi

| Signal (số records, không phải số lỗi chắc chắn) | Facebook raw / I.3 | Legacy raw / I.3 |
| --- | ---: | ---: |
| Entity bị tách thuộc pattern audit | 0 / 0 | 404 / 404 |
| `ko/khum/hok/đc/cx` whole-token | 1.306 / 1.306 | 3.152 / 3.152 |
| Whitespace trước dấu câu | 1.448 / 1.448 | 9.715 / 9.714 |
| Entity chuẩn thuộc pattern audit | 0 / 0 | 0 / 0 |

Entity hỏng và viết tắt đã có trong raw, không phải do patch tạo ra. Surface
punctuation signal gồm cả emoticon có dụng ý; không coi tất cả là lỗi.
Các dạng entity chuẩn/nested được kiểm thử bằng fixture, không giả nhận chúng
xuất hiện trong corpus thực. Pattern tách phổ biến là nhóm quote legacy;
bảng pattern đầy đủ và tần suất nằm local ở `source_patterns.local.csv`.
Không đủ bằng chứng xác định tên tokenizer hay upstream processor của legacy.

## Biến đổi thực tế

Các cột dưới là **số transformation events**, không phải số dòng độc lập.
Entity split repair và decode có thể là hai event trên cùng một occurrence.

| Rule | Facebook | Legacy | Tổng |
| --- | ---: | ---: | ---: |
| Khôi phục compound đã xác nhận `con_gái` | 0 | 62 | 62 |
| Function-word segmentation recovery | 0 | 534 | 534 |
| HTML split repair | 0 | 1.067 | 1.067 |
| HTML decode | 0 | 1.067 | 1.067 |
| `ko → không` | 1.327 | 3.615 | 4.942 |
| `khum → không` | 34 | 38 | 72 |
| `hok → không` | 12 | 35 | 47 |
| `đc → được` | 524 | 1.233 | 1.757 |
| `cx → cũng` | 59 | 147 | 206 |
| Single-punctuation spacing | 1.124 | 33.062 | 34.186 |

Bổ sung khôi phục **596 occurrences** trong inventory 12.264 token I.3 chưa
phân giải, tính bằng giao Counter giữa token cũ và event recovery mới. Không
lấy chênh lệch residual inventory để nhận là số token khôi phục: bộ đếm mới
loại protected regions/quotes và có đơn vị khác.

Phân loại bảo thủ inventory I.3 (occurrences): 10.645 shape candidate cần
evidence thêm, 1.518 unknown, 94 ambiguous/name-like cần review, 7 known emoji
aliases. Không gọi toàn bộ 10.645 candidate là compound hợp lệ. Inventory này
đã loại technical identifiers/protected regions từ I.3; URL/email, username,
mention, hashtag và code được kiểm riêng từ raw và bảo vệ, không ép vào nhóm
compound. Không có tên riêng nào được xác nhận chỉ từ chữ hoa.

Sau patch còn **10.561 unprotected format-token occurrences trong 4.782 dòng**.
Nếu đếm mọi whitespace token chứa `_`, gồm cả protected identifier/URL/code,
con số là **11.701**. Các số này không đồng nghĩa lỗi cần sửa. Inventory cũ có
shape, known-alias flag và tần suất ở `i3_remaining_token_inventory.local.csv`;
không tự coi shape candidate là compound đã xác nhận. Tên riêng, username,
hashtag, URL, code và alias/unknown mơ hồ được giữ để review.

7.800 dòng được flag nguy cơ cần kiểm tra nghĩa theo rule/uncertainty;
16.645 dòng có thay đổi, flags hoặc residual nên được đề xuất human review.
Đây là **screening heuristic**, không phải 7.800 lỗi nghĩa được phát hiện.
Các trường hợp ambiguous abbreviation, quote hỏng, entity quá sâu và tên thiếu
evidence vẫn được giữ. Bảng rule không cố ép `mn/bt/k/...` sang một nghĩa.

## Duplicate và cách ly

Đếm duplicate trên view normalized tạm, giữ nguyên ID và duplicate fields cũ:
36.138 exact groups, 3.704 duplicate rows ngoài representative; 28 nhóm mới
gộp các exact groups I.3. Có 521 direct near edges liên quan 1.027 rows,
trong đó 6 cặp mới so với I.3. Không tự xóa/gộp records hay đổi split.
Không có nhóm exact normalized chứa nhãn sentiment người mâu thuẫn.

Near duplicate dùng token 3-shingle Jaccard ≥0,9, từ 40 ký tự; bỏ shingles có
document frequency >256 (2.034 shingles). Vì vậy chưa chứng minh phát hiện
mọi near duplicate. Review loại các ID test/planned-test, toàn bài test đã
quarantine, 40 ID quality holdout I.4, exact groups cũ/mới và direct neighbors.
Không xem việc thiếu metadata legacy là bằng chứng độc lập test.

## Workbook và approval

150 ID duy nhất: **42 Facebook + 108 legacy**, có **10 unchanged controls**.
Lấy mẫu targeted với seed 20261117, neo theo nhóm rule, nguồn, phủ định,
text dài và nhiều thay đổi; sau đó round-robin nguồn/nhóm. Không phải mẫu
ngẫu nhiên đại diện corpus và không dùng tỷ lệ ACCEPT để tuyên bố chất lượng
toàn bộ. Sheet chính không hiển thị lặp ba phiên bản; sheet đối chiếu giữ đủ
raw, I.3, normalized và events, không truncate.
Các nhóm chồng lấp: underscore 36, HTML 37, abbreviation 53, punctuation 88;
có 58 dòng mang signal phủ định và 7 dòng dài hơn 1.000 ký tự.

File Excel đã kiểm tra dữ liệu với coordinator, render cả ba sheet và mở
read-only bằng Excel: 3 sheets, 150 data rows, filter table, freeze header và
dropdown đúng. Toàn bộ human_decision/human_note để trống. Importer từ chối
workbook chưa hoàn thành và mọi sửa ID/text/evidence; import đủ chỉ tạo ledger.

Workbooks format I.3 và domain I.4 hiện vẫn **200 BLANK mỗi file**. Giữ
`PENDING_HUMAN_FORMAT_APPROVAL` và `PENDING_HUMAN_DOMAIN_REVIEW`; không tự
chuyển approval sang version mới, không cập nhật `text_annotation`.

## Kiểm chứng và giới hạn

Unit tests và full-corpus checks bao phủ entity chuẩn/nested/split/depth,
whole-token/source gate, quoted abbreviation, tên/identifier/URL/code,
phủ định, slang, emoticon/Unicode, text dài, fixed point, workbook tamper,
immutable review ledger và không tự approval. Manifest và protected snapshots
giữ các artifact I/I.1/I.2/I.3/I.4, E/H, master, nhãn và guideline.
Lệnh `python -m unittest discover -s tests` chạy **317 tests: 316 pass,
1 skipped**, không lỗi. Gồm 15 tests mới cho patch/workbook. Full-corpus
verification tái dựng từ raw và kiểm idempotence đủ 39.842 dòng, đối chiếu
human decisions/labels/pointer cũ; 156 file bảo vệ khớp SHA-256. Số token
phủ định đã có và emoji codepoint đã có bị mất so với I.3 đều bằng 0.
Đây là kiểm toàn vẹn ký tự/token, không chứng minh mọi ngữ nghĩa được giữ.
Holdout IDs và duplicate exclusions của review được kiểm riêng; import blank
bị chặn mà không tạo folder output. Kết quả aggregate/manifest ở
`outputs/phase_i4_1/verification_v1/`.

Chưa có human validation cho patch; không tuyên bố tất cả phép đổi đúng hoặc
sentiment ngoài fixture được bảo toàn tuyệt đối. Những rule lexical/contextual
vẫn có thể nhầm trong câu đặc biệt; người dùng cần duyệt workbook và trường
hợp khó trước khi chốt phiên bản. Số token thay chỉ đo khối lượng thay đổi.

Code/config/spec nằm Git; comment, IDs, before/after, workbook và manifests
chi tiết chỉ local/gitignored. [Hướng dẫn rule, tái lập và import](../PHASE_I4_1_NORMALIZATION_SPEC.md).
