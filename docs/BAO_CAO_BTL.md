# Phân loại cảm xúc bình luận tiếng Việt về phim

**Bài tập lớn Xử lý dữ liệu văn bản · cmt-tag**

**Cập nhật 26/11/2026.** T2 đã khóa ở 613 câu. Thực nghiệm E+C đã chốt biến thể văn bản cho lượt chạy chính thức V2. T2 chưa chấm trong thiết kế này.

## 1. Bài toán

Dự đoán cảm xúc chung mà người viết thể hiện trong một bình luận Facebook về phim. Ba lớp là **POS** (tích cực), **NEG** (tiêu cực) và **NEU** (trung tính). Người gán đọc `text_clean` của chính bình luận. `REVIEW` dùng khi cần xem lại và `EXCLUDE` dùng cho mẫu bị loại theo [hướng dẫn gán nhãn](guidelines/SENTIMENT_GUIDELINE.md).

## 2. Dữ liệu và gán nhãn

Crawler thu bình luận theo từng bài. Bước tiền xử lý tối thiểu chuẩn hóa Unicode, giải mã thực thể HTML hợp lệ và xử lý khoảng trắng ngoài câu. Các lượt gán có thể lấy đề xuất từ ChatGPT, Claude và Gemini. Nhãn test do người gán chốt. Trên mẫu hiệu chuẩn C, 136/149 câu đồng thuận 3/3 khớp nhãn người. Trường hợp đúng hai AI trùng chỉ khớp 5/9 câu, số mẫu còn ít. [Chi tiết hiệu chuẩn](annotation/BAO_CAO_THUC_NGHIEM_V2_C_3_SEED.md)

## 3. T2 · Tập test chính

| Nguồn | Quyết định đã gán | POS | NEG | NEU | Số câu chấm |
| --- | ---: | ---: | ---: | ---: | ---: |
| T gốc | 202 | 55 | 61 | 73 | 189 |
| Test bổ sung | 450 | 119 | 145 | 160 | 424 |
| **T2** | **652** | **174** | **206** | **233** | **613** |

Trong 652 quyết định có 32 REVIEW và 7 EXCLUDE. Manifest lưu nguồn từng câu và SHA-256 của bản đang dùng. Hàng chờ 1.731 câu được giữ riêng và nằm ngoài train lẫn test của lượt chính thức này.

Phần bổ sung 424 câu đã được chấm trong một lượt thử nghiệm một seed. T gốc 189 câu chưa được chấm. Bảng kết quả tách điểm của hai phần và của toàn bộ T2.

## 4. Thiết kế thực nghiệm chính

### Nguồn train và kiểm tra rò rỉ

Dựng lại tập train từ E, C, U đã chốt và các nhãn mở rộng chunk 01–50 theo quy tắc chọn nhãn hiện hành. Chỉ dùng quyết định POS, NEG, NEU. Cả sáu mô hình dùng một danh sách train sau khi loại các mẫu trùng ID hoặc cùng bài với T2, trùng văn bản, hoặc gần trùng ở dạng gốc hay sau chuẩn hóa. Kiểm tra gần trùng dùng hàm hiện có của repo, với Jaccard ít nhất `0,9` trên cụm ba token và văn bản chuẩn hóa dài tối thiểu 40 ký tự.

### Chuẩn hóa văn bản

Khôi phục văn bản và ID lỗi Excel từ nguồn đã đối chiếu trước khi chạy phép chuẩn hóa. Dấu `=` đầu câu vẫn là chữ khi thuộc emoticon như `=)))`. ID lưu dưới dạng chuỗi. Với cả train và T2, chuẩn hóa NFC, xử lý ký tự điều khiển, giải mã HTML entity hợp lệ và chuẩn hóa khoảng trắng. Giữ emoji, emoticon và ký tự nối chuỗi emoji. Kết quả đối chứng E+C ở mục 6 chọn văn bản sau bước kỹ thuật này làm đầu vào chính thức, với cách viết tắt gốc của người dùng.

| Quy tắc | Số câu train thay đổi | Số câu T2 thay đổi |
| --- | ---: | ---: |
| Khôi phục văn bản lỗi Excel | — | — |
| Đối chiếu và khôi phục ID từ nguồn | — | — |
| Chuẩn hóa Unicode NFC | — | — |
| Xử lý ký tự điều khiển | — | — |
| Giải mã HTML entity | — | — |
| Chuẩn hóa khoảng trắng | — | — |
| **Số câu bị thay đổi bởi ít nhất một quy tắc** | **—** | **—** |

Một câu có thể xuất hiện ở nhiều hàng. Số liệu train ghi kèm số mẫu trước và sau lọc, cùng số loại theo từng lý do.

Chạy [script chuẩn hóa và nối nhãn](../scripts/prepare_v2_normalized.py) từ thư mục gốc repo. Dùng một thư mục đích mới dưới `outputs/`.

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_v2_normalized --output outputs/V2_chuan_hoa_chay_lai
```

Lượt này đã được tái lập với SHA-256 khớp cho năm tệp dữ liệu và thống kê. Sửa chính tả và áp dụng bảng viết tắt được để sang lượt phát triển riêng.

### Cấu hình mô hình

| Hạng mục | Cấu hình |
| --- | --- |
| Baseline | Giữ pipeline hiện có sau bước chuẩn hóa chung. Gồm BoW + MultinomialNB, BoW + ComplementNB, TF-IDF từ + LinearSVC và TF-IDF ký tự + LinearSVC. |
| PhoBERT | `vinai/phobert-base`, revision `01daacda68afe13d83023d16ec647239e344a1e6`. Chuẩn hóa chung rồi tách từ bằng PyVi. |
| ViSoBERT | `uitnlp/visobert`, revision `196a62afad9cbe4f52a54aabad828b13f0eec59a`. Dùng chuẩn hóa chung. |
| Khởi tạo | Tải trọng số pretrained gốc và khởi tạo đầu phân loại mới cho mỗi seed. |
| Fine-tune | 4 epoch, learning rate `2e-5`, batch 16, tối đa 128 token, warmup 10%, weight decay `0,01`, trọng số lớp `N / (3 × n_lớp)`. Dùng mô hình sau epoch cuối, với cấu hình cố định trước khi chấm. |
| Seed BERT | `20261123`, `20261124`, `20261125`. |
| Tái lập | Đóng băng SHA-256 của train, test, code và cấu hình trước khi gửi lượt chạy BERT lên Modal. Lệnh tái lập sẽ kiểm tra manifest trước khi chạy, sau đó ghi dự đoán theo ID, bảng điểm, thời gian và chi phí thực tế. |

## 5. Kết quả chính thức trên T2

**Chưa chạy.** Mỗi ô ghi macro-F1. Hai mô hình BERT báo mean ± độ lệch chuẩn mẫu qua ba seed. Bảng chi tiết ghi accuracy, F1 POS, F1 NEG và F1 NEU theo từng seed và theo ba phần test.

| Mô hình | T gốc (189) | Bổ sung (424) | T2 (613) |
| --- | ---: | ---: | ---: |
| BoW + MultinomialNB | — | — | — |
| BoW + ComplementNB | — | — | — |
| TF-IDF từ + LinearSVC | — | — | — |
| TF-IDF ký tự + LinearSVC | — | — | — |
| PhoBERT | — | — | — |
| ViSoBERT | — | — | — |

### Phân tích lỗi

Dùng ViSoBERT seed `20261123` cho ma trận nhầm lẫn trên T2. Hàng là nhãn người, cột là dự đoán. Bảng lỗi tổng hợp ghi số lượng theo cặp nhãn nhầm, nguồn thu thập và hai phần T gốc / bổ sung. Chọn 30 dự đoán sai theo cặp nhầm và nguồn bằng seed đã định trước. Văn bản và ID của mẫu phân tích lưu cục bộ.

| Nhãn người | Dự đoán POS | Dự đoán NEG | Dự đoán NEU |
| --- | ---: | ---: | ---: |
| POS | — | — | — |
| NEG | — | — | — |
| NEU | — | — | — |

## 6. Thử nghiệm phát triển

- Trên C và E+C, đã thử learning curve theo số chunk và cross-validation theo bài để so sánh các mô hình. [Báo cáo thực nghiệm C và E+C](annotation/BAO_CAO_THUC_NGHIEM_V2_C_3_SEED.md)
- Trên 424 câu bổ sung với một seed, macro-F1 của ViSoBERT, PhoBERT và baseline TF-IDF từ lần lượt là **0,7086**, **0,6639** và **0,6283**. [Chi tiết lượt thử nghiệm](annotation/BAO_CAO_TEST_BO_SUNG_V2.md)
- Trên 149 câu C với cùng 3.778 dòng train, thêm bộ quy tắc viết tắt sẵn có làm TF-IDF từ tăng macro-F1 từ **0,6558** lên **0,6620**, TF-IDF ký tự từ **0,5888** lên **0,5952**. Hai BoW + NB giữ nguyên điểm. Đây là đối chứng đầu vào mô hình. C không có token `ncc`, nên phép thử chưa đo được việc mở rộng token này hoặc ảnh hưởng đến chất lượng nhãn AI.

### Ablation viết tắt giữ sắc thái trên E+C

Bộ quy tắc [chuẩn hóa viết tắt](../scripts/apply_v2_abbreviations.py) gom các biến thể cảm thán về `vl` hoặc `đm` khi ngữ cảnh rõ. Các dạng `wtf`, `lmao`, `sml`, `như cc`, `ncc`, `44` và `đ` được giữ nguyên. Viết tắt ngắn đa nghĩa chỉ được mở rộng trong ngữ cảnh đã định hoặc được giữ nguyên. Có 2.229/5.998 câu trong danh sách ứng viên train và 246/613 câu T2 có thay đổi theo quy tắc. Đây là thống kê văn bản, chưa phải điểm trên T2.

Ablation dùng cùng 5 fold theo bài đã khóa cho từng seed `20261123` và `20261124`. Trong mỗi seed, tính macro-F1 trên 184 dự đoán ngoài fold của E+C. Hai biến thể dùng cùng ID train của từng fold, cùng pipeline mô hình và cùng cấu hình. Bản chuẩn hóa đổi 77/184 câu E+C và 1.450–1.459 câu trên 3.922–3.928 mẫu train mỗi fold. Kiểm tra trùng hoặc gần trùng sau chuẩn hóa không phát sinh mẫu train cần loại. T2 nằm ngoài ablation.

| Mô hình | Macro-F1 gốc | Macro-F1 chuẩn hóa | Accuracy gốc | Accuracy chuẩn hóa |
| --- | ---: | ---: | ---: | ---: |
| TF-IDF từ + LinearSVC | **0,6815 ± 0,0039** | 0,6615 ± 0,0072 | **0,6984 ± 0,0038** | 0,6821 ± 0,0038 |
| ViSoBERT | **0,8150 ± 0,0089** | 0,8061 ± 0,0036 | **0,8261 ± 0,0077** | 0,8179 ± 0,0038 |

Điểm ghi trung bình ± độ lệch chuẩn mẫu qua hai seed. ViSoBERT trên văn bản gốc đạt 0,8087 và 0,8212 macro-F1 theo từng seed, so với 0,8036 và 0,8087 khi chuẩn hóa viết tắt. Theo quy tắc ghi trước trong manifest đầu vào, chọn **văn bản gốc sau chuẩn hóa kỹ thuật**. Đây là quyết định dựa trên hai seed của tập dev E+C.

Hai nhánh ViSoBERT chạy đủ 20 lượt trên Modal A10 sau khi L4 chưa cấp container. Modal báo 0,5544 USD cho lượt A10 và 0,5613 USD tổng trên workspace mới khi tính cả kiểm tra GPU và lần khởi tạo L4. Các app đã dừng.

Manifest đầu vào có SHA-256 `ee3eeee892cd2183c57716411f93083694ca7e91c6bdb0e36ebc123fe13657e1`. Manifest kết quả chốt `selected_view=original` với SHA-256 `7027b20a0641f88714be512e2f14e6f3b33a9bd7695a7a14873011fc3202f70a`. Bảng điểm theo seed và dự đoán theo ID lưu cục bộ cùng manifest. Lượt chấm chính thức trên T2 vẫn đang chờ.

### Chuẩn hóa bản đọc V2

Bản đọc mở rộng viết tắt theo ngữ cảnh rồi sửa lỗi gõ đã có quy tắc rõ. Ví dụ, `ko bt` thành `không biết` và `xuất chiếu` thành `suất chiếu` trong câu về lịch rạp. Từ tục, emoji và emoticon được giữ nguyên. Trong 12.030 câu được rà chính tả ở phần ngoài T2 và hàng chờ test, có 50 lượt sửa trên 39 câu. Sheet **Chính tả** ghi các lượt sửa và 12 dạng còn cần xem ngữ cảnh. Bản đọc giữ nguyên 5.670 nhãn đã gán theo ID.

[Script Python chuẩn hóa bản đọc](../scripts/chuan_hoa_binh_luan_v2.py) đã đóng gói bảng quy tắc. Chạy trong CMD tại thư mục gốc repo.

```cmd
py -m pip install openpyxl
py -X utf8 scripts\chuan_hoa_binh_luan_v2.py --input "cmt.xlsx" --output "cmt_chuan_hoa.xlsx"
py -X utf8 scripts\chuan_hoa_binh_luan_v2.py --text "ko bt rạp có mấy xuất chiếu"
```

Chế độ Excel giữ các sheet, thêm cột **Bình luận chuẩn hóa** và có thể chỉ định cột nguồn bằng `--sheet`, `--column` và `--header-row`. Chế độ một câu chỉ cần Python. Đây là công cụ tạo bản đọc. Lượt chấm chính thức vẫn theo lựa chọn đầu vào của ablation ở trên.

Chạy thêm `--suggest` để xuất sheet **Gợi ý từ corpus** trong cùng Excel đầu ra. Script lấy những dạng xuất hiện tối đa ba lượt, tìm từ gần giống sau khi bỏ dấu và so số lượt cùng từ đứng cạnh. Cách làm này dùng tần suất trong file đầu vào để ưu tiên gợi ý cần đọc lại. Các mục ở sheet gợi ý chưa trở thành quy tắc tự sửa.

### Đối chiếu và ablation của `normalize_v2`

Hàm `normalize_v2(text)` đóng gói viết tắt theo ngữ cảnh và đúng 10 ánh xạ chính tả ở nhóm **Đã sửa**. Cùng một hàm áp dụng cho mọi câu. Hàm giữ từ tục và để nguyên các mục **Cần rà**. Sheet **Viết tắt đã sửa** dùng để đối chiếu 159 ánh xạ đã áp dụng.

Đối chiếu với cột **Sau chuẩn hóa** trên 14.408 bình luận cho kết quả **14.406 câu khớp**. Cả 613 câu T2 khớp. Hai câu sai khác đều thuộc hàng chờ test, có tổng cộng năm lượt `xuất chiếu → suất chiếu` từng bị bỏ qua ở bản Excel. Không có sai khác chưa giải thích. Danh sách đủ hai câu và manifest đối chiếu lưu cục bộ. Các kết quả trên là đối chiếu văn bản, chưa chấm T2.

So hai nhánh sau cùng một bước làm sạch kỹ thuật: giữ cách viết gốc và dùng `normalize_v2`. Dùng lại 5 fold theo bài cho mỗi seed `20261123` và `20261124`, cùng 3.922–3.928 mẫu train mỗi fold. Bộ quy tắc mới làm thay đổi 79/184 câu E+C. Kiểm tra gần trùng không phát sinh mẫu cần loại ở bất kỳ fold nào. Manifest đầu vào có SHA-256 `878e3c79808e9385a9fd02930a4bcf9c80e34a3fc419555c9dd724f5f055dbb1`. Giữ tiêu chí đã định trước là macro-F1 ViSoBERT ngoài fold trung bình, ưu tiên văn bản gốc nếu bằng điểm.

| Mô hình | Macro-F1 gốc | Macro-F1 `normalize_v2` | Accuracy gốc | Accuracy `normalize_v2` |
| --- | ---: | ---: | ---: | ---: |
| TF-IDF từ + LinearSVC | **0,6815 ± 0,0039** | 0,6681 ± 0,0022 | **0,6984 ± 0,0038** | 0,6875 ± 0,0038 |
| ViSoBERT | **0,8251 ± 0,0009** | 0,8080 ± 0,0103 | **0,8342 ± 0,0038** | 0,8207 ± 0,0077 |

Điểm là trung bình ± độ lệch chuẩn mẫu qua hai seed. Từng seed của ViSoBERT đạt 0,8258 và 0,8245 khi giữ cách viết gốc, so với 0,8007 và 0,8153 với `normalize_v2`. Chốt **văn bản gốc sau làm sạch kỹ thuật** theo tiêu chí đã định trước. Manifest kết quả ghi `selected_view=original` và có SHA-256 `6a03ce54523241bde48ccf642e15c1fb1ec42234c76c391561ce35d80b7d9234`.

Modal đã hoàn tất 20 lượt ViSoBERT trên A10 với chi phí 0,5190 USD trước tín dụng và đã dừng app. Các dự đoán ngoài fold và bảng điểm lưu cục bộ. T2 được dùng để đối chiếu văn bản với Excel. T2 chưa được dùng để chọn biến thể hoặc chấm điểm trong lượt này.
