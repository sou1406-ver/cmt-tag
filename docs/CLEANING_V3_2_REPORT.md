# HISTORICAL — v3.2 tạm dừng

Hướng hiện tại là [simple dataset filtering](DATASET_FILTER_REPORT.md), không
mở rộng normalizer. Nội dung dưới giữ làm lịch sử; không dùng các candidate
hoặc approvals cũ làm corpus hiện tại. Diễn giải57 blank v3.2 thành ACCEPT đã
được supersede theo xác nhận mới của người duyệt; v3.2 cần decision tường minh.

# plain_text_v3_2 — evidence-based cleaning candidate

Ngày 12/11/2026. **Candidate, QUALITY_REVIEW_PENDING, approved = 0.** Không train,
API, crawl, đổi guideline/nhãn/split, phát hành annotation input hoặc chuyển
active pointer. Corpus mới và mọi comment/event/provenance chỉ giữ local.

## Human review follow-up — 12/11/2026

Người dùng đã hoàn tất workbook và xác nhận riêng convention cho **đúng file
đã lưu**: decision/note đều trống = ACCEPT; explicit REJECT không note là lỗi
dấu nối còn sót. Nhập **57 ACCEPT /43 REJECT**, gồm42 REJECT/no-note đều có `_`
và1 REJECT có note emoticon. Không biến ACCEPT sample thành corpus approval.
Workbook không bị importer sửa; reviewed snapshot, original cell decision,
decision basis và issue lưu immutable tại `outputs/canonical/quality_import_v32_01/`.
Receipt có hash workbook/coordinator và lời xác nhận ở
`outputs/canonical/review_receipts/v32_20261112/convention.local.json`.

Default importer vẫn yêu cầu decision đầy đủ; chỉ opt-in `--human-convention`
với receipt đúng hash mới diễn giải ô trống. Workbook mới khác không kế thừa
convention này; note-only chưa được cho phép sẽ bị chặn. Authoring manifest ban
đầu mô tả template trống; hash bản người dùng đã sửa được ghi ở receipt mới.

Trường hợp emoticon được đối chiếu raw: raw đã có closing parentheses tách rời,
không có bằng chứng dấu colon bị v3.2 xóa. Giữ REJECT và
NO_SAFE_AUTOMATIC_EMOTICON_RECONSTRUCTION; không tự biến `))` thành `:))`, không
đoán lại biểu cảm hoặc bỏ `_` toàn cục. Chưa sửa normalization engine/corpus.
Các số liệu build, workbook trống và kiểm thử ở phần dưới là snapshot trước
human review; follow-up này cập nhật trạng thái task review, không đổi snapshot.
Regression sau importer opt-in: **392 tests, 391 pass, 0 fail, 1 skip**.

## 1. Input và checksums

Đọc đầy đủ local lineage, không rebuild từ public CSV thay thế journals:

| Nguồn | SHA-256 manifest/file |
| --- | --- |
| Canonical v3.1 `rebuild_20261112/manifest.json` | `fe1d39674af11168a454fcb0ea05adf23609cbadda3e87ca443893514b9d1e79` |
| Public canonical snapshot manifest | `431623f1d267f56db9e4997e7be6d98511b5ebf360e153a5318723aa525f8d2b` |
| Phase G master manifest | `7b66f8aaf08d74bc249ff4d613be08d4a9bb64645f7448f1065a704b81d79af9` |
| Original legacy CSV | `4cfe4a00d7a95c46909755b3255e7bc504a7728f503f4b30a68abba7ff9b17b7` |
| Frozen v3.1 engine | `b8f89892e910807525e93f5aa8044159ec4f33d5eb5fc55296a457e9aa255749` |

Đã đối chiếu 37 logical raw sources, 60.627 observations, source row/raw hash,
archive container/member hashes, 650 historical decisions, workbook150,
resources frozen, reservation/availability và quarantine. Source mismatch hoặc
thiếu manifest bắt buộc chặn rebuild; DOM evidence thiếu ở từng record chỉ làm
fallback RAW, không chặn toàn corpus. Nguồn legacy vẫn chưa xác minh platform/
bài/phim/phương pháp gán `overall`; không dùng `overall` làm nhãn hoặc chọn pool.

## 2. Pipeline và entry points

Implementation mới duy nhất: `src/preprocessing/evidence_cleaning.py`.
Facade `src.preprocessing.preprocess(..., version="plain_text_v3_2")` dispatch
riêng; engine v3.1 và các resources cũ giữ nguyên byte.

Luồng: raw → source-bound DOM selection/fallback → bảo vệ technical spans,
emoji alias trước underscore → compose v3.1 → phục hồi residual underscore bằng
evidence Facebook → quality diagnostics. Name/identifier spans được bảo vệ;
không đoán tên để xóa. Không lowercase/bỏ dấu/phủ định/emoji/cắt đuôi comment.
Không có `text_compact`. Mọi transform có rule/stage/offset/before/after.
Trong candidate, `normalization_events` đồng nhất với `transform_events` v3.2;
events cũ ở `normalization_events_v3_1`. `annotation_pool_reasons` đồng nhất với
`eligibility_reasons` tính lại; giá trị cũ ở `annotation_pool_reasons_v3_1`.
Không để trường lịch sử mang nghĩa như kết quả hiện tại.

```powershell
python scripts/build_master_dataset.py --cleaning-v3-2 outputs/canonical/versions/rebuild_20261112 --output outputs/canonical/versions/NEW_V32_CANDIDATE
```

Bản bàn giao: `outputs/canonical/versions/cleaning_v3_2_candidate/`. Không ghi đè
output có sẵn. `cleaning_v3_2/` là internal draft quá bảo thủ vì chặn cả recovery
cũ; đã giữ nguyên để audit và không dùng bàn giao. Các internal refined/final
drafts giữ cùng normalized text như bản bàn giao; candidate cuối bổ sung kiểm
source/reservation, validation DOM và contract event/eligibility nhất quán.
Chúng không phải các corpus được duyệt song song.

## 3. DOM recovery

| Đơn vị đo | Kết quả |
| --- | ---: |
| Facebook retained records | 10.154 |
| Records có candidate DOM từ observation đã pin | 7.205 |
| Records có candidate vượt toàn bộ kiểm tra và được chọn | 4.943 |
| Selected view khác raw | **0** |
| DOM conflicts | 0 |
| Candidate observations bị từ chối | 7.246 |
| Records có ít nhất một candidate bị từ chối | 4.015 |
| Records có candidates nhưng không candidate nào được chọn | 2.262 |
| Posts có record chưa có DOM evidence đủ điều kiện | 40 |

7.246 là **observations**, có lặp journal/export, không phải số comment distinct.
Theo loại source: raw JSONL có6.714 VALID/4.442 rejected observations; export
CSV có2.478 VALID/2.804 rejected. Một record có thể có cả observation hợp lệ và
observation bị từ chối; full source-by-source counts nằm trong summary local.
Lý do từ chối thực tế là DOM_EVIDENCE_MISSING: cặp raw/DOM và mention_count có
trong source, nhưng không lưu span/href của từng đoạn bị xóa. Không lấy
deletion/subsequence match làm bằng chứng đủ rằng chỉ mention bị loại. Do đó
4.943 selected views đều giống raw; không tuyên bố đã sửa tên đầu reply.

Identity kiểm cả source SHA/row, namespace/post/comment, raw observation và
`dom_text_v2`; không join riêng comment_id. Raw variant khác text canonical
được giữ như lineage nhưng không tự coi là replacement tương đương nội dung.
Code hỗ trợ thay đổi DOM khi có spans xác thực và tái tạo đúng output, đã test
bằng fixture; nguồn thật hiện chưa đủ evidence đó. Chi tiết theo source và lý
do ở `dom_provenance.local.jsonl`, `unresolved_dom.local.jsonl`, `summary.json`.
Không tự thiết kế crawl lại. DOM flags tách khỏi quality; thiếu evidence không
tự EXCLUDE hay chặn annotation. DOM_CONFLICT yêu cầu review.

## 4. Emoji aliases

Dùng exact English `en` names của fully-qualified Unicode sequences trong
[emoji==2.14.1](https://pypi.org/project/emoji/2.14.1/), pin wheel/member SHA,
license và mapping trong `configs/emoji_aliases_v3_2.json`; không cần cài thêm
package khi chạy. Mapping 3.781 names, SHA
`1014f70e5da4946fafb0923b878182400cbe21f962ba620cc32d52d6ecd01356`.
Không fuzzy/substring match; chỉ syntax được parser nhận dạng. Bare alias cần
legacy/Vietnamese prose context, tránh assignment/code/identifier; không đủ
context thì giữ và review. URL/email/code/hashtag/mention được bảo vệ.

1.797 recovery events trên **1.124 records** khác baseline có bước alias.
Baseline có565 records còn exact alias signatures theo cùng parser; baseline
technical-@ pattern có4 records, không suy ra số tên người/plain-text mentions.
20 records có unmatched-alias review flags; 0 bare-alias ambiguity flags trong
corpus này. Đây là số đo theo parser đã khai báo, không phải toàn bộ mọi dạng
alias có thể tồn tại. Unicode emoji hợp lệ giữ nguyên, không ánh xạ sentiment.
Các rule co-occur nên contribution counts không cộng thành số câu cải thiện;
các alias đã được v3.1 xử lý và delimiter repair có thể cùng hiện diện.

## 5. Underscore evidence

117 distinct Facebook comments hợp lệ sau guard; **121 tokens** đạt >=5 distinct
comments. Dùng NFC, case-sensitive lowercase Latin alphabetic 1–7 ký tự,
standalone; không đếm occurrence lặp hoặc exact duplicate comment; không lấy
legacy, URL/code/email/hashtag/mention, development/test/holdout/protected posts.
10.037/10.154 Facebook records vốn đã protected. Không nới guard để tăng vocab.

`token_evidence.local.json` giữ full frequencies, used IDs, tokenizer version,
source content SHA, exclusion policy và vocabulary SHA. Frequency/Latin shape
**không xác nhận âm tiết là tiếng Việt**; vocabulary rất hẹp và còn source bias.
Resources lexical/roundtrip frozen của v3.1 được compose riêng, không gán nhầm
cho evidence mới. Rule mới chỉ chạy trên residual legacy tokens, không Facebook.

**670 token splits, 673 ký tự `_` trên 592 rows** bằng evidence mới. Không đủ component
evidence thì giữ nguyên. Emoticons, numbers, uppercase/name-shaped compounds,
ASCII identifiers và protected spans không bị tách bởi rule mới.

Còn 4.786 rows có `_` (bao gồm protected structures); 4.771 rows có residual
format tokens, 10.399 occurrences/2.957 types. Full frequency/top20 và reasons
ở `remaining_underscore.local.csv`/candidate events local, không đưa token có
khả năng là tên/account vào public report. Cần kiểm false positives từ evidence
heuristic và những compounds đa nghĩa; không lấy mức giảm `_` làm quality score.

## 6. Ma trận 47 REJECT

Đọc lại workbook/coordinator, đúng convention người dùng đã xác nhận trong
config: explicit REJECT hoặc có note => REJECT; ô trống không note => ACCEPT.
150 quyết định cũ = **103 ACCEPT /47 REJECT**, retained102/47; không hardcode khi
import. Quy ước này **không áp dụng workbook v3.2 mới**.

| Root-cause/evidence tag (có thể chồng lấp) | Records |
| --- | ---: |
| Residual underscore chưa phục hồi | 40 |
| Emoji serialization | 5 |
| Name/abbreviation mơ hồ | 2 |
| Non-text/domain decision, không chỉ normalization | 1 |
| Không đủ evidence xác định rule cụ thể | 1 |
| REJECT không kèm lý do, chưa xác nhận causal attribution | 37 |

Kết quả: **10 FIX_PROPOSED /35 NEEDS_REVIEW /2 NO_SAFE_FIX**. Một đề xuất có
thể chỉ sửa một phần; không đồng nghĩa toàn câu đúng hoặc REJECT đã giải quyết.
37 trường hợp chưa có fix proposed, và cả 10 đề xuất vẫn chờ người duyệt.
Không tự mở rộng tên viết tắt, sửa tên riêng, diễn giải note mơ hồ hoặc xóa
emoji-only. Không có bypass theo record ID. Mỗi ID có raw/v3.1/v3.2, note,
events/flags, cause evidence và status trong ledger local. **0 old decisions
được chuyển thành approval v3.2**; old REJECT vẫn gắn với old checksum/version.

## 7. Non-text và nhãn người

70 NON_TEXT_REVIEW records; không tự EXCLUDE. Emoji/emoticon/punctuation-only
cần review; biểu thức điểm hợp lệ giữ nguyên, không suy sentiment. Technical
`@handle` removal có 1 changed record; URL/email/code và tên plain text giữ.

650 quyết định lịch sử nguyên vẹn; retained642 quyết định/524 sentiment vẫn
POS187/NEG219/NEU118. Block1.200 vẫn ngoài corpus; 8 nhãn lịch sử trong block
không bị đưa lại. **17** retained human-labeled rows đổi preprocessing view
được gắn `needs_human_recheck`, không sửa nhãn. Mọi `text_raw` và source bytes
bất biến; `text_annotation` vẫn null.

## 8. Duplicate, leakage và pool

Cùng population38.642, cùng near policy0.9/3-shingles/min40chars/posting cap256:

| Metric | Canonical v3.1 | Candidate v3.2 |
| --- | ---: | ---: |
| Records | 38.642 | 38.642 |
| Facebook / legacy | 10.154 /28.488 | 10.154 /28.488 |
| Retained human sentiment | 524 | 524 |
| Exact groups | 34.938 | 34.934 |
| Exact duplicate excess | 3.704 | 3.708 |
| Direct near edges | 522 | 527 |
| Protected retained records | 11.837 | 11.837 |
| Rows có residual format | 4.782 | 4.771 |
| Diagnostic format-review rows: residual token hoặc normalization flag | 7.975 | 8.044 |
| Quality KEEP_PROPOSED /REVIEW | 11.614 /27.028 | 11.621 /27.021 |
| Proposed annotation pool | 8.814 | **8.812** |
| Approved annotation/training | 0 | 0 |

8 newly merged exact groups; near edges thêm6/mất1. Không có changed DOM view
nên các duplicate mới không thể được quy cho DOM removal. Raw aliases, old/new
normalized identities và excluded shadows đều tham gia guard; không chỉ dedup
new text. Raw, old và new direct-near edges cùng protection closure bảo vệ human,
dev/test/reserved/planned/exposure posts và quality holdout. Giữ cả old guards,
không đổi frozen graph/splits. Newly protected0; eligibility/reason differences468.

Snapshot v3.1 có7.919 NEEDS_REVIEW và47 HUMAN_REJECTED format statuses. V3.2 không
kế thừa approval đó; residual format count không đồng nhất với mọi quality/
normalization flag. Normalization approval của **toàn candidate vẫn pending**.
Predicate diagnostic trong bảng giống nhau ở cả hai phía, không phải human
decision/status approval. FORMAT_REVIEW_PENDING eligibility reason là7.959→7.972.
Các diagnostic tăng dù residual giảm; không kết luận v3.2 tốt hơn trước review.
Near candidate generation cap có thể bỏ sót boilerplate-driven links; không
gọi bounded near detection là bảo đảm không còn duplicate.

## 9. Workbook và review

Một workbook bàn giao `cleaning_review.xlsx`, đúng5 cột
`id,text_truoc,text_sau,decision,note`; không metadata hoặc sentiment trong sheet.
Decision/note trống. Seed20261120; 35 random changed +25 largest remaining
changed +30 risk +10 unchanged controls, quota đủ, không cần reallocate.
Random group lấy trước; largest là lớn nhất trong phần còn lại, không nói đó là
top25 toàn corpus. Không lấy protected IDs/posts/aliases/near neighbors hoặc hai
exact/direct-near linked records; không dùng sentiment để chọn.

Chỉ điền D/E: ACCEPT hoặc REJECT; blank là pending. Đọc toàn văn bằng F2/thanh
công thức nếu row height không hiển thị hết. Import sau khi hoàn thành:

```powershell
python scripts/import_final_normalization_review.py --cleaning-v3-2 --input outputs/canonical/versions/cleaning_v3_2_candidate/review/cleaning_review.xlsx --coordinator outputs/canonical/versions/cleaning_v3_2_candidate/workbook_input.local.json --output outputs/canonical/quality_import_v32_01
```

Importer kiểm đúng IDs/text/candidate hash/version, từ chối ô trống, giữ ledger
immutable và không tự approval/source switch. Workbook companion có manifest
riêng; candidate content đã seal trước authoring, không sửa các entry đã seal.

## 10. Regression và tái lập

`python -m unittest discover -s tests`: **388 tests, 387 pass, 0 fail, 1 skip**.
Hai rebuild độc lập có **17/17 sealed artifact hashes và manifest giống nhau**.
Candidate content SHA-256:
`24595b67227d7761e3f63902d80c83c34795d0b4f666ea0f8b1c470d23ba56c7`.
Vocabulary SHA-256:
`df8509a16599483140ddef4f3f862bbb07a03c0f075eaba09c4e6c7eba06a630`.
281 protected input files vẫn đúng checksum. Đối chiếu mọi retained ID/raw/source/
human decision; recompute vocabulary độc lập; workbook100 blank, protected/exact/
near overlap0; proposed pool8.812 không giao protected IDs/near links. Workbook
được render và kiểm XML/text/dropdown/freeze, một sheet đúng5 cột, không formulas.
Verification receipt: `outputs/canonical_support/cleaning_verification_v2/`.
Mỗi retained row đã được kiểm raw/human preservation và text idempotence. Hai
rebuild độc lập kiểm determinism từ raw/resources; không dùng idempotence thay
lineage verification. Source-pointer, old canonical/public snapshot, old engines,
650 decisions, guideline và locked experiments đều được checksum bảo vệ.

## 11. Blockers trước khi duyệt

- Changed DOM views thiếu deletion-span/href evidence; chưa sửa tên plain text.
- 47 REJECT vẫn cần review v3.2; 10 đề xuất không là10 approvals.
- Evidence vocabulary117 comments/121tokens còn hẹp; frequency không là ngôn ngữ
  validator. Unresolved tokens/unknown aliases/ambiguous identifiers giữ review.
- 70 non-text và17 human-labeled changed views cần người xem, không tự bỏ nhãn.
- Legacy provenance/rights và independent-test readiness chưa được xác minh.
- Quality holdout37 retained/3 excluded vẫn reservation cũ, không tự bù mẫu.
- Cần review workbook, quyết định source switch và quality approval riêng.

Full-corpus implementation không bị BLOCKED vì đủ local nguồn/manifest đã pin;
**changed-DOM recovery và corpus approval vẫn bị chặn** ở các điều kiện trên.
Không xuất candidate corpus lên Git; snapshot v3.1 đã chia sẻ không bị sửa/xóa.
