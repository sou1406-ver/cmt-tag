# Báo cáo thử nghiệm PhoBERT, ViSoBERT và baseline trên nhãn đồng thuận V2

Ngày chạy 23/11/2026

PhoBERT đạt macro-F1 **0,736** trên 69 câu có nhãn người của tập C, cao hơn ViSoBERT (**0,706**) và baseline tốt nhất TF-IDF từ + LinearSVC (**0,652**). Sáu mô hình dùng cùng 3.005 câu train từ các chunk 01–50 và cùng tập chấm. Đây là phép thử một lượt với checkpoint BERT V1 có sẵn.

## Dữ liệu

Phép thử dùng ba nhãn cảm xúc POS, NEG và NEU. Một câu vào tập ứng viên khi ba model đồng thuận ở lượt 1 hoặc lượt 2. Ở lượt 2, hai model cùng một nhãn cảm xúc và model còn lại trả `REVIEW` cũng được tính là đồng thuận theo quy tắc đã chọn. Các câu còn thiếu phiếu, đồng thuận ở `REVIEW` hoặc `EXCLUDE`, hay còn khác nhãn ngoài quy tắc này không vào tập train. Với các câu có nhãn cảm xúc đồng thuận từ lượt 1, phép thử dùng nhãn của lượt đó.

| Nguồn nhãn | Ứng viên | Sau lọc train |
|---|---:|---:|
| Lượt 1, đồng thuận 3/3 | 3.749 | 2.841 |
| Lượt 2, đồng thuận 3/3 | 153 | 117 |
| Lượt 2, hai phiếu giống nhau và một `REVIEW` | 65 | 47 |
| **Tổng** | **3.967** | **3.005** |

Lọc theo ID bình luận và ID bài đăng của toàn bộ tập C loại 962 câu khỏi train. Kiểm tra trùng hoặc gần trùng nội dung với C và kiểm tra trùng chính xác trong train không loại thêm câu nào. Tập train cuối có 688 POS, 1.312 NEG và 1.005 NEU.

Tập C ban đầu có 149 câu mang ba nhãn cảm xúc. Khi đối chiếu với 425 mẫu từng dùng để train checkpoint V1, quy tắc loại giao theo ID, bài đăng và nội dung trùng hoặc gần trùng loại tổng cộng 80 câu. Tập chấm chung còn **69 câu** gồm 12 POS, 39 NEG và 18 NEU. Tập T nằm ngoài phép thử.

## Cấu hình

- Bốn baseline của repo được fit lại trên 3.005 câu sau tiền xử lý tối thiểu. Hai mô hình BoW dùng unigram. LinearSVC dùng TF-IDF từ unigram–bigram hoặc TF-IDF ký tự `char_wb` 3–5.
- Hai BERT tiếp tục fine-tune từ checkpoint đã học 425 nhãn người V1. Mỗi mô hình cập nhật hai lớp encoder cuối và đầu phân loại trong một epoch. Seed là 20261123, batch size 16, độ dài tối đa 64 token, AdamW với learning rate 2e-5 và weight decay 0,01. PhoBERT tách từ bằng PyVi. ViSoBERT dùng văn bản tiền xử lý tối thiểu.
- Macro-F1 là chỉ số chính, tính trung bình F1 của POS, NEG và NEU với trọng số bằng nhau. Accuracy và F1 từng lớp được tính trên cùng 69 câu.

## Kết quả trên tập C

| Mô hình | Macro-F1 | Accuracy | F1 POS | F1 NEG | F1 NEU |
|---|---:|---:|---:|---:|---:|
| **PhoBERT** | **0,736** | **78,3%** | 0,632 | 0,846 | **0,732** |
| ViSoBERT | 0,706 | 76,8% | **0,636** | **0,857** | 0,625 |
| TF-IDF từ + LinearSVC | 0,652 | 71,0% | 0,500 | 0,790 | 0,667 |
| BoW + MultinomialNB | 0,644 | 72,5% | 0,571 | 0,828 | 0,533 |
| TF-IDF ký tự + LinearSVC | 0,632 | 66,7% | 0,519 | 0,730 | 0,649 |
| BoW + ComplementNB | 0,581 | 66,7% | 0,480 | 0,795 | 0,467 |

PhoBERT và ViSoBERT hơn baseline mạnh nhất lần lượt **0,084** và **0,054 macro-F1**. PhoBERT hơn ViSoBERT **0,030 macro-F1**, chủ yếu nhờ NEU (**0,732** so với **0,625**). ViSoBERT nhỉnh hơn ở POS và NEG. Về accuracy, PhoBERT dự đoán đúng 54/69 câu và ViSoBERT đúng 53/69 câu.

## Phạm vi kết luận

Kết quả so sánh các mô hình sau khi dùng cùng đợt nhãn V2. Hai BERT đã có lợi thế khởi tạo từ checkpoint học nhãn người V1. Phép thử chưa đo các checkpoint đó trên chính 69 câu này trước khi fine-tune, nên chưa định lượng được riêng phần cải thiện nhờ nhãn đồng thuận V2. Tập chấm có 69 câu, trong đó chỉ có 12 POS, và mỗi BERT chạy một seed. Thứ hạng vì vậy mang tính sơ bộ. Báo cáo mốc chunk 01–20 dùng tập chấm và cách chạy khác, nên không dùng chênh lệch giữa hai bảng để ước lượng hiệu quả của việc thêm chunk 21–50.

## Tệp thực nghiệm

Bảng điểm sáu mô hình (`comparison.csv`) và danh sách train, tập chấm, cấu hình (`split.local.json`) được lưu cục bộ trong `outputs/annotation_v2_consensus_bert_smoke_01/`.

[Báo cáo gán nhãn V2 đến chunk 20](BAO_CAO_GAN_NHAN_V2.md)
