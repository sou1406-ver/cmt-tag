# Thử nghiệm V2 trên 424 câu test bổ sung

**Ngày 25/11/2026.** ViSoBERT đạt macro-F1 **0,7086**, cao hơn **0,0447** so với PhoBERT và **0,0803** so với baseline tốt nhất, TF-IDF từ + LinearSVC.

Lượt này là thử nghiệm trên phần bổ sung, một seed. Tập chính T2 được trình bày trong [báo cáo bài tập lớn](../BAO_CAO_BTL.md).

## Dữ liệu và cấu hình

Từ 450 quyết định gán nhãn người, giữ 424 câu để chấm, gồm 119 POS, 145 NEG và 160 NEU. Có 22 REVIEW và 4 EXCLUDE nằm ngoài ba lớp. Các câu đến từ 24 bài về 17 phim. Hai bình luận bắt đầu bằng `=` đã được khôi phục từ CSV crawl sau lỗi Excel diễn giải văn bản thành công thức, rồi được người gán chốt lại. Người gán cũng xác nhận `PNEG` là `NEG`.

Cả sáu mô hình dùng seed `20261123` và cùng 3.777 dòng train mốc 01–50, gồm 919 POS, 1.569 NEG và 1.289 NEU. Đối chiếu 450 câu bổ sung với snapshot train đã đóng băng theo ID, bài viết, văn bản chuẩn hóa và văn bản gần trùng. Loại một dòng train trùng văn bản chuẩn hóa. Giữ quy tắc chọn nhãn V2 của lần chạy trước. C và T gốc không được chấm trong lượt này.

PhoBERT và ViSoBERT khởi tạo từ checkpoint gốc đã ghim revision. PhoBERT dùng PyVi. Cả hai full fine-tune 4 epoch, learning rate `2e-5`, batch 16, tối đa 128 token, warmup 10%, weight decay `0,01` và trọng số lớp `N / (3 × n_lớp)`. Tập bổ sung chỉ dùng sau epoch cuối. Modal L4 chưa cấp container nên lượt chờ đã dừng. Hai lượt chạy hoàn tất trên NVIDIA A10G.

## Kết quả

| Mô hình | Macro-F1 | Accuracy | F1 POS | F1 NEG | F1 NEU |
|---|---:|---:|---:|---:|---:|
| ViSoBERT | **0,7086** | **0,7052** | **0,7411** | **0,6916** | **0,6931** |
| PhoBERT | 0,6639 | 0,6627 | 0,6923 | 0,6552 | 0,6443 |
| TF-IDF từ + LinearSVC | 0,6283 | 0,6274 | 0,6582 | 0,6422 | 0,5845 |
| BoW + ComplementNB | 0,6102 | 0,6156 | 0,6522 | 0,6625 | 0,5159 |
| BoW + MultinomialNB | 0,6019 | 0,6061 | 0,6307 | 0,6439 | 0,5312 |
| TF-IDF ký tự + LinearSVC | 0,5949 | 0,5943 | 0,6025 | 0,5916 | 0,5906 |

Kết quả dùng một seed và một lượt gán nhãn người. Tập bổ sung được lấy mẫu từ các bình luận crawler đọc được theo thứ tự Phù hợp nhất trên Facebook.

## Tái lập

- SHA-256 của manifest đã đóng băng trước khi chạy là `237bd95fce6711454aa726ac8d2cb4e7a8c38014b21fd46a469f2ea8d05e3c4b`.
- Manifest, dự đoán từng ID và bảng kết quả ở `outputs/test_extra_label_20261125/evaluation/`.
- Chi phí Modal ghi nhận cho app A10 là **0,04406030 USD trước credit**. App đã dừng sau khi trả kết quả.
