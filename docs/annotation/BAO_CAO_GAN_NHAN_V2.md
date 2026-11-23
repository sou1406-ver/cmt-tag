# Tiến độ gán nhãn cảm xúc V2

**Cập nhật 23/11/2026.** V2 phân loại sắc thái chung do người viết thể hiện trong `text_clean`, bất kể đối tượng được nhắc tới. Ba lớp mô hình là POS, NEG và NEU. REVIEW và EXCLUDE được lưu để theo dõi quyết định gán nhãn.

## Phần đã hoàn thành

| Tập | Số câu | Vai trò |
| --- | ---: | --- |
| E | 41 | Ví dụ chọn từ pilot 200 câu đã gán độc lập A/B và đối soát. |
| C | 159 | Phần pilot còn lại dùng để hiệu chuẩn AI với nhãn người. E+C có 184 câu thuộc ba lớp sentiment. |
| T | 202 | Tập test đã khóa, lấy từ 12 bài. Trong 50 câu người dùng gán mù trước khi xem AI, 47 nhãn khớp quyết định cuối. Có 189 câu thuộc ba lớp sentiment. |
| U | 798 | Ba AI gán. Người dùng chốt 181 câu bất đồng và kiểm tra 62 câu đồng thuận, sửa 1 nhãn. Có 773 câu dùng được cho train, gồm 231 POS, 257 NEG và 285 NEU. |

47/50 (94%) là mức khớp giữa lần gán mù và nhãn chốt T. Trong mẫu audit U, 61/62 (98,4%) nhãn đồng thuận được giữ nguyên. Đây là kết quả trên hai mẫu đã kiểm tra.

## Hiệu chuẩn AI trên C

Đối chiếu cả 159 câu C với nhãn người. Kappa 5 tính trên POS, NEG, NEU, REVIEW và EXCLUDE. Kappa 3 chỉ tính trên những câu mà cả hai phía đều chọn POS, NEG hoặc NEU.

| Nguồn nhãn | Phủ trên C | Khớp nhãn người | Kappa 5 | Số cặp tính Kappa 3 | Kappa 3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| ChatGPT | 159/159 | 141/159 (88,7%) | 0,821 | 149 | 0,876 |
| Claude | 159/159 | 141/159 (88,7%) | 0,822 | 148 | 0,887 |
| Gemini | 159/159 | 140/159 (88,1%) | 0,809 | 148 | 0,874 |
| Đồng thuận 3/3 | 149/159 (93,7%) | 136/149 (91,3%) | 0,861 | 140 | 0,915 |

Lượt hiệu chuẩn C dùng guideline SHA `2e4ba18c…`. Lượt mở rộng ghim guideline SHA `e652aa2a…`, trong đó tán thưởng như “Chuẩn!” có thể là POS, còn câu có thêm nội dung được xét theo toàn câu. Rà nhanh các câu mở đầu bằng “chuẩn” thấy một câu hỗn hợp ở E có nhãn NEU trong prompt cũ và không thấy câu tương ứng ở C. Số liệu trên dùng các nhãn đã lưu của lượt cũ. T vẫn giữ bản đã khóa.

## Kết quả train thử

Hai cấu hình dùng cùng 5 fold chia theo bài viết trên 184 câu E+C có nhãn người từ 28 bài. U chỉ thêm vào train của mỗi fold sau khi kiểm tra trùng bài và nội dung với validation. Bảng dùng macro-F1 gộp các dự đoán ngoài fold. T vẫn dành cho lần chấm cuối.

| Mô hình | E+C, chấm E+C | E+C+U, chấm E+C | E+C, chấm C | E+C+U, chấm C |
| --- | ---: | ---: | ---: | ---: |
| BoW + ComplementNB | 0,380 | 0,476 | 0,394 | 0,482 |
| BoW + MultinomialNB | 0,334 | 0,521 | 0,356 | 0,536 |
| TF-IDF từ + LinearSVC | 0,345 | 0,592 | 0,360 | 0,596 |
| TF-IDF ký tự 3–5 + LinearSVC | 0,481 | 0,603 | 0,530 | 0,625 |

Hai cột chấm C lấy 149 câu POS/NEG/NEU của C trong cùng các dự đoán ngoài fold. Các fold và điểm E+C đã được tái lập. Ở mô hình ký tự, thêm U tăng macro-F1 trên C khoảng 0,095. Trên toàn E+C, F1 của POS tăng từ 0,314 lên 0,529 và vẫn thấp hơn NEG và NEU.

## Lượt gán mở rộng

Từ bốn export Facebook V2 có **12.795 bình luận**, giữ **8.965 câu** từ **74 bài, 55 phim và 4 nguồn**. Đã xuất **90 CSV local**, mỗi file tối đa 100 câu và chỉ có `comment_id`, `text_clean`. Manifest lưu seed `20261123`, SHA-256 của prompt và guideline snapshot, cùng checksum từng file.

| Lý do loại khỏi lượt mở rộng | Số câu |
| --- | ---: |
| Thuộc một trong 12 bài của T | 2.109 |
| ID đã có trong pilot hoặc U, sau khi chặn T | 998 |
| Trạng thái làm sạch kỹ thuật khác KEEP | 611 |
| Trùng nội dung với bình luận thuộc bài của T | 30 |
| Trùng đúng nội dung thuộc reservation cũ | 5 |
| Trùng nội dung đã gán | 10 |
| Trùng đúng nội dung trong pool mới | 61 |
| Gần trùng nội dung trong pool mới | 6 |
| **Tổng loại** | **3.830** |

Phân bố pool mới gồm 6.322 câu từ Maybe You Never Watched This Movie, 2.449 từ Chê Phim Review, 178 từ XEM PHIM & BÌNH PHIM và 16 từ Cuồng Phim. Số lượng phản ánh pool sau lọc và tập trung vào hai nguồn lớn.

Người dùng gán trên web với ChatGPT, Claude và Gemini. Các câu bất đồng được gán lại một lần trong chat mới với cùng prompt và guideline. Người dùng chốt các câu vẫn bất đồng và kiểm tra ngẫu nhiên 10% trong từng nhóm đồng thuận. Nguồn nhãn được lưu theo lượt, câu chưa chốt ở PENDING. CSV, prompt chứa ví dụ thật và kết quả theo từng ID lưu local tại `outputs/annotation_expansion_round_01/`.

## Kết quả sơ bộ chunk 01–20

Lượt 1 đã nhận đủ 60 file, tương ứng 20 chunk cho mỗi AI. Ba AI đồng thuận trên **1.545/2.000 câu (77,25%)**. Còn **455 câu (22,75%)** cần gán lại. Bảng tính lũy kế đến từng mốc.

| Chunk | Tổng câu | Đồng thuận 3/3 | Bất đồng | POS | NEG | NEU | REVIEW | EXCLUDE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01–10 | 1.000 | 804 | 196 | 152 | 379 | 259 | 6 | 8 |
| 01–20 | 2.000 | 1.545 | 455 | 336 | 683 | 505 | 10 | 11 |

### Baseline chấm trên nhãn người C

Giữ nguyên 5 fold chia theo bài và chấm trên cùng 149 câu POS/NEG/NEU có nhãn người của C. Tập train gốc là E+C+U trong từng fold. Hai mốc mở rộng có 790 và 1.524 nhãn POS/NEG/NEU đồng thuận 3/3 ở lượt 1. Sau khi chặn cùng bài và kiểm tra trùng nội dung với validation, số mẫu thêm thực tế là 746–760 và 1.436–1.468 mỗi fold. Bảng dùng macro-F1 gộp các dự đoán ngoài fold.

| Mô hình | Gốc E+C+U | Thêm chunk 01–10 | Thêm chunk 01–20 | Thay đổi 01–20 so với gốc |
| --- | ---: | ---: | ---: | ---: |
| BoW + ComplementNB | 0,482 | 0,489 | 0,563 | +0,081 |
| BoW + MultinomialNB | 0,536 | 0,500 | 0,563 | +0,028 |
| **TF-IDF từ + LinearSVC** | **0,596** | **0,635** | **0,657** | **+0,062** |
| TF-IDF ký tự 3–5 + LinearSVC | 0,625 | 0,608 | 0,620 | −0,004 |

TF-IDF từ + LinearSVC đạt điểm cao nhất ở mốc 20 chunk và cải thiện ở 4/5 fold so với cấu hình gốc của chính nó. Điểm tốt nhất tăng khoảng 0,033 so với mô hình tốt nhất ở mốc gốc. F1 lớp POS của mô hình từ đạt 0,489 ở mốc 20 chunk, thấp hơn 0,533 ở mốc 10 chunk. Lượt chạy sơ bộ dùng đồng thuận lượt 1. Kết quả gán lại và duyệt tay sẽ được tính trong lần chạy sau.

### Checkpoint BERT V1 đối chiếu nhãn AI V2

PhoBERT và ViSoBERT là hai checkpoint cũ đã học từ 425 nhãn người V1 về thái độ với phim. Hai mô hình được chấm trên cùng 1.310 câu của chunk 01–20 có nhãn POS/NEG/NEU đồng thuận 3/3, sau khi loại 214 câu cùng bài với dữ liệu huấn luyện cũ. Điểm dưới đây đo mức khớp với nhãn AI V2. Bảng baseline phía trên đo trên nhãn người C.

| Checkpoint | Accuracy | Macro-F1 | F1 POS | F1 NEG | F1 NEU |
| --- | ---: | ---: | ---: | ---: | ---: |
| PhoBERT | 61,5% | 0,568 | 0,592 | 0,702 | 0,411 |
| ViSoBERT | 65,0% | 0,636 | 0,604 | 0,699 | 0,606 |

ViSoBERT đạt macro-F1 cao hơn 0,068 trên phép thử này, với chênh lệch lớn nhất ở NEU. Sau khi chốt nhãn 20 chunk, chạy lại baseline và so ViSoBERT fine-tune trên V2 với TF-IDF từ + LinearSVC bằng cùng dữ liệu train, fold và 149 câu C. Tập T chưa dùng để chấm ở cả hai phép thử. Kết quả chi tiết lưu local trong `outputs/annotation_v2_expansion_preliminary_cv_01/` và `outputs/annotation_v2_expansion_bert_probe_01/`.
