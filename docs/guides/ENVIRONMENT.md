# Môi trường và dependencies

Một guide setup cho toàn repo. Structural consolidation không cài package,
nâng version hoặc ghép môi trường NumPy/sklearn không tương thích. Những pin
dưới là của các run đã có, không phải khuyến nghị phiên bản mới nhất.

## Chọn đúng môi trường

| Việc | Requirements chuẩn | Runtime và giới hạn |
| --- | --- | --- |
| Data/quality/import cơ bản | requirements/data.txt | Python standard library. Current normalization dùng accepted-token snapshot có sẵn, không tự chạy segmenter |
| Crawler Selenium | requirements/crawler.txt | selenium4.52.0; Chrome/Brave riêng, profile/session local; không thuộc quality approval |
| Classical baseline tối thiểu | requirements/classical-base.txt | sklearn1.9.1, NumPy2.5.4, SciPy1.18.1, joblib1.6.0 |
| Classical + segmentation | requirements/classical-nlp.txt | Includes classical-base + segmentation8.3.0 |
| E/E.1 reproduction | requirements/locks/classical-windows-py312.txt | Full resolved Windows/CPython3.12 lock, nguyên byte lock gốc |
| E.2 plots/ranking | requirements/analysis-plots.txt | Full classical lock + matplotlib3.11.2 |
| Offline segmentation resource rebuild | requirements/segmentation.txt | underthesea8.3.0; resource/model hashes vẫn phải đúng contract |
| Transformer H | requirements/transformer.txt | transformers4.57.1, sklearn1.7.2, NumPy2.3.4; cần PyTorch phù hợp riêng |
| H CPU PyTorch wheel | requirements/torch-cpu.txt | torch2.14.1 từ CPU index; chỉ cài riêng, không propagate index sang dependency khác |

**Classical và H dùng venv khác nhau.** Không install tất cả requirement files
vào cùng một môi trường. H có SentencePiece/Accelerate/safetensors/protobuf/
py_vncorenlp như manifest cũ; PhoBERT thêm Java/local RDR assets theo H report.
Không download/train model chỉ để kiểm tra cleanup. Builder Excel JS cần
bundled artifact-tool của môi trường authoring; không thêm npm dependency vào
repo hoặc pip package Excel chỉ để chạy validator stdlib.

## Quick setup có chủ đích

```powershell
py -3.12 -m venv .venv-phase-e
.\.venv-phase-e\Scripts\python.exe -m pip install -r requirements/locks/classical-windows-py312.txt
.\.venv-phase-e\Scripts\python.exe -m pip install -r requirements/crawler.txt
.\.venv-phase-e\Scripts\python.exe -m unittest discover -s tests
```

Đây là setup cho test suite có optional sklearn/Selenium, không phải lệnh
train/crawl. DOM tests có thể mở trình duyệt fixture local; không đăng nhập
Facebook. Một số test integration cần nguồn local đúng manifest và quyền đọc
outputs; fresh checkout không tự có comment/workbook/model. Không giả fixture
thành dữ liệu nghiên cứu thiếu. Không sửa venv/profile hiện có để xử lý lỗi
dependency của môi trường khác. Các run lịch sử dùng CPython3.12.14 trên
Windows; runtime khác cần kiểm riêng, không tự coi lock cross-platform.

H, chỉ khi có nhiệm vụ experiment được phê duyệt:

```powershell
py -3.12 -m venv .venv-phase-h
.\.venv-phase-h\Scripts\python.exe -m pip install -r requirements/torch-cpu.txt
.\.venv-phase-h\Scripts\python.exe -m pip install -r requirements/transformer.txt
```

CUDA phải chọn wheel/runtime riêng rồi ghi vào run metadata; cleanup này không
đổi CPU thành GPU, không ghi đè local cache/checkpoint.

## Compatibility và nguồn pin duy nhất

Chín tên root requirements-* vẫn nhận `pip install -r` như trước nhưng chỉ
include nguồn chuẩn dưới requirements/. Expansion giữ nguyên package/version
và index options, kể cả lock/transitive deps. Bảng `underthesea==8.3.0` ngoài
lock có một owner segmentation.txt; classical-nlp include lại owner đó.
Không coi bản sao pin trong full research lock là duplication có thể tự sửa.

| Tên cũ | Nguồn chuẩn |
| --- | --- |
| requirements-data.txt | requirements/data.txt |
| requirements-crawler.txt | requirements/crawler.txt |
| requirements-baseline.txt | requirements/classical-base.txt |
| requirements-phase-e.txt | requirements/classical-nlp.txt |
| requirements-phase-e-lock.txt | requirements/locks/classical-windows-py312.txt |
| requirements-phase-e2.txt | requirements/analysis-plots.txt |
| requirements-phase-h.txt | requirements/transformer.txt |
| requirements-phase-h-torch-cpu.txt | requirements/torch-cpu.txt |
| requirements-phase-i3.txt | requirements/segmentation.txt |

Config/rules ở configs/ giữ nguyên path và byte. Mọi thay đổi dependency sau
này phải thuộc môi trường thích hợp, nêu run nào bị ảnh hưởng, giữ historical
lock và không âm thầm nâng package. Không tạo requirements-phase-x.txt mới
nếu chỉ thêm một dependency vào môi trường đã có.
