# Phân loại cảm xúc bình luận tiếng Việt về phim

**Bài tập lớn Xử lý dữ liệu văn bản · cmt-tag**

**Cập nhật 25/11/2026.** Bộ nhãn T2 đã được đóng băng cho bản hiện tại. Hàng chờ còn 1.731 câu và lượt thực nghiệm chính đang đợi nhãn hoàn tất.

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

Trong 652 quyết định có 32 REVIEW và 7 EXCLUDE. Manifest lưu nguồn từng câu và SHA-256 của bản đang dùng. 1.731 câu chờ gán thuộc các bài đã có trong test, được giữ để bổ sung test sau khi người dùng duyệt. Train loại các mẫu cùng bài, trùng ID, trùng nội dung hoặc gần trùng với T2 trước khi đóng băng.

Phần bổ sung 424 câu đã được dùng trong một lượt thử nghiệm. Báo cáo cuối cần trình bày riêng T gốc, phần bổ sung và tổng hợp T2 để người đọc biết phần nào đã có điểm sơ bộ.

## 4. Thiết kế thực nghiệm chính

| Hạng mục | Cấu hình |
| --- | --- |
| Baseline | BoW + MultinomialNB, BoW + ComplementNB, TF-IDF từ + LinearSVC, TF-IDF ký tự + LinearSVC |
| Transformer | PhoBERT `vinai/phobert-base` và ViSoBERT `uitnlp/visobert`, ghim revision. PhoBERT tách từ bằng PyVi. |
| Khởi tạo | Hai BERT tải trọng số pretrained gốc và khởi tạo đầu phân loại mới cho mỗi seed. |
| Fine-tune | 4 epoch, learning rate `2e-5`, batch 16, tối đa 128 token, warmup 10%, weight decay `0,01`, trọng số lớp theo tần suất train. Dùng mô hình sau epoch cuối. |
| Lặp và báo điểm | Seed `20261123`, `20261124`, `20261125`. Báo macro-F1, accuracy và F1 từng lớp theo seed, kèm mean ± std. Các mô hình dùng cùng tập train và cùng tập chấm. |
| Tái lập | Lưu SHA-256 của snapshot và revision model, manifest, dự đoán theo ID, thời gian chạy và chi phí Modal. |

**Kết quả chính trên T2 đang chờ lượt chạy cuối.** Những phép thử trước dùng snapshot và tập chấm riêng.

## 5. Các thử nghiệm trước

- Trên C và E+C, đã thử learning curve theo số chunk và cross-validation theo bài để so sánh các mô hình. [Báo cáo thực nghiệm C và E+C](annotation/BAO_CAO_THUC_NGHIEM_V2_C_3_SEED.md)
- Trên 424 câu bổ sung với một seed, macro-F1 của ViSoBERT, PhoBERT và baseline TF-IDF từ lần lượt là **0,7086**, **0,6639** và **0,6283**. [Chi tiết lượt thử nghiệm](annotation/BAO_CAO_TEST_BO_SUNG_V2.md)
