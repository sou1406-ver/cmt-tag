# Phân loại cảm xúc bình luận tiếng Việt về phim

**Bài tập lớn Xử lý dữ liệu văn bản · cmt-tag**

**Cập nhật 27/11/2026.** Báo cáo trình bày kết quả của sáu mô hình, mỗi mô hình chạy ba seed trên cùng tập train 7.864 bình luận và tập test T2 gồm 613 bình luận.

## 1. Bài toán

Dự đoán cảm xúc chung mà người viết thể hiện trong một bình luận Facebook về phim. Ba lớp là **POS** (tích cực), **NEG** (tiêu cực) và **NEU** (trung tính). Người gán đọc `text_clean` của chính bình luận. `REVIEW` dùng khi cần xem lại và `EXCLUDE` dùng cho mẫu bị loại theo [hướng dẫn gán nhãn](guidelines/SENTIMENT_GUIDELINE.md).

### Cơ sở lý thuyết

**Biểu diễn văn bản.** Bag of Words (BoW) đếm số lần mỗi từ xuất hiện trong bình luận và bỏ qua thứ tự từ. TF-IDF tăng trọng số của đặc trưng hay xuất hiện trong một bình luận và giảm trọng số của đặc trưng phổ biến trên nhiều bình luận. Thực nghiệm dùng BoW unigram, TF-IDF unigram và bigram theo từ, cùng TF-IDF n-gram ký tự độ dài 3–5 trong từ. Từ vựng và IDF được học trên tập train. [1]

**Phân loại cổ điển.** Multinomial Naive Bayes ước lượng phân phối từ theo từng lớp dưới giả định các đặc trưng độc lập có điều kiện theo lớp. Complement Naive Bayes ước lượng trọng số từ các mẫu thuộc phần bù của từng lớp. LinearSVC học ranh giới tuyến tính để phân loại các vector TF-IDF. Với ba nhãn, mô hình học một bộ phân loại cho mỗi nhãn đối lập với các nhãn còn lại. [1–3]

**Mô hình ngôn ngữ tiền huấn luyện.** PhoBERT được tiền huấn luyện chuyên biệt cho tiếng Việt. ViSoBERT dùng kiến trúc XLM-R và được tiền huấn luyện trên văn bản mạng xã hội tiếng Việt. Hai mô hình biểu diễn văn bản theo ngữ cảnh, sau đó được fine-tune cùng đầu phân loại POS, NEG và NEU trên tập train của bài. [4–5]

**Chỉ số.** Accuracy là số câu dự đoán đúng chia cho tổng số câu. Với từng lớp, Precision là tỷ lệ dự đoán về lớp đó đúng, Recall là tỷ lệ mẫu thực tế thuộc lớp đó được nhận ra, và F1 là trung bình điều hòa của Precision và Recall. Macro-Precision, Macro-Recall và Macro-F1 lấy trung bình đơn giản qua ba lớp. Ma trận nhầm lẫn ghi số mẫu theo cặp nhãn thực tế và nhãn dự đoán. [6]

## 2. Dữ liệu và gán nhãn

Crawler thu bình luận theo từng bài. Bước tiền xử lý tối thiểu chuẩn hóa Unicode, giải mã thực thể HTML hợp lệ và xử lý khoảng trắng ngoài câu. Các lượt gán có thể lấy đề xuất từ ChatGPT, Claude và Gemini. Nhãn test do người gán chốt. Trên mẫu hiệu chuẩn C, 136/149 câu đồng thuận 3/3 khớp nhãn người. Trường hợp đúng hai AI trùng chỉ khớp 5/9 câu, số mẫu còn ít. [Chi tiết hiệu chuẩn](annotation/BAO_CAO_THUC_NGHIEM_V2_C_3_SEED.md)

## 3. T2 · Tập test chính

| Nguồn | Quyết định đã gán | POS | NEG | NEU | Số câu chấm |
| --- | ---: | ---: | ---: | ---: | ---: |
| T gốc | 202 | 55 | 61 | 73 | 189 |
| Test bổ sung | 450 | 119 | 145 | 160 | 424 |
| **T2** | **652** | **174** | **206** | **233** | **613** |

Trong 652 quyết định có 32 REVIEW và 7 EXCLUDE. Sáu mô hình được chấm trên toàn bộ 613 câu có nhãn POS, NEG hoặc NEU. Manifest lưu nguồn từng câu và SHA-256 của bản đang dùng.

## 4. Thiết kế thực nghiệm chính

### Nguồn train và kiểm tra rò rỉ

Qua hai lượt gán nhãn, GPT, Claude và Gemini cùng chọn một nhãn POS, NEG hoặc NEU cho **9.772/12.758** bình luận. Sau khi ghép thêm 957 câu E/C/U đã chốt, nhóm loại 2.842 câu cùng bài với T2 và 23 câu trùng văn bản với T2. Tập train cuối gồm **7.864** câu với 1.759 POS, 3.261 NEG và 2.844 NEU. Khi lọc train, nhóm kiểm tra trùng và gần trùng ở cả dạng gốc và dạng chuẩn hóa. Tiêu chí gần trùng là Jaccard ít nhất `0,9` trên cụm ba token với văn bản chuẩn hóa dài tối thiểu 40 ký tự. [Manifest train cuối](../outputs/06_Du_lieu_cuoi_V2/manifest.json)

### Chuẩn hóa văn bản

Khôi phục văn bản và ID lỗi Excel từ nguồn đã đối chiếu trước khi chạy phép chuẩn hóa. Dấu `=` đầu câu vẫn là chữ khi thuộc emoticon như `=)))`. ID lưu dưới dạng chuỗi. Với cả train và T2, chuẩn hóa NFC, xử lý ký tự điều khiển, giải mã HTML entity hợp lệ và chuẩn hóa khoảng trắng. Giữ emoji, emoticon và ký tự nối chuỗi emoji. Bộ đầu vào chính thức được chuẩn bị bằng `normalize_v2` đã duyệt theo yêu cầu. Kết quả đối chứng E+C ở mục 6 ghi riêng hiệu quả của việc giữ cách viết gốc.

Chạy [script chuẩn hóa và nối nhãn](../scripts/prepare_v2_normalized.py) từ thư mục gốc repo. Dùng một thư mục đích mới dưới `outputs/`.

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_v2_normalized --output outputs/V2_chuan_hoa_chay_lai
```

Lượt chuẩn hóa kỹ thuật đã được tái lập với SHA-256 khớp cho năm tệp dữ liệu và thống kê. Snapshot trước đợt gộp dùng 4.945 câu train và là nguồn của tập T2 đã khóa. Hai biến thể đầu vào của snapshot này có cùng ID và nhãn trên từng tập. Kết quả ở mục 5 dùng tập train cuối 7.864 câu và đầu vào `normalize_v2`.

| Vai trò | Thư mục đầu vào | SHA-256 manifest |
| --- | --- | --- |
| Trước đợt gộp · `normalize_v2` và tập T2 | `outputs/03_Dau_vao_chinh_thuc/` | `9573f5ebd776be8ee2de86667600abfd52b38c61ddf4ac3b273902045541f637` |
| Đối chứng trước đợt gộp · `original` | `outputs/04_Dau_vao_phu/` | `bb2bd66feb0bf58f7b6d521bfe64746cacd59a88f2e095a5dd4aabc635d46667` |

```powershell
.\.venv\Scripts\python.exe -m scripts.freeze_v2_official --input-view normalize_v2 --output outputs/V2_dong_bang_chay_lai
.\.venv\Scripts\python.exe -m scripts.freeze_v2_official --input-view original --output outputs/V2_doi_chieu_chay_lai
```

### Cấu hình mô hình

| Hạng mục | Cấu hình |
| --- | --- |
| Baseline | BoW + MultinomialNB, BoW + ComplementNB, TF-IDF từ + LinearSVC và TF-IDF ký tự + LinearSVC. Cả hai biến thể dùng `v2_baseline_model`: chuyển chữ thường, rút gọn chữ kéo dài, tách dấu câu và giữ emoji, emoticon ở bước tiền xử lý. `teencode=False`, `segment=False`. |
| PhoBERT | `vinai/phobert-base`, revision `01daacda68afe13d83023d16ec647239e344a1e6`. Chuẩn hóa chung rồi tách từ bằng PyVi. |
| ViSoBERT | `uitnlp/visobert`, revision `196a62afad9cbe4f52a54aabad828b13f0eec59a`. Dùng chuẩn hóa chung. |
| Khởi tạo | Tải trọng số pretrained gốc và khởi tạo đầu phân loại mới cho mỗi seed. |
| Fine-tune | 4 epoch, learning rate `2e-5`, batch 16, tối đa 128 token, warmup 10%, weight decay `0,01`, trọng số lớp `N / (3 × n_lớp)`. Dùng mô hình sau epoch cuối, với cấu hình cố định trước khi chấm. |
| Seed | `20261123`, `20261124`, `20261125` cho cả sáu mô hình. LinearSVC dùng `random_state` theo seed, hai biến thể Naive Bayes cho kết quả xác định trên cùng dữ liệu. |
| Tái lập | Các script kiểm tra SHA-256 của train, test và checkpoint. Dự đoán từng seed được đối chiếu theo ID và lưu cục bộ. |

`GOLD_CONFIG` cấu hình vectorizer và bộ phân loại. Bộ teencode nằm trong tiền xử lý tùy chọn đã dùng ở các lượt phát triển. So trên ví dụ tổng hợp, các ánh xạ `ko`, `k0`, `khong`, `hok`, `khum`, `đc`, `cx` có chỗ trùng. Quy tắc cũ đổi `hông` thành `không`, có thể đổi `đc comics` thành `được comics`, và xét `mn` theo ngữ cảnh khác. Hai biến thể chính thức cùng tắt bước teencode ở baseline để khác biệt đầu vào chỉ đến từ văn bản đã đóng băng.

## 5. Kết quả trên T2

Mỗi ô là trung bình ± độ lệch chuẩn mẫu qua ba seed. Mọi lượt chấm sử dụng cùng 613 câu T2. [Kết quả chi tiết theo seed](../outputs/08_Danh_gia_T2_V2_chi_tiet/manifest.json)

| Mô hình | Accuracy | Macro-Precision | Macro-Recall | Macro-F1 |
| --- | ---: | ---: | ---: | ---: |
| BoW + Multinomial NB | 0,6509 ± 0,0000 | 0,6577 ± 0,0000 | 0,6538 ± 0,0000 | 0,6507 ± 0,0000 |
| BoW + Complement NB | 0,6248 ± 0,0000 | 0,6312 ± 0,0000 | 0,6359 ± 0,0000 | 0,6232 ± 0,0000 |
| TF-IDF từ + LinearSVC | 0,6688 ± 0,0000 | 0,6774 ± 0,0000 | 0,6675 ± 0,0000 | 0,6682 ± 0,0000 |
| TF-IDF ký tự + LinearSVC | 0,6362 ± 0,0000 | 0,6401 ± 0,0000 | 0,6346 ± 0,0000 | 0,6368 ± 0,0000 |
| PhoBERT | 0,7238 ± 0,0034 | 0,7264 ± 0,0027 | 0,7266 ± 0,0043 | 0,7260 ± 0,0039 |
| ViSoBERT | 0,7292 ± 0,0016 | 0,7376 ± 0,0024 | 0,7266 ± 0,0013 | 0,7293 ± 0,0018 |

TF-IDF từ + LinearSVC có Macro-F1 cao nhất trong bốn baseline. Với cùng LinearSVC, TF-IDF từ đạt 0,6682 và TF-IDF ký tự đạt 0,6368. Với cùng BoW, Multinomial NB đạt 0,6507 và Complement NB đạt 0,6232. ViSoBERT đạt Macro-F1 trung bình cao nhất, hơn baseline tốt nhất 6,11 điểm phần trăm. PhoBERT và ViSoBERT có Macro-Recall trung bình cùng làm tròn thành 0,7266.

So sánh giữa hai nhóm BoW và TF-IDF phản ánh chênh lệch của cả đặc trưng lẫn thuật toán vì nhóm BoW dùng Naive Bayes còn nhóm TF-IDF dùng LinearSVC.

### Phân tích lỗi

Ma trận dưới đây dùng ViSoBERT seed `20261123`. Hàng là nhãn thực tế, cột là nhãn dự đoán. Mục Thực nghiệm của web cho phép chọn đủ sáu mô hình và ba seed. [Xem ma trận trên web](http://127.0.0.1:8768/#thuc-nghiem)

| Nhãn người | Dự đoán POS | Dự đoán NEG | Dự đoán NEU |
| --- | ---: | ---: | ---: |
| POS | **118** | 32 | 24 |
| NEG | 9 | **159** | 38 |
| NEU | 20 | 42 | **171** |

Hai ô ngoài đường chéo lớn nhất là 42 câu NEU bị dự đoán thành NEG và 38 câu NEG bị dự đoán thành NEU. Hai hướng này chiếm 80/165 lỗi của ViSoBERT ở seed trên.

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

Manifest đầu vào có SHA-256 `ee3eeee892cd2183c57716411f93083694ca7e91c6bdb0e36ebc123fe13657e1`. Manifest kết quả E+C chốt `selected_view=original` với SHA-256 `7027b20a0641f88714be512e2f14e6f3b33a9bd7695a7a14873011fc3202f70a`.

### Chuẩn hóa bản đọc V2

Bản đọc mở rộng viết tắt theo ngữ cảnh rồi sửa lỗi gõ đã có quy tắc rõ. Ví dụ, `ko bt` thành `không biết` và `xuất chiếu` thành `suất chiếu` trong câu về lịch rạp. Từ tục, emoji và emoticon được giữ nguyên. Trong 12.030 câu được rà chính tả ở phần ngoài T2 và hàng chờ test, có 50 lượt sửa trên 39 câu. Sheet **Chính tả** ghi các lượt sửa và 12 dạng còn cần xem ngữ cảnh. Bản đọc giữ nguyên 5.670 nhãn đã gán theo ID.

[Script Python chuẩn hóa bản đọc](../scripts/chuan_hoa_binh_luan_v2.py) đã đóng gói bảng quy tắc. Chạy trong CMD tại thư mục gốc repo.

```cmd
py -m pip install openpyxl
py -X utf8 scripts\chuan_hoa_binh_luan_v2.py --input "cmt.xlsx" --output "cmt_chuan_hoa.xlsx"
py -X utf8 scripts\chuan_hoa_binh_luan_v2.py --text "ko bt rạp có mấy xuất chiếu"
```

Chế độ Excel giữ các sheet, thêm cột **Bình luận chuẩn hóa** và có thể chỉ định cột nguồn bằng `--sheet`, `--column` và `--header-row`. Chế độ một câu chỉ cần Python.

Chạy thêm `--suggest` để xuất sheet **Gợi ý từ corpus** trong cùng Excel đầu ra. Script lấy những dạng xuất hiện tối đa ba lượt, tìm từ gần giống sau khi bỏ dấu và so số lượt cùng từ đứng cạnh. Cách làm này dùng tần suất trong file đầu vào để ưu tiên gợi ý cần đọc lại. Các mục ở sheet gợi ý chưa trở thành quy tắc tự sửa.

### Đối chiếu và ablation của `normalize_v2`

Hàm `normalize_v2(text)` đóng gói viết tắt theo ngữ cảnh và đúng 10 ánh xạ chính tả ở nhóm **Đã sửa**. Cùng một hàm áp dụng cho mọi câu. Hàm giữ từ tục và để nguyên các mục **Cần rà**. Sheet **Viết tắt đã sửa** dùng để đối chiếu 159 ánh xạ đã áp dụng.

Đối chiếu với cột **Sau chuẩn hóa** trên 14.408 bình luận lúc đó cho kết quả **14.406 câu khớp**. Cả 613 câu T2 khớp. Hai câu sai khác đều thuộc hàng chờ test, có tổng cộng năm lượt `xuất chiếu → suất chiếu` từng bị bỏ qua ở Excel. Hai câu đã cập nhật trong workbook chính.

So hai nhánh sau cùng một bước làm sạch kỹ thuật: giữ cách viết gốc và dùng `normalize_v2`. Dùng lại 5 fold theo bài cho mỗi seed `20261123` và `20261124`, cùng 3.922–3.928 mẫu train mỗi fold. Bộ quy tắc mới làm thay đổi 79/184 câu E+C. Kiểm tra gần trùng không phát sinh mẫu cần loại ở bất kỳ fold nào. Manifest đầu vào có SHA-256 `878e3c79808e9385a9fd02930a4bcf9c80e34a3fc419555c9dd724f5f055dbb1`. Giữ tiêu chí đã định trước là macro-F1 ViSoBERT ngoài fold trung bình, ưu tiên văn bản gốc nếu bằng điểm.

| Mô hình | Macro-F1 gốc | Macro-F1 `normalize_v2` | Accuracy gốc | Accuracy `normalize_v2` |
| --- | ---: | ---: | ---: | ---: |
| TF-IDF từ + LinearSVC | **0,6815 ± 0,0039** | 0,6681 ± 0,0022 | **0,6984 ± 0,0038** | 0,6875 ± 0,0038 |
| ViSoBERT | **0,8251 ± 0,0009** | 0,8080 ± 0,0103 | **0,8342 ± 0,0038** | 0,8207 ± 0,0077 |

Điểm là trung bình ± độ lệch chuẩn mẫu qua hai seed. Từng seed của ViSoBERT đạt 0,8258 và 0,8245 khi giữ cách viết gốc, so với 0,8007 và 0,8153 với `normalize_v2`. Chốt **văn bản gốc sau làm sạch kỹ thuật** theo tiêu chí đã định trước. Manifest kết quả ghi `selected_view=original` và có SHA-256 `6a03ce54523241bde48ccf642e15c1fb1ec42234c76c391561ce35d80b7d9234`.

Modal đã hoàn tất 20 lượt ViSoBERT trên A10 với chi phí 0,5190 USD trước tín dụng và đã dừng app. T2 chỉ được dùng để đối chiếu văn bản với Excel trong lượt này.

### Đối chiếu viết tắt và chính tả với nguồn ngoài

Trích các thay thế từ tập train của ViLexNorm (8.372 cặp bình luận gốc và chuẩn hóa do người chú giải), ghim revision `1070c6b9b00830fad278f48d9797df9ae1c942ac`. Dùng Viet74K tại revision `688b0953c8cdb21ee090ce80b83cefdb052fe2cd` để ghi nhận sự hiện diện của dạng gốc và dạng đề xuất. Hai nguồn lưu cục bộ. [Bài báo ViLexNorm, EACL 2024](https://aclanthology.org/2024.eacl-long.85/) · [Kho ViLexNorm](https://github.com/ngxtnhi/ViLexNorm) · [Viet74K](https://github.com/duyet/vietnamese-wordlist)

[Script đối chiếu](../scripts/audit_v2_external_lexicon.py) căn chỉnh từng cặp bình luận theo token, lấy cụm thay thế dài tối đa ba token mỗi phía và bỏ qua các dạng tục đã được bảo vệ. Một gợi ý cần ít nhất ba cặp hỗ trợ trong ViLexNorm và ít nhất ba bình luận V2 còn giữ dạng gốc trong bản đọc. Trên 12.030 bình luận ngoài T2 và hàng chờ test, thu được **207 dạng cần rà**. Ví dụ, `lun → luôn` có 87/126 câu hỗ trợ trong ViLexNorm và 99 câu V2 còn giữ `lun`. Từ `dị` xuất hiện cả trong cụm `kinh dị`, minh họa vì sao việc thay thế cần xét ngữ cảnh. Tần suất và kết quả tra từ điển dùng để rà thủ công. Bước đối chiếu này chưa đưa gợi ý vào `normalize_v2` hay huấn luyện lại mô hình.

Lọc đợt rà tiếp theo theo bốn điều kiện: dạng gốc vắng trong Viet74K, dạng đích có trong Viet74K, ít nhất năm câu ViLexNorm hỗ trợ, và tỷ lệ hỗ trợ ít nhất 70% trên số câu ViLexNorm có dạng gốc. Loại các dạng đa nghĩa đã liệt kê, từ tục, chữ kéo dài và các dạng từng được áp dụng trong bảng 159 dòng ánh xạ. Kết quả là **21 dạng đạt ngưỡng, tương ứng 166 lượt xuất hiện**, và **186 dạng bị loại**. Sheet **Gợi ý từ ViLexNorm** lưu ví dụ và lý do loại. Hai dạng `toy` và `sv` có ví dụ cần xét thêm theo ngữ cảnh trước khi duyệt.

### Ablation sau lượt duyệt ViLexNorm

Bổ sung 20 mục từ danh sách lọc sau khi bỏ `toy`. Các dạng `lun`, `rùi`, `mún`, `zậy` được duyệt tay. `sv` chỉ đổi khi có tín hiệu về trường, ngành hoặc năm học. Giữ `thanh kiu` trong các biến thể của *thank you*. Quy tắc mới làm đổi thêm **353/14.408 câu** so với code trước đó, gồm 138 ứng viên train, 158 câu corpus, 43 câu chờ, 13 câu T2 được chấm về sau và một câu T2 có nhãn ngoài ba lớp. Workbook cập nhật 355 câu vì còn hai trường hợp chính tả cũ chưa cập nhật ở hàng chờ. Nhãn giữ theo ID.

Hai biến thể dùng cùng 184 dự đoán ngoài fold E+C cho mỗi seed, 5 fold theo bài và hai seed `20261123`, `20261124`. Không phát sinh mẫu gần trùng cần loại thêm trong 10 fold. Macro-F1 và accuracy báo trung bình ± độ lệch chuẩn mẫu qua seed.

| Mô hình | Macro-F1 gốc | Macro-F1 `normalize_v2` | Accuracy gốc | Accuracy `normalize_v2` |
| --- | ---: | ---: | ---: | ---: |
| TF-IDF từ + LinearSVC | **0,6815 ± 0,0039** | 0,6687 ± 0,0108 | **0,6984 ± 0,0038** | 0,6875 ± 0,0115 |
| ViSoBERT | **0,8262 ± 0,0148** | 0,8100 ± 0,0232 | **0,8370 ± 0,0077** | 0,8234 ± 0,0192 |

| Seed | TF-IDF gốc | TF-IDF chuẩn hóa | ViSoBERT gốc | ViSoBERT chuẩn hóa |
| --- | ---: | ---: | ---: | ---: |
| `20261123` | 0,6788 | 0,6611 | 0,8157 | 0,7936 |
| `20261124` | 0,6843 | 0,6763 | 0,8366 | 0,8264 |

Macro-F1 trên E+C nghiêng về giữ cách viết gốc ở cả hai mô hình. Lượt T2 ở mục 5 sử dụng `normalize_v2`, với các thay thế được ghi trong code và workbook. ViSoBERT hoàn tất 20 lượt E+C trên Modal A10. Tổng thời gian huấn luyện ghi trong log là 1.265,66 giây GPU. SHA-256 manifest E+C đầu vào `cace1f591e393c4f36d9a81ffde0cabe27b88a2c6ef4a708f746aa0b73b20612`, manifest kết quả `c8582c03a6b8d00ed660c8151adcb97566376b0facebfb02840449533961ebb6`.

## 7. Kết luận

Trong sáu mô hình chấm trên T2, ViSoBERT đạt Macro-F1 trung bình 0,7293 và Accuracy trung bình 0,7292. TF-IDF theo từ + LinearSVC dẫn nhóm baseline với Macro-F1 0,6682. Ma trận nhầm lẫn của ViSoBERT cho thấy lỗi tập trung giữa lớp trung tính và tiêu cực. Kết quả tổng hợp mô tả hiệu suất trên tập T2 đã khóa với ba seed sử dụng cùng tập train.

## Tài liệu tham khảo

1. Christopher D. Manning, Prabhakar Raghavan và Hinrich Schütze (2008). *Introduction to Information Retrieval*. Cambridge University Press. [Sách trực tuyến](https://nlp.stanford.edu/IR-book/)
2. Jason D. M. Rennie, Lawrence Shih, Jaime Teevan và David R. Karger (2003). *Tackling the Poor Assumptions of Naive Bayes Text Classifiers*. ICML. [Bài báo](https://people.csail.mit.edu/jrennie/papers/icml03-nb.pdf)
3. Corinna Cortes và Vladimir Vapnik (1995). *Support-Vector Networks*. Machine Learning, 20, 273–297. [Bài báo](https://doi.org/10.1007/BF00994018) · [Tài liệu LinearSVC](https://scikit-learn.org/stable/modules/generated/sklearn.svm.LinearSVC.html)
4. Dat Quoc Nguyen và Anh Tuan Nguyen (2020). *PhoBERT: Pre-trained language models for Vietnamese*. Findings of EMNLP. [ACL Anthology](https://aclanthology.org/2020.findings-emnlp.92/)
5. Nam Nguyen, Thang Phan, Duc-Vu Nguyen và Kiet Nguyen (2023). *ViSoBERT: A Pre-Trained Language Model for Vietnamese Social Media Text Processing*. EMNLP. [ACL Anthology](https://aclanthology.org/2023.emnlp-main.315/)
6. Nhóm phát triển scikit-learn. *Metrics and scoring: quantifying the quality of predictions*. [Tài liệu chỉ số](https://scikit-learn.org/stable/modules/model_evaluation.html)
