# Pipeline hiện tại và nơi triển khai

**Trạng thái: DATASET_FREEZE_PENDING.** Có 39.842 raw records, 650 human
decisions/532 sentiment labels; không có corpus/pilot AI mới được duyệt.
Plain text candidate là **plain_text_v3_1**. Nhãn legacy overall không được dùng
làm gold, chọn sentiment pool hoặc thay nhãn người. Các con số quality ở snapshot
J là proposal, không phải semantic accuracy. [Việc người dùng cần làm](QUALITY_REVIEW_HANDOFF.md).

## Luồng và hợp đồng

| Thành phần | Input → output | Implementation / config / môi trường | Entry được khuyến nghị và giới hạn |
| --- | --- | --- | --- |
| Crawler | Facebook URLs + session profile → journal/checkpoint, export/provenance | src/crawler; configs/post_urls.example.csv; requirements/crawler.txt | `python -m src.crawler interactive`; tái dùng Store/run_posts. Không chạy live trong refactor; không collect author fields |
| Raw / ingestion | nguồn CSV/JSON/journal → master records, variants, lineage | src/data; dataset/master.py; configs/master_dataset.json | build_master_dataset.py cho rebuild có chủ đích, không ghi đè master hiện có. Raw/source IDs bất biến |
| Preprocessing | text_raw + fixed version/resources → normalized proposal + events | src/preprocessing facade; engines bên dưới; abbreviations_v3_1.json, plain_text_lexicon_v1.json, accepted_tokens local | `from src.preprocessing import preprocess`; không gán sentiment, không tự đổi annotation pointer |
| Quality | normalized + metadata có evidence → technical/domain/spam proposals, eligibility reasons | quality_readiness.py, repetition.py; configs/phase_j_v1.json | `python -m src.dataset.quality_review prepare`; output immutable, hiện chờ người |
| Human quality | workbook + sealed coordinator → immutable human ledger, metrics khi đủ | quality_review.py, format_workbook.py, normalization_workbook.py; common XLSX/ID utilities | quality_review `import` / `evaluate`; format và normalization vẫn dùng importer riêng vì schema/ý nghĩa khác |
| Annotation | approved blind corpus + V2.1 → human/machine ledgers riêng | src/annotation; dataset/phase_i.py historical blind protocol; quality_release.py cho gate hiện tại | `python -m src.annotation --help` cho annotation contract; không silver/API lúc quality pending |
| Features | train partition → count/TF-IDF vocabulary; validation chỉ transform | src/baseline/core.py, preprocessing_experiments.py, bow_robustness.py | `python -m src.baseline --help`; experiment runners explicit, không fit trong cleanup |
| Models | labeled train → classical estimator hoặc model-specific Transformer checkpoint | src/baseline; src/transformer; classical/Transformer env riêng | Classical char-SVM là reference; H còn PARTIAL. Không có production model được nghiệm thu |
| Evaluation | locked folds/OOF hoặc untouched approved test → metrics/errors/report | baseline diagnostics, dataset/bootstrap.py, transformer/data.py | config/runners trong results index; grouped CV khác independent test, không dùng target labels tune threshold |

## Một entry preprocessing, nhiều engine bất biến

```python
from src.preprocessing import preprocess

proposal = preprocess(
    "phim này ko hay , nhưng diễn xuất ổn",
    version="plain_text_v3_1",
    source="facebook",
)
print(proposal["text_normalized"])
```

Envelope gồm `text_normalized`, `version`, `details`. `details` là nguyên kết
quả engine hiện hữu; facade không sửa text tiếp, không thêm approval hoặc sửa raw.
Muốn khớp full-corpus I.4.1 phải truyền **đúng accepted_tokens local** và bảng
rule/config đã khóa; ví dụ ngắn không tự load tài nguyên của nghiên cứu.

| Version | Engine và quan hệ | Dùng khi nào |
| --- | --- | --- |
| basic_v1 | normalization.py: NFC/whitespace/complete entity ngoài URL | G.3 ablation lịch sử; không thay cho plain-text annotation |
| plain_text_v1 | plain_text.py: protected spans, lexical compound/alias rules | I.2 reproduction và thành phần nền của v3 |
| plain_text_v3 | plain_text_v3.py gọi v1 trên raw đã mask, thêm shape/roundtrip/name protection | I.3 reproduction, input/resources của current candidate |
| plain_text_v3_1 | final_normalization.py gọi v3 từ raw được bảo vệ, bounded entity/abbr/punctuation recovery, fixed point | Candidate annotation chính, **pending human approval** |

Các engine không phải bốn implementation trùng nhau có thể xóa. Chúng được
compose có chủ đích và bị manifest pin. Import path cũ vẫn có hiệu lực để tái
lập. Không lowercase/cắt `_` toàn cục, bỏ phủ định/emoji, đoán tên hoặc tự sửa
teencode mơ hồ. Model adapters sau này thuộc model tương ứng, không tạo một
text_model chung ép PhoBERT/ViSoBERT/SVM dùng cùng segmentation.

## Quality workflow chuẩn

```powershell
python -m src.dataset.quality_review --help
python -m src.dataset.quality_review import --input outputs/phase_j/semantic_workbook_v1/semantic_quality_review_v31_200.xlsx --coordinator outputs/phase_j/v2/semantic_review_input.local.json --output outputs/phase_j/domain_import_01
python -m src.dataset.quality_review evaluate --imported outputs/phase_j/domain_import_01 --output outputs/phase_j/domain_evaluation_01
```

Import chỉ chạy sau khi người dùng đã điền đủ. `prepare` mặc định trỏ vào
artifact đã tồn tại nên sẽ từ chối overwrite; muốn snapshot khác phải chọn
`--output` mới. `freeze/export` tồn tại nhưng thiếu human imports/approval sẽ
bị chặn; **không chạy chúng trong trạng thái hiện tại**.

| Alias cũ vẫn hỗ trợ | Route chuẩn |
| --- | --- |
| scripts/prepare_quality_readiness.py | quality_review prepare |
| scripts/import_domain_spam_review.py | quality_review import |
| scripts/evaluate_quality_review.py | quality_review evaluate |
| scripts/freeze_annotation_dataset.py freeze/export | quality_review freeze/export |

Format ACCEPT/REJECT/UNSURE, domain IN_DOMAIN/OFF_TOPIC/CONTEXT_REQUIRED/UNSURE,
spam SPAM/NOT_SPAM/SPAM_UNSURE và sentiment POS/NEG/NEU là các hợp đồng khác
nhau. Shared parser/ID coverage ở common.py không hợp nhất các quyết định này.
Importers cũ I.2/I.3/I.4 vẫn giữ để tái lập; semantic I.4 đã được migration
**cùng 200 ID** sang bản v3.1, không cần điền cả hai bản.

## Config và dữ liệu đang active

| Vai trò | Path chuẩn, giữ nguyên để không phá checksum |
| --- | --- |
| Active quality/freeze protocol | configs/phase_j_v1.json |
| Active normalization build/resource paths | configs/phase_i4_1.json; configs/abbreviations_v3_1.json |
| Shared lexical/label resources | configs/plain_text_lexicon_v1.json; docs/guidelines/MOVIE_SENTIMENT_V2_1.md |
| Frozen prerequisite/source snapshots | configs/phase_i*.json; outputs/phase_i3/v3; outputs/phase_i4/v5; outputs/phase_i4_1/v2 |
| Current review/holdout and readiness | outputs/phase_j/v2, semantic_workbook_v1, holdout_workbook_v1 |
| Experiment configs | preprocessing_experiments, bow_robustness, ranking_diagnostics, normalization_ablation*, phase_h/* |
| Historical data/annotation configs | data_legacy, data_fixture, legacy_audit, unified_dataset, annotations_development |
| Independent-test/provenance contracts | master_dataset, blind_test, blind_test_exposure, cluster_bootstrap |

Không copy configs thành active/archive aliases: các source/manifest có fixed
paths, nên bảng vai trò là điều hướng thay vì duplicate config. Output cũ được
giữ nguyên, không move/delete; [outputs index](../outputs/README.md) chỉ đường.
Những file private đã có trong Git lịch sử không được sao chép vào tài liệu
tổng hợp; cleanup này không rewrite history hoặc tự untrack dữ liệu người dùng.

## Leakage và approval

- Bảo vệ test reservation, planned-test whole posts, development posts, source
  comment IDs, exact groups và detected direct-near pairs; UNKNOWN exposure không
  được nâng thành unused. Không loại giant component như direct duplicate.
- Human REVIEW/EXCLUDE giữ nguyên và ngoài annotation/train pool mới; overall
  legacy chỉ audit. Source/post provenance thiếu không được đoán từ nội dung.
- 40 quality holdout IDs cố định, không dùng tune rules; không phải independent
  sentiment test. Record/exact/direct-near/known-post overlap được kiểm riêng.
- J có 9.788 **ELIGIBLE_PROPOSED**, 0 approved; FB24 từ3 bài, legacy9.764 chưa
  xác minh quality/provenance. Không nới gate để đủ500 hoặc suy human labels
  cho toàn corpus từ một sample.
- Approval gắn đúng text version/checksum, imports và source scope. Không tự
  chuyển approval I.3 sang v3.1, không auto-fill ACCEPT; annotation pointer chưa đổi.

## Reproduction và bảo trì

[Môi trường](guides/ENVIRONMENT.md) phân biệt classical, crawler và Transformer.
[Experiment results](EXPERIMENT_RESULTS.md) chỉ rõ data/split/config/runner cho
từng phép đo. [Repository map](architecture/REPOSITORY_MAP.md) mô tả call graph;
[consolidation plan](architecture/CONSOLIDATION_PLAN.md) ghi deferred risks.
Mỗi chức năng có một owner/entry point/guide được khuyến nghị; wrapper và
frozen version là compatibility có lý do, không phải lời mời sao chép thêm.
