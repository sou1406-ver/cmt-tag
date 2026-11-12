# Canonical rebuild readiness — 12/11/2026

Candidate cleaning mới `plain_text_v3_2` đã được kiểm full-corpus, vẫn pending:
raw/nhãn giữ nguyên, pool8.812/approved0, 47 REJECT chưa có approval mới.
[Bảng before/after và giới hạn DOM](CLEANING_V3_2_REPORT.md). Bảng dưới là
canonical v3.1 baseline, không gắn các số này cho v3.2 hoặc coi corpus đã duyệt.

**REBUILD_VERIFIED / QUALITY_REVIEW_PENDING; 0 approved.** Các số liệu Phase J
bên dưới là snapshot lịch sử, không phải trạng thái mới nhất.

Nguồn legacy: `G:/dlvb/data_module1.csv`, UTF-8 BOM, 29.688 dòng, các cột
`id,comment,overall`; SHA-256
`4cfe4a00d7a95c46909755b3255e7bc504a7728f503f4b30a68abba7ff9b17b7`.
Không xác minh được platform/movie/post hoặc phương pháp tạo `overall`.
Kiểm tra đồng thời vị trí **28.489–29.688** (data rows, không tính header) và
ID liên tục **30513–31712** trước khi loại 1.200 dòng. Không áp dụng ID này
cho nguồn khác. Exclusion ledger giữ lý do SUSPECTED_TEMPLATE_BLOCK, raw/hash,
provenance và 8 quyết định người; raw gốc không bị sửa/xóa.

| Chỉ số | Trước | Sau rebuild |
| --- | ---: | ---: |
| Records | 39.842 | 38.642 |
| Facebook / legacy | 10.154 / 29.688 | 10.154 / 28.488 |
| Historical human decisions | 650 | 650 (642 retained) |
| Sentiment labels | 532 | 524 retained |
| Normalized exact duplicate excess | 3.704 | 3.704 |
| Normalized direct-near edges | 521 | 522 |
| Quality holdout reservations | 40 | 37 retained, 3 excluded |

8 nhãn bị cách ly cùng block: POS2/NEG2/NEU4. 524 retained gồm POS187/NEG219/
NEU118; 288 còn quality flags. Không tự sửa nhãn hoặc bù 3 holdout đã loại.
Historical experiments giữ nguyên, không chuyển sang dữ liệu mới âm thầm.

Audit nguồn dùng cửa sổ 1.000 dòng, không khẳng định ranh giới nguồn/tokenizer:
underscore gần như không có ở đầu, tăng từ vùng 17.001–18.000, phổ biến ở các
vùng sau; tail không underscore không chứng minh nó tự nhiên. Xem
`source_regions.json` trong snapshot công khai để đối chiếu số đo từng vùng.

Ngoài block: 0 hit theo tiêu chí literal 12-word phrases >=50 ký tự xuất hiện
trong >=8 tail records (30 phrase types, 153 tail records có hit). Đây chỉ là
review signal có giới hạn, không chứng minh ngoài block không nhiễm hoặc block
do AI tạo. Các câu chưa chứng minh là nhiễm không bị tự loại.

Rebuild tái dùng facade `plain_text_v3_1` và 2.814 accepted token types frozen;
không sửa engine/dictionary, không normalize từ output cũ. Vẫn **5.251** dòng
có `_`; **4.782** dòng/10.561 occurrences format chưa giải quyết. Protected
structures có thể chứa `_`; không được coi mọi `_` là lỗi rồi cắt toàn cục.

Raw exact duplicate excess 3.661; normalized 3.704. Near policy: >=40 chars,
3-shingles, threshold0.9, skip postings>256; có thể bỏ sót boilerplate. Thêm
1 normalized near edge sau curation do candidate-generation cap thay đổi khi
corpus giảm, không phải thêm/sửa comment. Old graph/reservations giữ nguyên,
recompute raw/normalized protections trên corpus retained; không nới guards.

Proposed pool 8.814 (Facebook25/legacy8.789), không dùng `overall` để chọn nhãn.
Quality KEEP_PROPOSED11.614/REVIEW27.028 chưa phải semantic accuracy. Cần xác
minh provenance, review format/normalization/domain/spam và reservation protocol
trước source switch và quality approval; không xuất AI input hoặc train.

Workbook normalization cũ được đọc theo quyết định người: có note hoặc explicit
REJECT => REJECT, ô trống không note => ACCEPT. 103 ACCEPT/47 REJECT; retained
102/47, 1 ACCEPT thuộc block loại. Carryover chỉ khớp ID/raw/normalized/version,
không coi ACCEPT là corpus approval, không tự sửa 47 đề xuất bị reject.

Hai rebuild độc lập cho cùng manifest/version/content SHA và **21/21 artifact
hashes**. Workbook mới có 200 dòng (46 Facebook/154 legacy), domain/spam/note
đều trống, không chứa block loại hoặc holdout reserved. 353 tests: 352 pass,
1 skip. Không train, API, thay guideline/split/nhãn hoặc kết quả đã khóa.


# Phase J — Dataset Quality Readiness

## Trạng thái hiện tại

**DATASET_FREEZE_PENDING**. Candidate normalization vẫn là `plain_text_v3_1`
tại `outputs/phase_i4_1/v2/`. Phase J không đổi preprocessing, dictionary,
tokenizer, guideline, raw, nhãn người hoặc annotation pointer. Không crawl,
train, gọi API hay tự gán sentiment. Nhận xét trực quan không được dùng làm
approval. Chưa có dataset FINAL hoặc ba file AI input chính thức mới.

Audit hiện tại: `outputs/phase_j/v2/`. Bản v1 giữ làm draft trước khi bổ sung
kiểm URL/post-ID concordance và cách ly bảo thủ cả bài có metadata thiếu.

| Hạng mục | Kết quả thực tế |
| --- | ---: |
| Raw records | 39.842 |
| Human decisions / sentiment labels giữ nguyên | 650 / 532 |
| Format decisions hợp lệ đã điền | 0 / 200 |
| Normalization decisions hợp lệ đã điền | 0 / 150 |
| Domain decisions hợp lệ đã điền | 0 / 200 |
| Spam markers đã điền trong semantic workbook cũ | 0 / 200 |
| Quality holdout đã điền domain và spam | 0 / 40 |
| ELIGIBLE_PROPOSED | 9.788 |
| ELIGIBLE_APPROVED | **0** |
| Pilot selected / released | **0 / 0** |

Tất cả 550 quyết định format/normalization/domain hiện vẫn trống. Spam là
200 đánh giá riêng, không suy từ domain. Bản semantic mới dùng **đúng 200 ID
I.4**, không chọn thêm mẫu mới; holdout dùng đúng 40 ID reservation cũ.

## Chất lượng nhiều tầng

Các rule chỉ tạo candidate, không phải domain classifier được kiểm định.
Tái dùng repetition detector I.1 trên normalized text, không loại chỉ vì
dài hơn 1.000 ký tự, tên riêng, ngôn ngữ, tôn giáo, quan điểm hoặc emoji lặp.
Không có từ phim chỉ dẫn đến UNCERTAIN khi thiếu evidence, không là OFF_TOPIC.
Metadata bài chỉ là identity/context, không chứng minh từng câu thuộc miền phim.
Parent chỉ nối khi source/post/comment ID tìm được đúng một record; evidence
parent không tự biến câu trả lời ngắn thành IN_DOMAIN.

| Layer trên 39.842 records | Số lượng |
| --- | ---: |
| Technical VALID | 39.749 |
| Technical REVIEW_NON_TEXT | 53 |
| Quality holdout không chạy proposal | 40 |
| IN_DOMAIN_CANDIDATE | 17.499 |
| CONTEXT_REQUIRED | 1.703 |
| UNCERTAIN (gồm 40 holdout không đánh giá) | 20.640 |
| SPAM_CANDIDATE | 3 |
| Spam NOT_FLAGGED_UNVALIDATED | 39.799 |
| Spam holdout không đánh giá | 40 |
| KEEP_PROPOSED về chất lượng | 17.498 |
| REVIEW_PROPOSED về chất lượng | 22.304 |
| RESERVED_QUALITY_HOLDOUT | 40 |

Không có technical exclusion trên corpus thực hiện tại. Fixture kiểm empty,
exact UI và encoding/corruption review. Ba spam candidates chưa được con
người xác nhận; không tự EXCLUDE. OFF_TOPIC_CANDIDATE có hỗ trợ cho nhiều ad
cues nhưng không đủ căn cứ để ép các câu UNCERTAIN thành OFF_TOPIC. Spam có
thể IN_DOMAIN; OFF_TOPIC có thể NOT_SPAM. OFF_TOPIC không bao giờ thành NEU.

`KEEP_PROPOSED` chỉ nói về quality candidate, chưa xét đủ identity/leakage,
format approval và provenance. Vì vậy 17.498 KEEP_PROPOSED không đồng nghĩa
17.498 câu được phép gán sentiment. Schema giữ các tầng riêng, technical
reasons, domain evidence, spam evidence, final proposal và eligibility reasons.
`format_status`/`quality_status` I.3 được bảo toàn để đối chiếu; việc phát hành
phải đọc các field mới và approval, không dùng boolean pool cũ.

## Review version và delta

Cả ba workbook gốc được validate với coordinator/checksum trước khi đọc quyết
định. Có 128/200 câu format và 76/200 câu semantic đổi text từ I.3 sang v3.1.
`review_delta.local.csv` lưu ID, vai trò review, text trước/sau, quyết định cũ
và hai text hashes. Không có quyết định cũ nào được tự chuyển thành approval.

Migration semantic giữ cùng 200 ID, dùng một cột `text_view` normalized và hai
cột human riêng. Nếu text giống hệt, quyết định domain và marker spam hợp lệ
có thể được giữ; nếu text đổi, cả hai quyết định để trống và ghi delta.
Note cũ được giữ để tham khảo. Hiện mọi quyết định vẫn BLANK nên không có
quyết định nào bị mất. File cũ I.4 vẫn nguyên byte, importer cũ vẫn hoạt động.
Không cần làm cả workbook semantic cũ lẫn mới: bản mới là bản làm việc hiện tại.

Quyết định trên text I.3 chỉ áp dụng cho đúng text/hash đó. Khi freeze, người
duyệt phải xác nhận đã giải quyết delta, bind checksum bảng delta và version
normalization; không suy approval toàn corpus từ 150 ACCEPT trong mẫu targeted.

## Quality holdout

Đã hoàn thiện export, validator, importer và evaluator cho **đúng 40 ID** đã
đặt trước: 39 legacy, 1 Facebook archive. Workbook để trống domain/spam/note,
không hiển thị proposal. Trong build Phase J, 40 câu không chạy qua domain/spam
rules và toàn bộ bị cách ly khỏi proposed annotation pool.

Review union gồm format I.3, semantic I.4 và normalization I.4.1. Đối chiếu
holdout với union này trên old/new exact groups, old/new direct near edges
và Facebook post identity có URL/ID concordance: **0 overlap ID, 0 exact group,
0 direct-near edge và 0 verified-post overlap**. Cả 40 holdout đều thiếu ít
nhất một thành phần full Facebook identity; không chứng minh độc lập bài
đối với legacy/archive. Đây là **quality-rule holdout**, không phải independent
sentiment test. Không thay ID để làm đẹp kết quả.

Evaluator chỉ chạy khi import đủ quyết định thật; rule implementation hash
phải đúng contract đã ghi trước review. Nếu sửa rule sau khi xem holdout,
không được tiếp tục gọi đó là phép đánh giá holdout chưa sử dụng.

## Annotation pool và nguồn Facebook

| Nguồn | Records | Proposed | Approved | Post identity đủ kiểm URL/ID trong pool |
| --- | ---: | ---: | ---: | ---: |
| Facebook | 10.154 | **24** | 0 | **3** |
| Legacy chưa xác minh | 29.688 | **9.764** | 0 | 0 |

Facebook pool có 3 movie IDs kèm metadata liên kết, không phải chứng nhận
khả năng đại diện ba phim/cộng đồng. So với 101 candidates I.3, 79 câu cũ
không còn qua proposal gates và 2 câu mới qua gates; net còn 24. Lý do ở nhóm
79 câu (chồng lấp): 72 thiếu comment-level domain evidence, 14 format flags/
residual, 1 exact duplicate, 1 quality-review exposure. Không nới leakage guard.
Hai câu mới chỉ là proposal sau đánh giá lại quality/format, chưa được duyệt.

`readiness.json` có funnel tuần tự và lý do không độc quyền cho từng nguồn.
Giữ các guard human labels/REVIEW/EXCLUDE, bài development, test quarantine,
comment identity, old/new exact và direct-near với protected data. Thêm cách
ly cả bài của quality holdout và dữ liệu review khỏi pool; Facebook thiếu
URL/post/comment concordance bị chặn. Không dùng legacy overall khi đánh giá
quality, eligibility hoặc chọn pool.

9.764 legacy là **local proposed candidates**, không phải quality đã được
người xác nhận hoặc permission gửi API. Provenance nguồn/bài gốc vẫn chưa
xác minh, không suy rộng 200 quality judgments thành nhãn thật của 29k dòng.
Do approved pool rỗng, không chọn candidate pilot 500. Manifest chuẩn bị ghi
seed 20261118, target 500, selected_ids rỗng và blockers. Nếu sau này tối đa
24 Facebook trong pilot 500 thì phần Facebook chỉ 4,8% và vẫn chỉ từ 3 bài;
không được gọi là pilot đại diện Facebook. Chưa có source distribution của
một pilot thực sự được chọn.

## Metrics, freeze và kiểm thử

Chưa đo được off-topic/spam precision/recall thực tế: mọi human review còn
trống, nên metrics để null. Evaluator hỗ trợ confusion, precision/recall và
false KEEP/false EXCLUDE theo source, short/middle/long, domain proposal và
repetition risk. CONTEXT_REQUIRED/UNSURE và SPAM_UNSURE được báo support/abstain;
mẫu review không được diễn giải thành natural prevalence. Chỉ đánh giá trên
holdout sau khi đã giữ nguyên rule contract; không vừa tune vừa tuyên bố
hiệu năng cuối cùng trên cùng bộ review.

Config `configs/phase_j_v1.json` và contract local ghi source/config/normalizer/
abbreviation/guideline SHA-256. Freeze/export có gate tương lai: bốn import
format/normalization/domain/holdout đầy đủ, evaluation holdout khớp contract,
delta được giải quyết, approval người với reviewer/date/checksums và phạm vi
record/source cụ thể. Pool approval dựa trên sample phải được xác nhận rõ là
phép suy rộng có giới hạn, không là per-row human domain labels. Legacy cần
chấp nhận rõ giới hạn provenance. Chưa có approval nào được tạo trong Phase J.

Chỉ sau freeze và một pilot approval riêng bound candidate bytes, exporter
mới cho ra ba file `id,text_annotation` giống SHA-256. Không có nhãn người,
overall, source/post metadata hoặc dự đoán trong input AI. Đồng thuận AI chỉ
là silver. Các đường freeze/export không được chạy trên dữ liệu thật ở đây.

Full-corpus verification giữ nguyên raw/normalized/annotation/human fields,
đếm đúng 650/532 và kiểm 214 protected files nguyên SHA-256. Hai workbook
đã validate full text/IDs/source checksums, render và mở read-only bằng Excel:
đúng 200/40 data rows, dropdown domain/spam riêng, freeze header. Blank import
bị từ chối, không tạo output. Full regression: **334 tests, 333 pass,
1 skipped**, không lỗi; gồm 17 tests Phase J. Fixture release hợp lệ kiểm
đúng 500 rows, ba file blind giống byte và không lộ labels/overall. Không có
release thử trên comment thật. CLI prepare/import/evaluate/freeze help chạy được.

Không thấy overlap mới ở các guard đã kiểm tra. Các 28 exact merge groups và
6 direct-near pairs mới do normalization đã được báo từ I.4.1, không phải lỗi
mới sinh trong Phase J. Near search vẫn giới hạn high-frequency shingles,
không bảo đảm phát hiện mọi paraphrase/duplicate; unknown provenance vẫn là
blocker. Không thêm preprocessing để cố tăng KEEP.

[Việc cần người dùng làm và các lệnh import](QUALITY_REVIEW_HANDOFF.md).
