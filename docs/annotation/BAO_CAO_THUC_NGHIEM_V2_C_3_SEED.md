# Thực nghiệm V2 trên tập C cố định với ba seed

Ngày chạy 24/11/2026

**ViSoBERT đạt macro-F1 trung bình 0,7914**, tiếp theo là PhoBERT 0,7790 và TF-IDF từ + LinearSVC 0,6558 ở mốc chunk 50. Hai BERT và baseline mốc 50 dùng cùng 3.778 mẫu train và cùng 149 câu C có nhãn người. Sáu lượt BERT chạy trên Modal L4 và 36 lượt baseline chạy cục bộ. Tập T nằm ngoài thực nghiệm.

## Kiểm tra nhãn đa số trên 159 câu C

Đối chiếu nhãn GPT, Claude và Gemini ở lượt 1 với nhãn người theo `comment_id`. Có 149 câu cả ba AI trùng, 9 câu đúng hai AI trùng và 1 câu cả ba khác. Trong nhóm đúng hai AI trùng, phiếu đa số khớp nhãn người ở **5/9 câu (55,6%)** và sai ở 4 câu. Phép tính dùng khớp nhãn chính xác trên POS, NEG, NEU, REVIEW và EXCLUDE. Kết quả là thống kê hiệu chuẩn trên nhóm nhỏ. Quy tắc lựa chọn nhãn được giữ nguyên.

## Thiết kế và dữ liệu

Giữ riêng toàn bộ 159 câu C khi lọc train. Tập tính điểm gồm đủ 149 câu C có nhãn cảm xúc, với 23 POS, 80 NEG và 46 NEU. Pool train theo từng mốc gồm E, U đã chốt và nhãn mở rộng từ chunk 01 đến mốc tương ứng. Với dữ liệu mở rộng, dùng nhãn cảm xúc nếu lượt 1 đồng thuận 3/3. Các câu khác nhãn ở lượt 1 vào train khi lượt 2 đồng thuận 3/3 hoặc có hai phiếu cùng một nhãn cảm xúc và một phiếu REVIEW.

Đã lọc theo ID, bài đăng, nội dung trùng và gần trùng với toàn bộ C. Kiểm tra gần trùng dùng Jaccard trigram token từ 0,90 với văn bản chuẩn hóa dài ít nhất 40 ký tự. Ở mốc 50, bộ lọc loại 997 mẫu do giao ID hoặc bài, gồm toàn bộ 35 mẫu E có nhãn cảm xúc. Không có mẫu bị loại thêm bởi kiểm tra nội dung. Mỗi model và seed dùng cùng tập chấm. Các mốc train lồng nhau và số liệu dưới đây là sau lọc.

| Mốc | U | Mở rộng | Tổng train | POS | NEG | NEU |
|---|---:|---:|---:|---:|---:|---:|
| 01–20 | 773 | 1.239 | 2.012 | 522 | 781 | 709 |
| 01–35 | 773 | 2.120 | 2.893 | 714 | 1.162 | 1.017 |
| 01–50 | 773 | 3.005 | 3.778 | 919 | 1.569 | 1.290 |

## Cấu hình

Dùng ba seed `20261123`, `20261124` và `20261125`. Cả hai BERT cập nhật toàn bộ tham số trong 4 epoch, batch 16, tối đa 128 token, AdamW với learning rate `2e-5` và weight decay 0,01. Lịch learning rate warmup tuyến tính 95/948 bước rồi giảm tuyến tính. Cross-entropy đặt trọng số lớp bằng `N / (3 × n_lớp)`. C chỉ được chấm sau epoch cuối để báo kết quả.

| Mô hình | Checkpoint gốc | Revision | Tiền xử lý |
|---|---|---|---|
| PhoBERT | `vinai/phobert-base` | `01daacda68afe13d83023d16ec647239e344a1e6` | Tối thiểu, tách từ PyVi |
| ViSoBERT | `uitnlp/visobert` | `196a62afad9cbe4f52a54aabad828b13f0eec59a` | Tối thiểu |

Bốn baseline giữ cấu hình và tiền xử lý của repo giữa các mốc. Baseline mốc 50 và cả hai BERT dùng đúng cùng danh sách ID train. Token train, token C và nhãn train được gửi tới Modal để chạy GPU. Nhãn người của C và ID gốc được giữ cục bộ, nơi tính điểm từ dự đoán trả về.

## Điểm BERT trên 149 câu C

Giá trị tổng hợp là trung bình ± độ lệch chuẩn mẫu qua 3 seed. Các chỉ số trong bảng dùng thang 0–1.

| Mô hình | Macro-F1 | Accuracy | F1 POS | F1 NEG | F1 NEU |
|---|---:|---:|---:|---:|---:|
| ViSoBERT | **0,7914 ± 0,0163** | **0,8166 ± 0,0169** | 0,7251 ± 0,0166 | **0,8638 ± 0,0166** | **0,7854 ± 0,0177** |
| PhoBERT | 0,7790 ± 0,0135 | 0,7875 ± 0,0103 | **0,7925 ± 0,0374** | 0,8273 ± 0,0042 | 0,7172 ± 0,0310 |

| Mô hình | Seed | Macro-F1 | Accuracy | F1 POS | F1 NEG | F1 NEU |
|---|---:|---:|---:|---:|---:|---:|
| PhoBERT | 20261123 | 0,7638 | 0,7785 | 0,7600 | 0,8280 | 0,7033 |
| PhoBERT | 20261124 | 0,7839 | 0,7852 | 0,8333 | 0,8228 | 0,6957 |
| PhoBERT | 20261125 | 0,7894 | 0,7987 | 0,7843 | 0,8312 | 0,7527 |
| ViSoBERT | 20261123 | 0,8060 | 0,8322 | 0,7347 | 0,8790 | 0,8043 |
| ViSoBERT | 20261124 | 0,7738 | 0,7987 | 0,7059 | 0,8462 | 0,7692 |
| ViSoBERT | 20261125 | 0,7945 | 0,8188 | 0,7347 | 0,8662 | 0,7826 |

## Learning curve của baseline

Ba seed cho cùng điểm ở mỗi cấu hình trên split cố định, nên mọi độ lệch chuẩn ở bảng này bằng 0.

| Mốc | Mô hình | Macro-F1 | Accuracy | F1 POS | F1 NEG | F1 NEU |
|---|---|---:|---:|---:|---:|---:|
| 20 | TF-IDF từ + LinearSVC | 0,6720 | 0,7047 | 0,5769 | 0,7561 | 0,6829 |
| 20 | TF-IDF ký tự + LinearSVC | 0,6278 | 0,6644 | 0,4906 | 0,7190 | 0,6739 |
| 20 | BoW + MultinomialNB | 0,5727 | 0,6376 | 0,5106 | 0,7416 | 0,4658 |
| 20 | BoW + ComplementNB | 0,5459 | 0,6040 | 0,4898 | 0,7176 | 0,4304 |
| 35 | TF-IDF từ + LinearSVC | **0,6729** | 0,6980 | 0,5882 | 0,7317 | 0,6988 |
| 35 | TF-IDF ký tự + LinearSVC | 0,6510 | 0,6913 | 0,4906 | 0,7451 | 0,7174 |
| 35 | BoW + MultinomialNB | 0,5875 | 0,6510 | 0,5455 | 0,7514 | 0,4658 |
| 35 | BoW + ComplementNB | 0,5828 | 0,6510 | 0,5417 | 0,7684 | 0,4384 |
| 50 | TF-IDF từ + LinearSVC | 0,6558 | 0,6846 | 0,5490 | 0,7195 | 0,6988 |
| 50 | TF-IDF ký tự + LinearSVC | 0,5888 | 0,6309 | 0,4151 | 0,6846 | 0,6667 |
| 50 | BoW + MultinomialNB | 0,5982 | 0,6577 | 0,5532 | 0,7614 | 0,4800 |
| 50 | BoW + ComplementNB | 0,5579 | 0,6174 | 0,5200 | 0,7326 | 0,4211 |

## Diễn giải

Ở mốc 50, ViSoBERT và PhoBERT hơn baseline mạnh nhất lần lượt 0,1356 và 0,1232 macro-F1. ViSoBERT dẫn về macro-F1, F1 NEG và F1 NEU, còn PhoBERT dẫn về F1 POS. ViSoBERT có macro-F1 cao hơn ở hai trong ba seed. Chênh lệch trung bình 0,0124 giữa hai BERT chỉ mô tả kết quả trên tập C cố định. Độ lệch chuẩn qua seed phản ánh biến động lần chạy trên tập này.

Baseline TF-IDF từ đứng đầu ở cả ba mốc và đạt đỉnh ở mốc 35. Khi thêm dữ liệu đến mốc 50, macro-F1 của mô hình này giảm 0,0171, trong khi BoW + MultinomialNB tiếp tục tăng. Báo cáo sơ bộ trước dùng checkpoint V1 và 69 câu C, nên hai bảng có tập chấm và cách khởi tạo khác nhau. Xem [báo cáo tiến độ gán nhãn và thử nghiệm sơ bộ V2](BAO_CAO_THU_NGHIEM_MO_HINH_V2.md).

## Tệp thực nghiệm

SHA-256 manifest của snapshot trước khi train là `55591c36de6a74f17e023447b4e9981bf524fe1f74b596fa35864a389c55ec75`. Manifest, bảng tổng hợp, điểm từng seed và dự đoán theo ID được lưu cục bộ trong `outputs/annotation_v2_fixed_c_3seed_01/`. Đã đối chiếu đủ 149 ID C cho từng lượt và tính lại các chỉ số từ dự đoán lưu trên máy.
