# Phase C — Annotation foundation

Quyết định dữ liệu: [Phase 0](PHASE_0_DATA_AUDIT.md), nhánh B trên fixture.
Nguồn 29k chưa được phép dùng cho train/API. Không có gold hoặc Kappa người thật.
Guideline của task ban đầu: [V2.0](guidelines/MOVIE_SENTIMENT_V2_0.md).
Công việc mới dùng [V2.1](guidelines/MOVIE_SENTIMENT_V2_1.md). Cả hai file giữ
bất biến; task cũ giữ nguyên hash, không di trú nhãn tự động.

## Workflow CLI

```powershell
python -m src.annotation --help
python -m src.annotation export --data-root data --version VERSION --split train --count 150 --hard-ids hard_ids.json --output data/tasks/pilot
python -m src.annotation export --data-root data --version VERSION --split dev --count 200 --output data/tasks/dev
python -m src.annotation export --data-root data --version VERSION --split test --count 300 --output data/tasks/test
python -m src.annotation import-human --task data/tasks/pilot/task.json --csv annotator_a.csv --annotator a --blind --output data/annotations/a.jsonl
python -m src.annotation import-human --task data/tasks/pilot/task.json --csv annotator_b.csv --annotator b --blind --output data/annotations/b.jsonl
python -m src.annotation agreement --left data/annotations/a.jsonl --right data/annotations/b.jsonl --output data/agreement/pilot
python -m src.annotation import-human --task data/tasks/pilot/task.json --csv adjudicated.csv --annotator adjudicator --blind --adjudication --output data/annotations/adjudicated.jsonl
python -m src.annotation release --data-root data --version VERSION --events data/annotations/a.jsonl data/annotations/adjudicated.jsonl --output data/releases/RELEASE
```

Tạo thư mục cha cho outputs JSONL trước khi gọi import. `VERSION` là data_version
thực từ prepare-data, không phải ID giả. Export chỉ mẫu eligible trong split đã
reservation Phase B, không tự chia lại nhóm. `hard_ids.json` là danh sách khoảng
50 ID train chọn có chủ đích; không tự gọi heuristic là “mẫu khó đã xác nhận”.
150 ngẫu nhiên và hard là hai cohort tách biệt; mẫu holdout random, không chọn
theo nhãn/dự đoán. Nếu pool không đủ, task.json báo requested/selected; không
tuyên bố đã đạt ngân sách. Dev/test tối thiểu 200/300 là mục tiêu người gán thực,
không được fixture đáp ứng thay. Challenge lớp hiếm ~50/lớp cần thiết kế độc lập,
không trộn Accuracy với test đại diện; chưa có challenge thật trong workspace.

Hai người sao chép blind.csv rồi điền status/label/review_reason/reason độc lập,
không xem event máy. Status LABELED chỉ POS/NEG/NEU; REVIEW/EXCLUDE có label trống.
Import join theo ID, chặn sửa text/thiếu/trùng ID; ghi người, thời gian, guideline,
evidence_mode. `--blind` là xác nhận của người vận hành, không phải bằng chứng
phần mềm có thể tự kiểm chứng việc người đó chưa xem dự đoán. Adjudication là
quyết định phân xử rõ ràng, không lặng lẽ lấy người gán cuối. Agreement/Kappa
báo riêng random/hard, có REVIEW/EXCLUDE như workflow categories (không phải lớp
model); Kappa null nếu marginals suy biến. Không lấy Kappa fixture làm kết quả thật.

## Silver một provider

```powershell
python -m src.annotation silver --data-root data --version VERSION --provider-config provider.json --output data/silver/run1 --retries 2
```

Provider JSON gồm `kind`, `model`, `model_version` tùy chọn. `kind=replay` đọc
`responses` JSONL tương đối với config, **chỉ kiểm thử fixture**, event không thể
vào release thật. `kind=command` cần `argv` danh sách executable/args cho adapter
LLM do người vận hành cung cấp, `external` mặc định true, timeout_seconds mặc định
60. Adapter đọc một JSON stdin gồm model/system/toàn văn guideline/input, trả đúng
một JSON stdout theo mục 8 guideline; không dùng shell, không lưu stderr/token.
Có thể nối một local LLM hoặc provider đã được phê duyệt; chưa cấu hình/gọi LLM
thật trong nhiệm vụ này. Không tự tạo API server, không yêu cầu key trong repo.

Provider external bị chặn nếu chưa có cả --allow-external lẫn privacy của nguồn
`external_llm_approved` và license đã xác minh. **Chưa có các quyền này cho file
29k; không thêm chúng giả để vượt guard.** Chỉ train eligible được gửi; không gửi
dev/test để tune prompt. Fixed prompt/version/hash + guideline hash, model/version,
timestamp/reason/evidence lưu riêng ở event máy; không coi score là xác suất.
Output resume theo completed ID, kiểm tra contract/hash; retry tối đa 5, ghi lỗi
theo type. Nếu journal bị ghi dở, báo lỗi để kiểm tra, không âm thầm xóa raw.

## Release và guard

Không sửa artifacts Phase B. Release snapshot records + append-only event history,
near pairs, manifest, source report hash, guideline hash và checksum files; dùng
thư mục mới, cấm overwrite. Dùng `--used-ids` JSON array để khai báo train/tune
history khi tạo release kế tiếp; không chấp nhận nhóm holdout đã bị dùng.
Release chưa đủ blind human holdout là draft, không được Phase D dùng kết luận.
Train cho phép silver nhãn máy không pseudo (weak supervision); gold dev/test
chỉ người confirmed/blind, REVIEW chưa giải quyết chặn release ready. EXCLUDE
confirmed được ghi riêng, không train hay tính metric như lớp sentiment.

Tests ở `tests/test_annotation.py`: export blind, ID join, agreement/adjudication,
guard holdout/usage, checksum và không sửa Phase B, silver resume/permission.

Kiểm chứng trước commit Phase C: **60 tests PASS, không skip** (54 cũ + 6 mới),
CPython 3.12.14, Playwright Chromium trên fixture. `python -m src.annotation
--help` và `git diff --check` pass. Không có kết quả annotation người thật.
