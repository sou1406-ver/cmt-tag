# Phase B — Data foundation (hoàn tất 09/11/2026)

## Đã thực hiện

Import CSV/JSON theo cấu hình; snapshot raw byte nguyên vẹn; schema và
provenance tách nhãn người/máy; quality có lý do; exact dedup giữ lineage;
near-duplicate candidates giữ lại để kiểm tra; union nhóm post/comment/trùng
rồi chia pool deterministic; blind export; checksum validator và gold guard.
Không chạy crawler, gán sentiment mới hoặc huấn luyện mô hình.

## File thay đổi

| Nhóm | File |
|---|---|
| Mới: data code | `src/__init__.py`, `src/data/__init__.py`, `src/data/importers.py`, `src/data/schema.py`, `src/data/quality.py`, `src/data/split.py`, `src/data/pipeline.py`, `src/data/validation.py` |
| Mới: CLI | `scripts/prepare_data.py`, `scripts/validate_data.py` |
| Mới: config/setup | `configs/data_legacy.json`, `configs/data_fixture.json`, `requirements-data.txt`, `.gitignore` |
| Mới: tests | `tests/__init__.py`, `tests/test_data_foundation.py`, `tests/fixtures/comments.csv`, `tests/fixtures/comments.json` |
| Mới: hướng dẫn/báo cáo | `README.md`, `docs/DATA_SCHEMA.md`, `docs/REPO_AUDIT_PHASE_A.md`, `docs/PHASE_B_REPORT.md` |
| Vá tối thiểu | `gan_nhan.py`: giữ human/metadata, output exclusive; `trich_dac_trung.py`: bắt buộc manifest và chỉ fit train |
| Chỉ tạo local, gitignored | `data/raw`, `data/processed`, `data/splits`, `outputs/phase_b_tests.txt` |

Ba CSV cũ, crawler, preprocessing cũ, MMR/media, virtualenv và đặc tả chính
không bị ghi đè hoặc xóa. SHA-256 ba CSV sau chạy trùng hoàn toàn audit A.

## Command và test thực tế

Python dùng để kiểm chứng: CPython 3.12.14 bundled, Windows. Thay `python`
bằng đường dẫn được ghi trong README khi PATH chưa hoạt động.

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src scripts tests gan_nhan.py trich_dac_trung.py
python scripts/prepare_data.py --config configs/data_legacy.json
python scripts/validate_data.py --data-root data --version b9edc9e7b24b66af8485
python scripts/validate_data.py --data-root data --version b9edc9e7b24b66af8485 --require-gold
```

- **39 tests PASS, không skipped**, log local `outputs/phase_b_tests.txt`.
- Compileall PASS trên mã đã sửa; không xác nhận chạy numerical helpers cũ
  vì thiếu sklearn/scipy.
- CSV và JSON fixture import end-to-end; giữ raw và unknown metadata;
  bảo toàn emoji/phủ định/teencode; kiểm tra nhãn/trạng thái; không ghi đè
  nhãn người; không tự nâng legacy label thành gold; pseudo schema không là gold.
- Các test kiểm tra cầu nối duplicate nối nhiều post, deterministic theo
  seed và thứ tự input, machine labels không ảnh hưởng split, từ chối manifest
  leakage, human gold phải có provenance, holdout phải blind và chưa dùng train/tune.
- Từ chối chạy đè version/input/output, phát hiện artifacts bị thay đổi,
  đối soát số dòng và tạo blind exports không chứa nhãn/prediction.
- Thử `--require-gold` trên dữ liệu thật phải trả **exit 2** vì chưa có nhãn
  người xác nhận; đây là hành vi bảo vệ mong đợi, không phải test lỗi.
- TF-IDF vocabulary train-only và end-to-end P0 metrics là nghiệm thu Phase D,
  chưa tuyên bố đã đạt ở Phase B.

## Kết quả trên dữ liệu thật

Phiên bản cuối của Phase B: **`b9edc9e7b24b66af8485`**, seed **42**.
Các bản thử trước vẫn được giữ nguyên; dùng version này để đi tiếp Phase C.

Artifacts local:

- `data/processed/b9edc9e7b24b66af8485/report.json`
- `data/processed/b9edc9e7b24b66af8485/records.jsonl`
- `data/processed/b9edc9e7b24b66af8485/near_duplicates.jsonl`
- `data/splits/b9edc9e7b24b66af8485/manifest.json`
- `data/splits/b9edc9e7b24b66af8485/{train,dev,test}_blind.jsonl`

| Đại lượng | Số lượng |
|---|---:|
| Raw nhập | 3.471 |
| Quality excludes theo luật bảo thủ hiện tại | 0 |
| Exact duplicate extra rows sau NFC/whitespace/casefold | 0 |
| Representatives giữ lại | 3.471 |
| Near-duplicate pairs chưa kiểm tra | 15 |
| Connected groups | 3.456 |
| Train pool | 2.430 |
| Dev pool | 521 |
| Test pool | 520 |
| Nhãn gold người đã xác nhận | **0** |

Không loại bằng topic keyword hay ép lớp; 0 quality excludes không có nghĩa
toàn bộ comment đã được con người xác nhận liên quan đến phim/sạch spam.
15 cặp near được gom nhóm nhưng chưa xóa dòng nào.

Sidecar cũ có 3.430 dòng: **3.429 match exact raw**, **1 không khớp** (row
number 1-based **1623**, không tính header). Dòng này cũng không có exact match
sau NFC/whitespace; không suy diễn hay chuyển nhãn sang text gần giống.
Snapshot chứa đầy đủ dòng không match để xử lý sau. Có **42 raw comment chưa
có đề xuất máy**. Không nhập 29k vì chưa có file.

| Đề xuất máy sau join/lọc, chưa kiểm định | Số lượng |
|---|---:|
| POS | 870 |
| NEG | 151 |
| NEU | 1.637 |
| REVIEW (trạng thái) | 109 |
| EXCLUDE (đề xuất trạng thái) | 662 |

Các số này là thống kê nhập nhãn cũ, **không phải kết quả thực nghiệm hoặc
phân phối sentiment gold**. Đề xuất EXCLUDE chưa làm mất raw comment.

## Hạn chế và bước tiếp theo

Toàn bộ 3.471 dòng thiếu post/comment IDs, thời gian thu thập, movie ID,
license/privacy. Không bổ sung metadata giả; không thể chứng minh split độc
lập bài/phim/nguồn chưa từng thấy. Near-duplicate heuristic không bắt hết
paraphrase. Không cân bằng bằng nhãn máy. Pool hiện tại **chưa là gold khóa**.

Phase C tiếp theo: đóng guideline versioned từ đặc tả, tạo dry-run 30–50 và
pilot 150 random + 50 hard riêng từ train pool; mẫu khó phải được người xác nhận,
không lấy luật máy làm đáp án. Chuẩn bị bảng gán độc lập, review queue,
agreement/kappa và phân xử. Gán blind cho reserved dev/test; kiểm tra tính đại
diện và khóa gold trước mọi thử nghiệm mô hình. Chỉ sau đó đến Phase D.

Git ban đầu chưa tồn tại. Người dùng đã yêu cầu đưa code lên
`https://github.com/sou1406-ver/cmt-tag`; khởi tạo nhánh main và chỉ bàn giao
code/docs/config/fixture. Dữ liệu thật/outputs/media/virtualenv được gitignore.
Report run ghi code SHA-256 thay cho commit (run được tạo trước commit bàn giao).
