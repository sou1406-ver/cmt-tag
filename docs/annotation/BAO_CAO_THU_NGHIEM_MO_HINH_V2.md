# Báo cáo tiến độ gán nhãn và thử nghiệm mô hình V2

Cập nhật ngày 24/11/2026

Đã đối chiếu đủ **50 chunk đầu, tương ứng 5.000 bình luận**, qua GPT, Claude và Gemini. Lượt gán lại có 1.223 câu. GPT và Claude đã trả đủ nhãn, còn Gemini đã trả 1.100 câu. Phép thử mô hình dùng 3.005 câu train được chọn từ hai lượt gán. Trên tập chấm chung có nhãn người, PhoBERT dẫn đầu với macro-F1 **0,736**.

## Gán nhãn lượt 1

Pool mở rộng có 8.965 câu, chia thành 90 chunk. Đợt này dừng ở chunk 50. Đã lưu và đối chiếu **150 file nhãn** với danh sách ID nguồn. Ở chunk 32, một ID Claude bị gõ sai đã được thay bằng ID đúng và bổ sung nhãn `NEG`. ID này hiện có cùng nhãn từ cả ba model.

| Kết quả sau khi sửa chunk 32 | Số câu |
|---|---:|
| Đồng thuận POS | 819 |
| Đồng thuận NEG | 1.707 |
| Đồng thuận NEU | 1.223 |
| Đồng thuận `REVIEW` | 11 |
| Đồng thuận `EXCLUDE` | 18 |
| Khác nhãn | 1.222 |
| **Tổng** | **5.000** |

Ba model trùng nhãn trên **3.778/5.000 câu (75,56%)**, trong đó 3.749 câu có nhãn POS, NEG hoặc NEU. Chi tiết các phép thử trước ở mốc 01–20 nằm trong [báo cáo gán nhãn V2](BAO_CAO_GAN_NHAN_V2.md).

## Gán lại và duyệt tay

Đã xuất bộ gán mù gồm 1.222 câu khác nhãn và một câu thiếu nhãn Claude lúc xuất. Sau khi nhận nhãn bổ sung cho chunk 32, danh sách vẫn giữ nguyên thứ tự để khớp với các lượt gán đã gửi.

| Kết quả lượt 2 | Số câu |
|---|---:|
| Cả ba trùng một nhãn POS, NEG hoặc NEU | 154 |
| Hai phiếu cùng nhãn và phiếu còn lại là `REVIEW` | 66 |
| Hai phiếu trùng, phiếu còn lại khác `REVIEW` | 736 |
| Cả ba phiếu khác nhau | 143 |
| Cả ba cùng trả `REVIEW` | 1 |
| Chờ Gemini | 123 |
| **Tổng** | **1.223** |

Quy tắc gộp 66 câu có hai phiếu trùng và một phiếu `REVIEW` cho ra 65 nhãn cảm xúc và một `EXCLUDE`. Bản Excel duyệt tay hiện có **1.003 câu**. Trong đó 144 câu cần xem kỹ vì cả ba khác nhãn hoặc cùng trả `REVIEW`, 736 câu đã có sẵn nhãn đa số để duyệt và 123 câu đang chờ Gemini.

| File đã xuất | Nội dung |
|---|---|
| `U_recheck_01_50.csv` | 1.223 câu để gán mù, gồm ID và nội dung |
| `Ket_qua_gan_lai_turn_2.xlsx` | Bảng đối chiếu nhãn, ghi chú, mức đồng thuận và nhãn đa số |
| `Gan_rieng_turn_2_kem_nhan.xlsx` | 1.003 câu chưa chốt, có phiếu từng model và cột trống để điền nhãn người duyệt |

Các file gán nhãn, nội dung bình luận và bản Excel lưu cục bộ trong `outputs/annotation_expansion_round_01/`. Phần chờ xử lý gồm 123 phiếu Gemini, các câu còn cần chốt và chunk 51–90 của pool mở rộng.

## Thử nghiệm PhoBERT, ViSoBERT và baseline

Ngày chạy 23/11/2026

### Dữ liệu

Phép thử dùng ba nhãn cảm xúc POS, NEG và NEU. Một câu vào tập ứng viên khi ba model đồng thuận ở lượt 1 hoặc lượt 2. Ở lượt 2, hai model cùng một nhãn cảm xúc và model còn lại trả `REVIEW` cũng được tính là đồng thuận theo quy tắc đã chọn. Các câu còn thiếu phiếu, đồng thuận ở `REVIEW` hoặc `EXCLUDE`, hay còn khác nhãn ngoài quy tắc này không vào tập train. Với các câu có nhãn cảm xúc đồng thuận từ lượt 1, phép thử dùng nhãn của lượt đó.

| Nguồn nhãn | Ứng viên | Sau lọc train |
|---|---:|---:|
| Lượt 1, đồng thuận 3/3 | 3.749 | 2.841 |
| Lượt 2, đồng thuận 3/3 | 153 | 117 |
| Lượt 2, hai phiếu giống nhau và một `REVIEW` | 65 | 47 |
| **Tổng** | **3.967** | **3.005** |

Lọc theo ID bình luận và ID bài đăng của toàn bộ tập C loại 962 câu khỏi train. Kiểm tra trùng hoặc gần trùng nội dung với C và kiểm tra trùng chính xác trong train không loại thêm câu nào. Tập train cuối có 688 POS, 1.312 NEG và 1.005 NEU.

Tập C ban đầu có 149 câu mang ba nhãn cảm xúc. Khi đối chiếu với 425 mẫu từng dùng để train checkpoint V1, quy tắc loại giao theo ID, bài đăng và nội dung trùng hoặc gần trùng loại tổng cộng 80 câu. Tập chấm chung còn **69 câu** gồm 12 POS, 39 NEG và 18 NEU. Tập T nằm ngoài phép thử.

### Cấu hình

- Bốn baseline của repo được fit lại trên 3.005 câu sau tiền xử lý tối thiểu. Hai mô hình BoW dùng unigram. LinearSVC dùng TF-IDF từ unigram–bigram hoặc TF-IDF ký tự `char_wb` 3–5.
- Hai BERT tiếp tục fine-tune từ checkpoint đã học 425 nhãn người V1. Mỗi mô hình cập nhật hai lớp encoder cuối và đầu phân loại trong một epoch. Seed là 20261123, batch size 16, độ dài tối đa 64 token, AdamW với learning rate 2e-5 và weight decay 0,01. PhoBERT tách từ bằng PyVi. ViSoBERT dùng văn bản tiền xử lý tối thiểu.
- Macro-F1 là chỉ số chính, tính trung bình F1 của POS, NEG và NEU với trọng số bằng nhau. Accuracy và F1 từng lớp được tính trên cùng 69 câu.

### Kết quả trên tập C

| Mô hình | Macro-F1 | Accuracy | F1 POS | F1 NEG | F1 NEU |
|---|---:|---:|---:|---:|---:|
| **PhoBERT** | **0,736** | **78,3%** | 0,632 | 0,846 | **0,732** |
| ViSoBERT | 0,706 | 76,8% | **0,636** | **0,857** | 0,625 |
| TF-IDF từ + LinearSVC | 0,652 | 71,0% | 0,500 | 0,790 | 0,667 |
| BoW + MultinomialNB | 0,644 | 72,5% | 0,571 | 0,828 | 0,533 |
| TF-IDF ký tự + LinearSVC | 0,632 | 66,7% | 0,519 | 0,730 | 0,649 |
| BoW + ComplementNB | 0,581 | 66,7% | 0,480 | 0,795 | 0,467 |

PhoBERT và ViSoBERT hơn baseline mạnh nhất lần lượt **0,084** và **0,054 macro-F1**. PhoBERT hơn ViSoBERT **0,030 macro-F1**, chủ yếu nhờ NEU (**0,732** so với **0,625**). ViSoBERT nhỉnh hơn ở POS và NEG. Về accuracy, PhoBERT dự đoán đúng 54/69 câu và ViSoBERT đúng 53/69 câu.

### Phạm vi kết luận

Kết quả so sánh các mô hình sau khi dùng cùng đợt nhãn V2. Hai BERT đã có lợi thế khởi tạo từ checkpoint học nhãn người V1. Phép thử chưa đo các checkpoint đó trên chính 69 câu này trước khi fine-tune, nên chưa định lượng được riêng phần cải thiện nhờ nhãn đồng thuận V2. Tập chấm có 69 câu, trong đó chỉ có 12 POS, và mỗi BERT chạy một seed. Thứ hạng vì vậy mang tính sơ bộ. Báo cáo mốc chunk 01–20 dùng tập chấm và cách chạy khác, nên không dùng chênh lệch giữa hai bảng để ước lượng hiệu quả của việc thêm chunk 21–50.

### Tệp thực nghiệm

Bảng điểm sáu mô hình (`comparison.csv`) và danh sách train, tập chấm, cấu hình (`split.local.json`) được lưu cục bộ trong `outputs/annotation_v2_consensus_bert_smoke_01/`.

[Báo cáo gán nhãn V2 đến chunk 20](BAO_CAO_GAN_NHAN_V2.md)
