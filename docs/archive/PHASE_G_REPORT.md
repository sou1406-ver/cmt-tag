# Phase G — Master Dataset & Independent Blind Test Preparation

Ngày thực hiện: 11/11/2026. Mốc kế thừa: `e033ecc` trên `main`.

**Trạng thái: PARTIAL.** Đã tạo master từ các nguồn dữ liệu thực tế truy cập
được và hoàn thiện tooling. **Chưa có independent test: 0/180 mẫu đủ bằng
chứng độc lập**, không tạo workbook gán nhãn thật hoặc gold. Không crawl thêm,
gọi GPT/Claude, train trên corpus thật, hay mở dự đoán test.

## Phạm vi kiểm kê thực tế

Đã duyệt workspace `G:/dlvb`, gồm repository và `../data_module1.csv`, kể cả
file gitignored. Có **604 mục kiểm kê**: CSV/JSON/JSONL, 18 workbook (chỉ đọc
cấu trúc XML để kiểm kê, không dùng bản sao làm nguồn nhãn mới), hai ZIP và
các thành viên CSV trong ZIP. Không giải nén/ghi đè archive.

Không đọc browser profile, cookie, credential, `.env`, cache Selenium,
virtualenv, Git internals. Config không phải dataset; config Phase G được lưu
riêng trong snapshot. Output/support của chính Phase G không được nhập lại.
Không có bằng chứng về dữ liệu trên máy khác; không tuyên bố đã hợp nhất
các file ngoài workspace này.

| Nguồn thực sự nhập master | Số đầu vào | Lượt xuất hiện dòng |
| --- | ---: | ---: |
| Journal crawler | 27 file, có cả run rỗng | 13.386 |
| Export crawler và import Facebook | 11 CSV | 10.113 |
| Archive Facebook | 2 ZIP, 6 thành viên CSV có text | 7.440 |
| `../data_module1.csv` | 1 CSV | 29.688 |
| **Tổng quan sát nguồn** | **45 nguồn logic** | **60.627** |

539 mục derived/support được kiểm kê, không xem là những đợt crawl mới.
Hai đường dẫn legacy trong config cũ **không tồn tại**:
`crawl/dataset.csv`, `crawl/dataset_daxuly_gannhan.csv`. Không tạo file thay thế.

## Master và đối chiếu identity

Version: `facebook_master_20261111_v1`.
Đường dẫn local: `outputs/phase_g/master/`.

| Chỉ tiêu | Số lượng |
| --- | ---: |
| Quan sát nguồn, gồm cả raw/export/bản sao | 60.627 |
| Bản ghi master sau đối chiếu identity bảo thủ | 39.842 |
| Quan sát cùng identity được nối provenance | 20.785 |
| Facebook có comment ID, post ID, URL, movie ID và collected_at | 7.205 |
| Có parent_comment_id | 3.386 |
| Phim / bài có metadata | 31 / 47 |
| Source dataset được ghi trong provenance | 22 |
| Nhóm exact text nối nhiều identity | 3.058 |
| Cặp near-duplicate trên các text view/variant khác nhau | 1.483 |
| Connected components sau nối bắc cầu | 27.886 |
| Thiếu metadata độc lập / chưa nối chắc identity | 32.637 |
| Bản ghi có nhiều biến thể text được giữ lại | 2.402 |
| Xung đột identity/nhãn người cần phân xử được phát hiện | 0 |

**39.842 không phải số comment Facebook độc nhất.** Con số này gồm 7.205
identity Facebook, 29.688 dòng external chưa xác minh và **2.949 quan sát
text-only trong archive** chưa chứng minh được identity. Các bản text-only
có thể chính là bản chiếu của comment đã có; không tự nối bằng text hoặc
tự xóa. Những bản trùng/gần trùng vẫn chung component chống leakage.

Chỉ nối identity khi có platform + comment ID + bài tương ứng, hoặc internal
observation ID + bài nếu thiếu comment ID. Cùng text nhưng khác comment ID
vẫn là những bản ghi khác. Comment ID xuất hiện với bài mâu thuẫn được giữ
riêng và đưa review queue; không có trường hợp đó trong dữ liệu lần này.

Đại diện được chọn theo metadata corroboration, extraction DOM có chính
sách mention, trạng thái extract và độ đầy đủ; timestamp hoặc độ dài không
quyết định bản nào đúng. Tất cả text gốc, text variant, metadata thay thế,
input checksum và số dòng nguồn vẫn có trong `master.jsonl`. Nhiều thời
điểm thu thập hoặc URL alias không bị coi là xung đột identity.

`text_raw` không sửa; `text_view` chỉ dùng `text_without_mentions` đã có với
`dom_text_v2`, nếu thiếu thì giữ nguyên. Không đoán tên qua chữ hoa hoặc
comment cha. Không thu thêm tên/ID tác giả.

Grouping dùng post ID/URL, comment ID, exact NFC/whitespace/casefold text và
near token-3gram Jaccard ≥ 0,9 từ 40 ký tự. Nối tất cả variant và giữ nguyên
36 nhóm development cũ trước khi union bắc cầu. Short exact text có thể nối
những bài vốn khác nhau: thiết kế bảo thủ này giảm pool độc lập, không khẳng
định mọi comment trong một component là cùng identity. Near-duplicate là
heuristic, không chứng minh đã phát hiện mọi paraphrase.

## Nhãn và lịch sử được bảo toàn

Đối chiếu được **đúng 400 quyết định** với `outputs/development/reviewed/`,
so sánh nguyên dictionary của từng dòng, không chỉ nhãn. Giữ nguyên text,
review event, source round, cohort và annotation provenance. Copy chính xác
**19 sự kiện duyệt**, gồm các lý do người gán đã để trống; không điền lý do mới.

| Quyết định người gán | Số lượng |
| --- | ---: |
| POS | 110 |
| NEG | 144 |
| NEU | 92 |
| REVIEW | 4 |
| EXCLUDE | 50 |

346 sentiment labels vẫn là nhãn người thuộc **development đã tiếp xúc**,
không đổi thành independent gold. REVIEW/EXCLUDE giữ đầy đủ, không xóa.

29.688 giá trị `overall` giữ ở `original_labels`, nguồn
`unverified_external`. Không điền chúng vào nhãn sentiment có hiệu lực,
không gọi là gold hoặc silver đã xác minh. Không có nhãn máy mới được tạo.
Master có 39.442 bản ghi chưa được người gán; tập này gồm cả external và
các bản text-only, không phải toàn bộ đều đủ điều kiện train.

## Independent test: lý do chưa thể khóa

Manifest lần này: `outputs/phase_g/blind_test/manifest.json`, **PARTIAL**,
`selected=0`, không có `reservation.json` hoặc workbook thật. Exit code 2
của CLI là kết quả fail-safe được dự kiến, không phải mất dữ liệu.

Điều kiện độc lập kiểm tra trên **toàn bộ 400 dòng**, kể cả REVIEW/EXCLUDE,
và component đã nối với các nguồn còn lại. Đọc thêm provenance của các pool
chọn mẫu/ranking cũ; thu được 36 post ID có bằng chứng xuất hiện ở pool đã
tiếp xúc. Không mở lại model dự đoán hoặc score để chọn test.

- 11.502 bản ghi thuộc component development/nguồn đã tiếp xúc, gồm cả
  các bridge tới bản sao/external; đây không phải 11.502 comment đã gán nhãn.
- 32.637 bản ghi thiếu metadata chứng minh bài mới.
- 356 text view rỗng sau chính sách mention hiện có; ID và lý do lưu trong log.
- Không có post nào được xác nhận bằng chứng **chưa dùng cho guideline hoặc
  chọn mô hình**. Thiếu tên trong 400 dòng không đủ chứng minh điều này.
- Có **8 post** ngoài component đã biết, cần rà lịch sử exposure thêm; ID
  nằm trong `availability.json`, URL/phim trong bảng nguồn local. Chúng chưa
  được xem là nguồn hợp lệ. Ngay cả khi cả 8 được xác nhận, quota 10/bài
  chỉ cho tối đa **80 mẫu**, vẫn không đủ 180.

Các lý do loại có thể chồng lấp, không cộng chúng thành tổng dòng bị loại.
Không crawl bổ sung, nới quota hoặc sử dụng lại bài cũ để lấp thiếu. Muốn đủ
180 cần ít nhất 18 bài và 9 phim thỏa điều kiện, sau kiểm tra connected group;
đây chỉ là điều kiện cần, không bảo đảm đủ pool.

## Tooling blind test và bảo vệ reservation

`configs/blind_test.json` pin master manifest, seed **20261111**, 180 mẫu,
tối đa 10/bài và 20/phim. Thuật toán: sắp ID ổn định, xáo phim/bài/comment
bằng seed, lấy lần lượt qua phim và các bài đã xáo. Không dùng nhãn, score,
từ khóa sentiment hoặc độ dài để chọn. Đây là **quota sample**, không đại
diện phân phối tự nhiên của Facebook.

Chỉ post có evidence rõ trong `attested_unused_posts` mới có thể vào pool.
Không được tự điền attestation vì muốn đủ quota. Khi đủ nguồn, manifest
khóa ID/post/URL/movie/component và toàn bộ identity/alias trong component;
những thành viên không nằm trong 180 câu cũng bị quarantine.

Guard đã nối vào entry point Phase D, development baseline, đầu vào Phase E
(nên bao phủ E.1/E.2), và silver annotation **trước khi provider được gọi**.
Usage API kiểm ID, group, source ID, post URL và hash text chuẩn hóa; các
pipeline mới phải dùng master component/guard tương tự trước train,
validation, pseudo-label, active learning hoặc prompt/threshold tuning.
File reservation hỏng bị chặn; manifest PARTIAL hợp lệ với 0 ID không giả
tạo một reservation. Guard không thể kiểm soát code ngoài repository.

Builder Excel dùng `@oai/artifact-tool`, chỉ nhận whitelist 6 field:
`id,text_view,status,label,review_reason,reason` (đã sửa tên cột trong
[follow-up](PHASE_G_FOLLOWUP.md), `text_raw` trong master không đổi). Một sheet nhìn thấy, header
cố định, wrap text, ô nhập màu nhạt và dropdown. A có 180 câu, B là 50 câu
chung test nhưng xáo độc lập; mọi quyết định trống. Mapping coordinator ở
file riêng, không phải sheet ẩn. Validator từ chối extra columns/sheets,
formula và metadata channels; text bắt đầu bằng `=` được lưu literal.

**Chỉ kiểm thử bằng workbook mô phỏng** trong
`outputs/phase_g_support/workbook_fixture/`: round-trip đủ 180/50 dòng,
không nhãn/metadata thừa, đã render kiểm tra cả hai sheet. Đây không phải
file cho người dùng gán thật và không được đếm vào 180 independent test.

Luồng tương lai: reserve → tạo Excel → kiểm privacy và seal `BLIND_READY`
→ A/B gán riêng → import có receipt/history → xử lý REVIEW/bất đồng rõ ràng
→ đánh giá một model đã freeze. Import không tự tạo gold hoặc sửa nhãn cũ.

## Cluster bootstrap đã chuẩn bị, chưa chạy test thật

`src/dataset/bootstrap.py`, CLI `scripts/evaluate_cluster_bootstrap.py`,
config `configs/cluster_bootstrap.json`: **2.000 replicates**, seed 20261111,
resample post có hoàn lại, lấy toàn bộ comment trong mỗi post kể cả khi post
được lấy nhiều lần. Báo point estimate và 95% percentile CI cho Macro-F1,
F1 POS/NEG/NEU, support, số bài/phim, số replicate hợp lệ/không hợp lệ.

Thiếu true support của lớp → F1 lớp đó undefined; macro undefined khi thiếu
bất kỳ lớp thật nào. Không thay các replicate này bằng 0. Lớp có true support
nhưng không có dự đoán đúng vẫn nhận F1=0 hợp lệ. Percentile chỉ dùng replicate
hợp lệ và ghi rõ conditioning; nếu không replicate nào hợp lệ thì CI=null.
Cảnh báo số cluster ít, support ít và phim chi phối. Không dùng bootstrap
để chọn model hoặc threshold.

CLI tương lai yêu cầu task `BLIND_READY`, receipt blind của A, không còn
REVIEW, prediction cố định bao phủ đầy đủ ID và hợp đồng freeze model trước
nhãn test. REVIEW không tự chuyển NEU. EXCLUDE được đếm riêng. Không chạy
CLI này trên dữ liệu/dự đoán test thật trong Phase G.

## Validation và tái lập

Mốc trước: **180/180 tests pass**. Sau: **210/210 tests pass** qua
`python -m unittest discover -s tests`. Các test mới dùng fixture, không
browser Facebook hoặc API thật. Có test identity, provenance, bridge,
giữ nhãn người/legacy, deterministic/quota, thiếu nguồn fail-safe, privacy
XLSX, guard entry point, import và công thức/resample nguyên cụm.

Kiểm tra dữ liệu thật: `outputs/phase_g/audit/validation.json` **PASS**;
614 checksum đầu vào không đổi, **96 tệp được bảo vệ** không đổi, nguyên
400 quyết định và 19 review events, 36 nhóm development không bị tách,
60.627 quan sát có provenance duy nhất. Không thay artifacts E/E.1/E.2,
guideline hoặc split; không chạy lại kết quả cũ.

Các đường dẫn local chính:

- `outputs/phase_g/master/master.jsonl`, `master.csv`, `manifest.json`.
- `inventory.csv/json`, `quality_report.json`, `conflicts.json`,
  `development_mapping.json`, `human_review_history.json`, `near_duplicates.json`
  và `exposure_ledger.json` cùng thư mục master.
- `outputs/phase_g/audit/source_files.csv`, `sources_by_post.csv`,
  `validation.json`, `manifest.json`.
- `outputs/phase_g/blind_test/manifest.json`, `availability.json`, `exclusions.json`.
- Log test/build và snapshot thử: `outputs/phase_g_support/`.

Master manifest SHA-256:
`7b66f8aaf08d74bc249ff4d613be08d4a9bb64645f7448f1065a704b81d79af9`.
Blind manifest SHA-256:
`4f8c4d6d60de8733950796b4f8b356ee4288305baa347de597a96bc9b757d079`.

Tất cả dữ liệu trên giữ local theo `/outputs/` trong `.gitignore`; commit chỉ
gồm code/config/tests, README và báo cáo tổng hợp, không CSV/XLSX/comment thật.
Chạy lại phải chọn output mới và pin checksum của master tương ứng. Trên máy
khác phải sửa inventory roots và có đủ nguồn local/checksum đã khóa; không
tạo dữ liệu mô phỏng để thay các file nghiên cứu thiếu.

## Các tiêu chí còn thiếu

Master/provenance/tooling/validation đã có. **Chưa đạt** khóa 180 independent
comment và bàn giao workbook A/B thật. Cần xác minh nguồn có metadata và lịch
sử chưa dùng cho phát triển, đủ quota; nếu chỉ còn 8 bài hiện tại thì vẫn
thiếu về số bài. Đây là blocker dữ liệu của Phase G, không phải lý do để
chuyển development sang test hoặc tự tạo ground truth.
