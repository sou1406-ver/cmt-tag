# Dataset filter — 12/11/2026

**FILTERED_CANDIDATE_QUALITY_REVIEW_PENDING.** Input canonical38.642, output **25.810**
records. Không dùng v3.2 để phục hồi text; không train/API/crawl, thay raw/nhãn/
guideline/frozen splits/experiments, phê duyệt corpus hoặc đổi active pointer.

## Chính sách đã chốt

- Legacy có `_` trong text_raw: loại khỏi tập sử dụng, không cố ghép/tách từ.
- Legacy **>1.000 ký tự raw**: EXC_TOO_LONG; đúng1.000 vẫn giữ. Không cắt cụt.
- Facebook >1.000: **giữ và REVIEW**, chưa vào annotation pool; không coi dài là
  lỗi. Dataset input có89 câu Facebook >1.000; sau các rule khác còn **66**,
  tất cả có facebook_length_review=true/quality_status=REVIEW.
- Câu ngắn kể nội dung nhưng không xác định sentiment: theo guideline V2.1 khi
  người gán đọc; không mặc định NEU. Không tạo hoặc đổi nhãn sentiment nào.

## Trước/sau và exclusions

Nguyên nhân chính theo thứ tự áp dụng, không đếm trùng:

| Bước | Loại thêm | Còn |
| --- | ---: | ---: |
| Canonical input | — | 38.642 |
| Legacy raw có `_` | 9.015 | 29.627 |
| Legacy >1.000 raw characters | 160 | 29.467 |
| EXCLUDE đã được người gán xác nhận | 105 | 29.362 |
| Strict exact duplicates | 3.552 | **25.810** |

| Nguồn | Input | Retained |
| --- | ---: | ---: |
| Facebook/archive | 10.154 | 7.146 |
| Legacy | 28.488 | 18.664 |

Facebook giảm50 human EXCLUDE +2.958 exact duplicates; không có Facebook bị loại
vì độ dài. Legacy giảm9.015 `_`,160 quá dài,55 human EXCLUDE và594 duplicates.
Không phát hiện thêm replacement/control encoding lỗi hoặc raw rỗng trong input
này. Các rule đó vẫn được unit test. Không suy đoán spam/off-topic để xóa.

Exclusions có **14.032 IDs**:12.832 loại mới +1.200 block đáng nghi preexisting.
Block cũ không trở lại corpus và không bị trừ hai lần khỏi38.642. Tổng reasons
có chồng lấp:312 legacy >1.000,152 đã ở nhóm `_`;114 human EXCLUDE,9 đã loại ở
bước trước. Ledger giữ primary_reason/all reasons và duplicate representative.

800 là ngưỡng nháp đã được thay bằng1.000; snapshot cũ giữ local, không overwrite.
Ngưỡng độ dài là chính sách thực dụng, không chứng minh mọi câu dài vô giá trị.
Dùng Python len(text_raw), không dùng text đã chuẩn hóa để né ngưỡng. Rule `_`
là lựa chọn bảo thủ, kể cả URL/alias hợp lệ có `_`; không gọi mọi dòng đó là hỏng.
Không tự loại vì ngắn/emoji/teencode hoặc thiếu tên phim ngoài rule đã chốt.

## Minimal view và dedup

Chỉ NFC/decode complete valid HTML entities ngoài URL/email/code; CRLF/NBSP và
trim ngoại biên. Giữ spacing/newlines bên trong, emoji/emoticon, dấu gạch,
phủ định, tên, teencode và chữ lặp. Không đổi alias thành emoji hoặc đoán tên/
mention. UI dictionary match chưa chứng minh UI extraction: giữ và REVIEW.
Chỉ162 retained views khác raw. Trường text_raw luôn bất biến.

Exact = **case-sensitive equality của text_minimal**. Giữ original labeled
identity trước, rồi human-decision presence, Facebook và stable ID; không
chuyển nhãn sang record khác. Strict exact duplicate excess còn0. Normalized
case/whitespace alias excess86 và323 direct-near edges/646 rows chỉ được đánh
dấu review, không bị loại vì similarity. Near policy cũ0.9/3-shingles/min40/cap256
có thể bỏ sót boilerplate; không khẳng định corpus hết near duplicates.

## Nhãn, guards và annotation pool

- Lịch sử **650 quyết định** được giữ nguyên; retained429 quyết định gồm
  **425 sentiment +4 REVIEW**: POS142/NEG176/NEU107.
- Trong524 sentiment canonical,63 không vào tập mới vì `_`,36 vì ngưỡng1.000;
  không mất thêm sentiment label bởi dedup.8 nhãn thuộc block cũ vẫn ở history.
- 141 retained labeled rows có cờ recheck do minimal view khác v3.1; không kết
  luận nhãn sai và không tự sửa. Legacy overall không dùng làm target/pool.
- Raw aliases, exact/near links và historical development/test/reserved/planned
  whole-post/source/exposure/holdout protections được tính lại/carry forward.
  **8.033 retained records protected**; không nới guard hoặc thay frozen split.
- Holdout gốc40 còn22 IDs trong tập mới;18 ngoài tập (gồm3 preexisting).
  Không tự bù mẫu hoặc coi protocol40 vẫn áp nguyên xi.
- **6.968 ELIGIBLE_PROPOSED**: Facebook31/legacy6.937; không giao protected,
  human-decision, near/alias-review hoặc Facebook-long-review rows.
- KEEP_PROPOSED8.866/REVIEW16.944
  là heuristic, không phải semantic ground truth. Approved corpus/pool/training0.
  Legacy thiếu provenance vẫn không là independent test; nhãn đã dùng phát triển
  guideline không tự trở thành test độc lập.

## Đầu ra và tái lập

Bản bàn giao: `outputs/canonical/versions/filtered_20261112_final/`:

- comments.csv và candidate.local.jsonl: filtered dataset/view + raw/provenance.
- exclusions.csv: ID/source/reasons, không xóa file gốc.
- human_history.local.jsonl, protection.local.json, direct_near_duplicates.local.csv.
- annotation_candidates.local.csv: pool đề xuất, không phải AI annotation release.
- before_after_examples.local.jsonl:12 ví dụ chẩn đoán, không protected IDs.
- summary/config/manifest và checksums. Không tạo phase/workbook/script mới.

```powershell
python scripts/build_master_dataset.py --filter-canonical outputs/canonical/versions/rebuild_20261112 --legacy-max-characters 1000 --output outputs/canonical/versions/NEW_FILTERED_CANDIDATE
```

Input: canonical_37cf670237e3398b5c96; manifest SHA
`fe1d39674af11168a454fcb0ea05adf23609cbadda3e87ca443893514b9d1e79`.
Đã đối chiếu60.627 raw observations với pinned sources. **405 tests:404 pass,
0 fail,1 skip**. Hai rebuild độc lập trùng **11/11 artifact hashes và manifest**;
269 protected files đúng checksum. Kiểm độc lập partition, raw/nhãn, strict
exact equality, legacy length, toàn bộ66 Facebook REVIEW, literal emoticon/dash,
pool và ví dụ không giao protected.677 retained records có`:))` không mất chuỗi;
các syntax khác có fixture tests. Public canonical snapshot vẫn nguyên bytes.

CSV SHA: `101e0d2cf88003a2c24867f04dd7ab39a394bfb7e28b987dbe83e1f73685fc5a`.
Output manifest SHA: `602d98e0ee184c8c01f7bd89e2e129918341a367fcfcf862e7b9f56d3352d0f6`.
Verification: `outputs/canonical_support/filter_verification_20261112_final/`.

Code thử nghiệm punctuation v3.2 chưa commit đã lưu patch/snapshots local ở
`outputs/canonical_support/paused_punctuation_work_20261112/`; không dùng trong
bản lọc này. Các approvals/receipts/workbooks cũ không chuyển sang dataset mới.
Đặc biệt diễn giải57 blank v3.2 thành ACCEPT đã bị supersede theo xác nhận mới;
blank=ACCEPT chỉ áp dụng workbook v3.1, không dùng để duyệt candidate filtered.
Raw comments/before-after/exclusions/corpus mới chỉ local, không đưa lên Git.
25.810 records không đồng nghĩa tất cả đã phù hợp sentiment; còn cần
người review chất lượng/nhãn và provenance trước approval/đổi active pointer.
