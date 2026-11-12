# Việc cần làm với canonical candidate mới

**Review normalization v3.2 mới:**
`outputs/canonical/versions/cleaning_v3_2_candidate/review/cleaning_review.xlsx`.
100 câu, cột B/C là trước/sau; chỉ điền D/E: ACCEPT hoặc REJECT và note.
Ô trống = chưa làm. Không metadata/sentiment trong sheet; không kế thừa
ACCEPT cũ. [Report và lệnh import đúng coordinator](CLEANING_V3_2_REPORT.md).
File domain/spam bên dưới là task v3.1 khác, chưa là quality approval cho v3.2.

Điền một file [`canonical_quality_review.xlsx`](../data/canonical/canonical_37cf670237e3398b5c96/canonical_quality_review.xlsx):
200 câu, chỉ cột C/D/E trong sheet Review. Domain và spam là hai quyết định
riêng; đọc hướng dẫn/dropdown, không sửa ID/text/source. **Ô trống là chưa làm**,
không áp dụng quy ước blank=ACCEPT của workbook normalization cũ cho file này.

Normalization150 cũ đã được đọc theo xác nhận người: 103 ACCEPT/47 REJECT,
không cần gán lại để nhập. Chưa sửa các lỗi text bị reject. Corpus chưa approved.
Holdout40 cũ có3ID nằm trong block loại; còn37 reservation, chưa tự bù mẫu.
Các bảng pending bên dưới phản ánh snapshot trước rebuild; không dùng chúng để
tự duyệt/chuyển nguồn canonical. Xem CURRENT_PIPELINE cho lệnh import mới.


# Quality review — việc cần làm

Trạng thái: **DATASET_FREEZE_PENDING**. Không có API call, train hoặc corpus
FINAL. Candidate chính là plain_text_v3_1; raw và nhãn sentiment không đổi.

## Các file cần điền

| Việc | File local | Cột cần điền | Còn thiếu |
| --- | --- | --- | ---: |
| Kiểm format I.3 so với raw | `outputs/phase_i3/workbook_v3/plain_text_validation_200.xlsx` | format_decision, human_note | 200 |
| Kiểm phép normalization v3.1 | `outputs/phase_i4_1/workbook_v2/final_normalization_review_150.xlsx` | human_decision, human_note | 150 |
| Domain/spam, cùng 200 ID semantic I.4 | `outputs/phase_j/semantic_workbook_v1/semantic_quality_review_v31_200.xlsx` | human_domain_decision, human_spam_decision, human_note | 200 domain + 200 spam |
| Quality holdout 40 ID đã giữ | `outputs/phase_j/holdout_workbook_v1/quality_holdout_40.xlsx` | human_domain_decision, human_spam_decision, human_note | 40 domain + 40 spam |

Semantic I.4 cũ vẫn còn nguyên. **Làm bản semantic v3.1 mới, không làm lại cả
hai file semantic.** Đây là migration cùng 200 câu, không phải thêm 200 câu.
Nếu đã điền bản cũ sau snapshot này, giữ file đó và import/refresh migration
theo checksum trước khi dùng bản mới; không ghi đè quyết định mới bằng bản
snapshot trống. Sau khi đã điền bản v3.1, dùng importer, không tạo migration
mới để thay file đã làm.

Domain: IN_DOMAIN / OFF_TOPIC / CONTEXT_REQUIRED / UNSURE.
Spam: SPAM / NOT_SPAM / SPAM_UNSURE. Hai cột độc lập, phải điền cả hai.
Không điền POS/NEG/NEU. OFF_TOPIC không phải NEU; thiếu keyword phim không
chứng minh off-topic. Review dài, trích dẫn hoặc emoji lặp không tự là spam.
Đọc đủ nội dung bằng F2/thanh công thức khi dòng dài.

Format/normalization: ACCEPT / REJECT / UNSURE. Ghi note khi phát hiện lỗi;
không sửa text/ID trực tiếp. Câu chưa rõ nghĩa hoặc context được phép UNSURE.
150 ACCEPT không tự chứng minh toàn corpus đúng. Format cũ gắn với I.3;
`outputs/phase_j/v2/review_delta.local.csv` đối chiếu 128 format và 76 domain
rows đã đổi. Quyết định trên text cũ không tự áp dụng cho phần delta mới.

Làm quality development trước; khi phát hiện lỗi, giải quyết và ghi rule
contract trước khi dùng quality holdout. Không xem holdout để chọn rule.
Nếu đã dùng holdout để chỉnh rule, phải ghi exposure; không gọi nó là
holdout chưa dùng nữa. 40 câu này không phải independent sentiment test.

## Import quyết định thật

Các lệnh chạy từ root repo trong môi trường Python hiện có. Output bất biến;
nếu đã tồn tại, dùng tên output mới. Import không tự freeze hoặc phát hành.

```powershell
python scripts/import_format_validation.py --input outputs/phase_i3/workbook_v3/plain_text_validation_200.xlsx --output outputs/phase_j/format_import_01
python scripts/import_final_normalization_review.py --input outputs/phase_i4_1/workbook_v2/final_normalization_review_150.xlsx --output outputs/phase_j/normalization_import_01
python -m src.dataset.quality_review import --input outputs/phase_j/semantic_workbook_v1/semantic_quality_review_v31_200.xlsx --coordinator outputs/phase_j/v2/semantic_review_input.local.json --output outputs/phase_j/domain_import_01
python -m src.dataset.quality_review import --input outputs/phase_j/holdout_workbook_v1/quality_holdout_40.xlsx --coordinator outputs/phase_j/v2/holdout_input.local.json --output outputs/phase_j/holdout_import_01
```

Importer kiểm sealed coordinator, source manifest, đúng 200/40 IDs, text hash,
raw/previous/source evidence; holdout phải khớp nguyên reservation. Từ chối
formula, text bị sửa/truncate, ID thiếu/lặp, sentiment trong cột domain và
quyết định trống. Chỉ tạo ledger riêng, không sửa các file nguồn.

Đánh giá khi đã có đủ quyết định:

```powershell
python -m src.dataset.quality_review evaluate --imported outputs/phase_j/domain_import_01 --output outputs/phase_j/domain_evaluation_01
python -m src.dataset.quality_review evaluate --imported outputs/phase_j/holdout_import_01 --output outputs/phase_j/holdout_evaluation_01
```

Holdout importer không tính metrics hoặc dùng labels để tune. Evaluator kiểm
implementation hash với contract trước khi tính proposal/metrics holdout lần
đầu. Kết quả development chỉ là diagnostics trên mẫu; không dùng nó để tune
rule rồi tuyên bố đó là hiệu năng cuối cùng. Không có số liệu precision/recall
thật cho tới khi có các quyết định này.

## Freeze và pilot sau này

Tooling có `scripts/freeze_annotation_dataset.py` với subcommand `freeze` và
`export`; hiện **không chạy** vì chưa có approval. `freeze` yêu cầu source J,
bốn human imports, evaluation holdout và một approval thật, gắn chính xác:

- Reviewer, thời điểm, source manifest/contract và bốn import-manifest hashes.
- Review-delta hash, xác nhận normalization/format/domain/spam findings đã xử lý.
- Chấp nhận quality holdout và giới hạn suy rộng quality sample sang pool.
- Danh sách record IDs, nguồn được phê duyệt; riêng legacy phải xử lý/chấp nhận
  rõ provenance chưa xác minh cho mục đích annotation. Không suy ra quyền gửi API.

Freeze chỉ đổi annotation pointer trong một output mới sau các gate này;
không sửa dataset gốc. `ELIGIBLE_APPROVED` là pool-level approval có evidence,
không giả thành human domain label cho từng câu chưa review.

Pilot phải được chọn bằng seed đã ghi (20261118), kiểm source concentration
và old/new duplicate guards, rồi duyệt checksum candidate riêng. Exporter chỉ
nhận đúng 500 ID/text thuộc frozen approved pool và kiểm lại test/human/
duplicate exclusions; ba blind CSV cùng bytes. Không có cơ chế tự điền approval.
Đồng thuận ba AI là silver; phase này không chạy annotation.

Hiện 9.788 proposed / 0 approved; legacy chưa được kiểm định và Facebook chỉ
24 candidates từ 3 bài, nên **chưa chọn pilot 500**. Không cần crawl thêm hoặc
gán sentiment mới trong lúc hoàn tất quality review.

## Kiểm tra kỹ thuật

```powershell
python -m src.dataset.quality_review prepare
python -m unittest discover -s tests
```

Default output `outputs/phase_j/v2/` đã tồn tại nên lệnh prepare từ chối ghi
đè; khi cần refresh snapshot, truyền `--output` mới. Workbook builder là
`scripts/build_domain_spam_workbook.mjs`, dùng bundled artifact-tool qua
isolated authoring workspace, nhận coordinator JSON và folder output mới.
Không ghi đè workbook đã có quyết định. Importers cũ của I.2/I.3/I.4 vẫn giữ.

Full-corpus verification: 39.842 records và 650/532 giữ nguyên, 214 protected
files khớp checksum. Full regression **334 tests: 333 pass, 1 skipped**.
Workbook/IDs/decisions giữ local, không commit lên Git.
