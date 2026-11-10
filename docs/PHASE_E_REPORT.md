# Kết quả Phase E trên 346 nhãn người

Chạy ngày 11/11/2026 trên đúng bộ nhãn đã chạy baseline, không phải chờ gán
thêm. Có 26 cấu hình báo cáo, 78 lần fit trong run chính, giữ nguyên ba fold
chia nhóm theo bài. B0 tái tạo đúng toàn bộ metrics cũ của LR/SVM balanced và
NB; không thay guideline, nhãn, text_raw, split hoặc cách chọn mẫu.

## Kết quả chính

Char TF-IDF + LinearSVC balanced là cấu hình tốt nhất trước mask: Macro-F1
**0,5802**, so với word TF-IDF cùng SVM balanced **0,4561**. Recall POS tăng
0,3182 → 0,4364, NEU 0,1957 → 0,4239; recall NEG giảm 0,9236 → 0,8819.
Đây là cải thiện OOF quan sát trên dữ liệu phát triển, chưa được kiểm chứng
trên test độc lập. Đỉnh baseline cũ gồm mask là LR 0,4828; không so con số đó
như một ablation chỉ đổi feature vì model và mask cũng khác nhau.

B6 sau khi cô lập đúng tác động mask đạt **0,5729**, thấp hơn B3 khoảng
0,0073; chưa thấy lợi ích từ mask ở phép thử này. Lượt kiểm tra ban đầu dùng
masker cũ còn NFC-normalize, đã được giữ trong support và không dùng làm run
chính. B0–B5 tái tạo y hệt sau sửa; không đổi tham số để chọn điểm cao hơn.

Bảng sau lấy cấu hình tốt nhất trong từng biến thể, nên có thể khác model:

| Biến thể | Model / class_weight | Macro-F1 | Recall POS | Recall NEG | Recall NEU |
|---|---|---:|---:|---:|---:|
| B0 | lr / balanced | 0.4575 | 0.3000 | 0.9167 | 0.2174 |
| B1 | lr / balanced | 0.4721 | 0.3364 | 0.9375 | 0.2065 |
| B2 | svm / balanced | 0.4844 | 0.3545 | 0.9375 | 0.2174 |
| B3 | svm / balanced | 0.5802 | 0.4364 | 0.8819 | 0.4239 |
| B4 | svm / balanced | 0.5192 | 0.4000 | 0.8958 | 0.2826 |
| B5 | lr / balanced | 0.5173 | 0.3818 | 0.8889 | 0.3043 |
| B6 | svm / balanced | 0.5729 | 0.4273 | 0.8819 | 0.4130 |

So sánh như nhau về classifier và class_weight để đọc tác động ablation:

| Biến thể | LR None | LR balanced | SVM None | SVM balanced |
|---|---:|---:|---:|---:|
| B0 | 0.3133 | 0.4575 | 0.4047 | 0.4561 |
| B1 | 0.3134 | 0.4721 | 0.4106 | 0.4530 |
| B2 | 0.3023 | 0.4664 | 0.4262 | 0.4844 |
| B3 | 0.3603 | 0.5418 | 0.5351 | 0.5802 |
| B4 | 0.3471 | 0.5046 | 0.4773 | 0.5192 |
| B5 | 0.3511 | 0.5173 | 0.4859 | 0.5158 |

Word segmentation có cải thiện ở SVM balanced trong bộ này, nhưng không vượt
char-only. Ghép word+char với tỷ trọng cố định 1:1 cũng chưa vượt char-only.
Teencode có lợi cho LR, nhưng giảm nhẹ SVM khi so B5 với B4; không kết luận
mọi chuẩn hóa đều tốt hoặc đều vô ích. B1 gộp các bước chuẩn hóa nhẹ nên không
quy tác động riêng emoji chỉ từ chênh lệch B1/B0.

## Lỗi còn lại và giới hạn

Ở B3, đúng 48/110 POS, 127/144 NEG và 39/92 NEU. Vẫn có 45 POS và 31 NEU bị
đoán NEG. Chủ đề nguồn Mưa Đỏ có 171 câu được đánh giá và 94 lỗi; precision
NEG trong nhóm này chỉ khoảng 0,081 (5 đúng trong 62 dự đoán NEG).
Một số phim khác có tỷ lệ đúng cao nhưng chủ yếu toàn NEG: ví dụ Thor có
12 NEG trong 14 câu, cả một POS và một NEU đều bị đoán sai. Không lấy tỷ lệ
đúng ở nhóm nhỏ/thiếu lớp làm bằng chứng khái quát tốt sang phim đó.

Dữ liệu ít, lệch theo nguồn/phim và được chọn có chủ đích; movie_id chỉ là chủ
đề bài nguồn. Chọn recipe/model/weight trên cùng CV làm điểm của cấu hình
thắng có selection optimism. Chưa đặt ngưỡng F1 cứng để quyết định mở rộng.
Kết quả hỗ trợ giữ char-SVM làm mốc tiếp theo, không chứng minh dữ liệu/nhãn
đã đủ hoặc bỏ qua nhu cầu có test độc lập.

Giai đoạn hiện tại chỉ thử tín hiệu trên 346 nhãn người. Chưa cào thêm, chưa
gọi ChatGPT/Claude gán nhãn. Nếu mở rộng sau này: hai AI gán độc lập, bất đồng
và một mẫu ngẫu nhiên trong nhóm đồng ý đều cần người kiểm tra; giữ riêng nhãn
người, nhãn AI đã xác nhận và silver chưa xác nhận. So sánh human-only với
human+silver bằng test từ bài/phim chưa dùng phát triển guideline/chọn model.
Không coi đồng thuận hai AI là ground truth.

## Chạy lại và artifact

```powershell
.\.venv-crawler\Scripts\python.exe -m venv .venv-phase-e
.\.venv-phase-e\Scripts\python.exe -m pip install -r requirements-phase-e-lock.txt
.\.venv-phase-e\Scripts\python.exe scripts/run_preprocessing_experiments.py
```

Dùng môi trường riêng, giữ nguyên venv crawler/baseline cũ. Đầu vào local phải
khớp checksum trong configs/preprocessing_experiments.json; không tái chia
fold hoặc nới khóa để dùng nhầm dữ liệu. Output đã tồn tại sẽ bị từ chối;
chọn --output khác khi cần một run mới. Không sửa artifact đã ghi nhận.

Thư mục `outputs/phase_e/` có comparison.csv, metrics.json, predictions.csv,
preprocessed.jsonl, normalization_counts.json, errors.csv,
errors_by_class_and_movie.json, processed_cross_fold_collisions.json,
locked_plan.json, experiment_config.json, environment.json, warnings.json,
REPORT.md và manifest.json. Tất cả 26 confusion matrices có trong metrics và
phần chi tiết dưới đây. Artifacts chứa dữ liệu từng câu giữ local; Git chỉ
chia sẻ code/config/dependencies/test và báo cáo tổng hợp.

API tách từ đã đối chiếu với model cài đặt, chạy offline bằng
[Underthesea 8.3.0](https://pypi.org/project/underthesea/8.3.0/), dùng
[word_tokenize format=text](https://undertheseanlp.github.io/underthesea/docs/next/api/word-tokenize)
và tắt use_token_normalize. Hash ba file model tách từ được lưu trong
môi trường run. Quy tắc emoji dùng mã codepoint trung tính, không gán nhãn
cảm xúc từ ký hiệu; vl/vch và từ phủ định được giữ nguyên.

Kiểm tra cuối: **164/164 test pass** (27,234 giây). Có regression cho socket
offline, Unicode/phủ định, emoji/emoticon, bảo toàn raw khi mask, teencode
có/không bật, không đổi fold, không học vocabulary validation, tái tạo B0,
config thay giữa chừng và rollback. B2 thực tế chạy toàn bộ 346 câu bằng model
local; không chỉ dùng segmenter giả trong unit test.

## Báo cáo run đầy đủ

Thăm dò trên 346 nhãn người, đúng ID/fold của plan đã khóa.
Không đổi text_raw, nhãn, guideline hoặc split. TF-IDF chỉ fit trong train từng
fold; không dùng test độc lập. B0 balanced/NB tái tạo đúng metrics baseline cũ.

### Thiết kế

B0 raw word(1,2); B1 NFC/khoảng trắng/lowercase + emoji/emoticon trung tính;
B2 B1 + underthesea 8.3.0, use_token_normalize=False; B3 raw char_wb(3,5);
B4 B1 word+char với trọng số 1:1, L2 sau nối; B5 B4 + ko/khum/đc/k có kiểm soát.
Mask B6 khớp alias NFC/NFD nhưng giữ nguyên Unicode ở phần không thay tên,
không lẫn thêm bước chuẩn hóa NFC vào parent raw/char. Chế độ mask Phase D cũ
giữ hành vi mặc định; chỉ Phase E dùng chế độ bảo toàn raw này.
Không thay vl/vch, bỏ phủ định/dấu tiếng Việt hoặc lọc stopwords.
k sau số được giữ (100 k), k độc lập ở ngữ cảnh khác là giả định của B5 và có
thể sai. Emoji/emoticon mã hóa theo ký tự, không gán POS/NEG theo biểu tượng.
Các bước chuẩn hóa là quy tắc cố định không học từ nhãn. Segmenter dùng model
đóng gói sẵn; kết nối mạng bị chặn suốt quá trình biến đổi và huấn luyện.

LR và LinearSVC C=1, None/balanced; NB alpha=1 chỉ ở B0 để tham chiếu.
Chọn B0–B5 theo pooled OOF Macro-F1, hòa điểm giữ thứ tự config. B6 chỉ thêm
mask vào đúng recipe/model/weight thắng; không đổi mask sau khi xem điểm.
Đây là lựa chọn trên cùng CV phát triển nên có selection optimism; điểm của
biến thể thắng không phải ước lượng độc lập về hiệu năng ngoài thực tế.

### So sánh

| Run | Macro-F1 OOF | Recall POS | Recall NEG | Recall NEU |
|---|---:|---:|---:|---:|
| B0_lr_none | 0.3133 | 0.1545 | 0.9722 | 0.0435 |
| B0_lr_balanced | 0.4575 | 0.3000 | 0.9167 | 0.2174 |
| B0_svm_none | 0.4047 | 0.2818 | 0.9306 | 0.1196 |
| B0_svm_balanced | 0.4561 | 0.3182 | 0.9236 | 0.1957 |
| B0_nb_none | 0.2946 | 0.1727 | 0.9514 | 0.0109 |
| B1_lr_none | 0.3134 | 0.1545 | 0.9722 | 0.0435 |
| B1_lr_balanced | 0.4721 | 0.3364 | 0.9375 | 0.2065 |
| B1_svm_none | 0.4106 | 0.2909 | 0.9375 | 0.1196 |
| B1_svm_balanced | 0.4530 | 0.3273 | 0.9375 | 0.1739 |
| B2_lr_none | 0.3023 | 0.1727 | 0.9444 | 0.0217 |
| B2_lr_balanced | 0.4664 | 0.3545 | 0.9306 | 0.1848 |
| B2_svm_none | 0.4262 | 0.3000 | 0.9375 | 0.1413 |
| B2_svm_balanced | 0.4844 | 0.3545 | 0.9375 | 0.2174 |
| B3_lr_none | 0.3603 | 0.1909 | 0.9306 | 0.1087 |
| B3_lr_balanced | 0.5418 | 0.3545 | 0.8611 | 0.4239 |
| B3_svm_none | 0.5351 | 0.4091 | 0.8958 | 0.3152 |
| B3_svm_balanced | 0.5802 | 0.4364 | 0.8819 | 0.4239 |
| B4_lr_none | 0.3471 | 0.2364 | 0.9514 | 0.0435 |
| B4_lr_balanced | 0.5046 | 0.3727 | 0.8681 | 0.2935 |
| B4_svm_none | 0.4773 | 0.3545 | 0.9097 | 0.2174 |
| B4_svm_balanced | 0.5192 | 0.4000 | 0.8958 | 0.2826 |
| B5_lr_none | 0.3511 | 0.2455 | 0.9514 | 0.0435 |
| B5_lr_balanced | 0.5173 | 0.3818 | 0.8889 | 0.3043 |
| B5_svm_none | 0.4859 | 0.3727 | 0.9167 | 0.2174 |
| B5_svm_balanced | 0.5158 | 0.3909 | 0.8958 | 0.2826 |
| B6_masked_parent_B3_svm_balanced | 0.5729 | 0.4273 | 0.8819 | 0.4130 |

B0 tốt nhất: B0_lr_balanced (0.4575). Parent chọn cho B6:
B3_svm_balanced (0.5802); sau mask
0.5729. Không khẳng định khác biệt có ý nghĩa thống kê.

### Số câu thực sự thay đổi

Đếm trên đúng 346 câu. Thay đổi text do lowercase/khoảng
trắng chưa chắc đổi vector vì vectorizer B0 vốn lowercase và tách bằng regex.

| Biến thể | Tổng câu đổi text | Số câu theo bước |
|---|---:|---|
| B0 | 0 | {"total_changed": 0} |
| B1 | 310 | {"unicode_nfc": 3, "whitespace": 62, "lowercase": 284, "emoticon_tokens": 34, "emoji_tokens": 93, "final_whitespace": 124, "total_changed": 310} |
| B2 | 339 | {"unicode_nfc": 3, "whitespace": 62, "lowercase": 284, "emoticon_tokens": 34, "emoji_tokens": 93, "segmentation": 331, "final_whitespace": 0, "total_changed": 339} |
| B3 | 0 | {"total_changed": 0} |
| B4 | 310 | {"unicode_nfc": 3, "whitespace": 62, "lowercase": 284, "emoticon_tokens": 34, "emoji_tokens": 93, "final_whitespace": 124, "total_changed": 310} |
| B5 | 319 | {"unicode_nfc": 3, "whitespace": 62, "lowercase": 284, "emoticon_tokens": 34, "emoji_tokens": 93, "teencode": 74, "final_whitespace": 124, "total_changed": 319} |
| B6 | 43 | {"entity_mask": 43, "total_changed": 43} |

Chi tiết số lần thay token có trong normalization_counts.json. Text view và
hash raw ở preprocessed.jsonl, không ghi đè annotation. Cặp text sau biến đổi
giống nhau nhưng nằm khác fold: {"B0": 0, "B1": 0, "B2": 0, "B3": 0, "B4": 0, "B5": 0, "B6": 0}.
Giữ nguyên fold theo yêu cầu; các cặp này được ghi để diễn giải kết quả.

### Lỗi theo chủ đề phim nguồn

Run parent tốt nhất B0–B5; correct_rate là tỷ lệ đúng trong từng nhóm nhỏ,
không phải hiệu năng tổng quát trên phim chưa xuất hiện khi train. movie_id là
chủ đề bài nguồn, comment có thể nói phim khác. Chi tiết từng lớp và mọi run
trong errors_by_class_and_movie.json; các câu sai ở errors.csv để người đọc rà,
không tự đổi nhãn theo model.

| Chủ đề phim | Số câu | Số lỗi | Tỷ lệ đúng mô tả |
|---|---:|---:|---:|
| mua_do | 171 | 94 | 0.4503 |
| thor_love_and_thunder | 14 | 3 | 0.7857 |
| ant_man_and_the_wasp_quantumania | 13 | 2 | 0.8462 |
| avatar_2 | 13 | 5 | 0.6154 |
| mat_biec | 13 | 2 | 0.8462 |
| interstellar | 12 | 6 | 0.5000 |
| insidious_the_red_door | 11 | 2 | 0.8182 |
| lat_mat_8 | 11 | 1 | 0.9091 |
| quy_nhap_trang_2 | 11 | 3 | 0.7273 |
| joker_2 | 10 | 0 | 1.0000 |
| dune_2 | 9 | 1 | 0.8889 |
| bo_tu_bao_thu | 8 | 0 | 1.0000 |
| nguoi_vo_cuoi_cung | 8 | 1 | 0.8750 |
| nha_ba_nu | 6 | 1 | 0.8333 |
| rom | 6 | 1 | 0.8333 |
| nha_gia_tien | 5 | 1 | 0.8000 |
| tiec_trang_mau | 5 | 1 | 0.8000 |
| lat_mat_6 | 4 | 2 | 0.5000 |
| joker | 3 | 1 | 0.6667 |
| parasite | 3 | 1 | 0.6667 |
| resident_evil_2026 | 3 | 2 | 0.3333 |
| jojo_rabbit | 2 | 0 | 1.0000 |
| mai | 2 | 1 | 0.5000 |
| the_dark_knight | 2 | 1 | 0.5000 |
| dao_pho_va_piano | 1 | 0 | 1.0000 |

### Confusion matrices

Hàng là nhãn người, cột là dự đoán, cùng thứ tự POS/NEG/NEU.

#### B0_lr_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 17 | 92 | 1 |
| NEG | 4 | 140 | 0 |
| NEU | 11 | 77 | 4 |
#### B0_lr_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 33 | 69 | 8 |
| NEG | 8 | 132 | 4 |
| NEU | 22 | 50 | 20 |
#### B0_svm_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 31 | 73 | 6 |
| NEG | 9 | 134 | 1 |
| NEU | 22 | 59 | 11 |
#### B0_svm_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 35 | 68 | 7 |
| NEG | 8 | 133 | 3 |
| NEU | 25 | 49 | 18 |
#### B0_nb_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 19 | 91 | 0 |
| NEG | 7 | 137 | 0 |
| NEU | 19 | 72 | 1 |
#### B1_lr_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 17 | 92 | 1 |
| NEG | 4 | 140 | 0 |
| NEU | 10 | 78 | 4 |
#### B1_lr_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 37 | 61 | 12 |
| NEG | 7 | 135 | 2 |
| NEU | 20 | 53 | 19 |
#### B1_svm_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 32 | 68 | 10 |
| NEG | 7 | 135 | 2 |
| NEU | 20 | 61 | 11 |
#### B1_svm_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 36 | 63 | 11 |
| NEG | 7 | 135 | 2 |
| NEU | 20 | 56 | 16 |
#### B2_lr_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 19 | 91 | 0 |
| NEG | 7 | 136 | 1 |
| NEU | 7 | 83 | 2 |
#### B2_lr_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 39 | 60 | 11 |
| NEG | 9 | 134 | 1 |
| NEU | 23 | 52 | 17 |
#### B2_svm_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 33 | 69 | 8 |
| NEG | 8 | 135 | 1 |
| NEU | 18 | 61 | 13 |
#### B2_svm_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 39 | 60 | 11 |
| NEG | 8 | 135 | 1 |
| NEU | 21 | 51 | 20 |
#### B3_lr_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 21 | 84 | 5 |
| NEG | 8 | 134 | 2 |
| NEU | 15 | 67 | 10 |
#### B3_lr_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 39 | 51 | 20 |
| NEG | 11 | 124 | 9 |
| NEU | 20 | 33 | 39 |
#### B3_svm_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 45 | 53 | 12 |
| NEG | 10 | 129 | 5 |
| NEU | 21 | 42 | 29 |
#### B3_svm_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 48 | 45 | 17 |
| NEG | 10 | 127 | 7 |
| NEU | 22 | 31 | 39 |
#### B4_lr_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 26 | 83 | 1 |
| NEG | 6 | 137 | 1 |
| NEU | 13 | 75 | 4 |
#### B4_lr_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 41 | 60 | 9 |
| NEG | 12 | 125 | 7 |
| NEU | 25 | 40 | 27 |
#### B4_svm_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 39 | 63 | 8 |
| NEG | 9 | 131 | 4 |
| NEU | 21 | 51 | 20 |
#### B4_svm_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 44 | 56 | 10 |
| NEG | 11 | 129 | 4 |
| NEU | 20 | 46 | 26 |
#### B5_lr_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 27 | 82 | 1 |
| NEG | 6 | 137 | 1 |
| NEU | 13 | 75 | 4 |
#### B5_lr_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 42 | 56 | 12 |
| NEG | 9 | 128 | 7 |
| NEU | 25 | 39 | 28 |
#### B5_svm_none

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 41 | 61 | 8 |
| NEG | 8 | 132 | 4 |
| NEU | 22 | 50 | 20 |
#### B5_svm_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 43 | 57 | 10 |
| NEG | 11 | 129 | 4 |
| NEU | 20 | 46 | 26 |
#### B6_masked_parent_B3_svm_balanced

| Người gán / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 47 | 46 | 17 |
| NEG | 9 | 127 | 8 |
| NEU | 21 | 33 | 38 |

### Giới hạn và kiểm tra

346 nhãn, một người gán, chọn mẫu có chủ đích và phụ thuộc phim/nguồn; chưa có
gold test độc lập. Không kết luận thiếu dữ liệu hay feature là nguyên nhân duy
nhất từ các ablation này. Không thêm dữ liệu hoặc sửa guideline để làm đẹp điểm.
Độ phủ mask/teencode/emoji và số lượng theo lớp cần đọc cùng điểm số. Underthesea
là model tách từ pretrained, không được fit trên toàn bộ nhãn hiện tại.

Config, plan nguyên byte, môi trường và checksum model tách từ được lưu cùng
artifact. Cảnh báo runtime: [].
