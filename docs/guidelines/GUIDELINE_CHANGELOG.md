# Lịch sử guideline gán nhãn

Bản đang dùng: `docs/guidelines/SENTIMENT_GUIDELINE.md`. Mỗi lượt gán ghi SHA256 của file tại thời điểm giao trong manifest; nhãn thuộc về đúng SHA đó.

| Ngày | Mốc | Thay đổi | Lượt gán dùng |
|---|---|---|---|
| 10–14/11/2026 | V2.0, V2.1 | Cảm xúc hướng vào phim (V1 của dự án) | 425 nhãn người, Gold V1 |
| 15/11/2026 | V3.1 — PROPOSED | Chuyển sang cảm xúc chung, chỉ đọc `text_clean`; bản đề xuất do Codex soạn, chưa được duyệt | Pilot 200: manifest pin PROPOSED `f079ce7b…`, nhưng bộ giao A/B kèm bản `2ba9f0…`; người dùng xác nhận người gán đọc bản kèm. Có lệch provenance; Kappa 5 quyết định 0,60, 3 nhãn 0,78 trên 158/200 câu |
| 15/11/2026 | V3.2 | Thu hẹp EXCLUDE; công kích người là NEG; tách tranh luận NEU/NEG; mỉa mai đọc nghĩa đen | Không có |
| 15/11/2026 | V3.3 | Mọi đối tượng đều tính; cảm xúc thuật lại hoặc giả định không tính; chốt tín hiệu mỉa mai và đánh giá nhẹ ("không tệ" là POS); lời lịch sự không tính; spam/quảng cáo EXCLUDE; bỏ ví dụ còn tranh cãi | đã prepare batch 1, không giao — thay bằng quy trình AI gán + người dùng duyệt |
| 15/11/2026 | Bản chính thức mới | Bỏ mục workbook/quy trình khỏi guideline; bỏ ví dụ “nổi da gà”; thêm quy tắc điểm số. SHA `2e4ba18c3c12c97b3bf4c33f39e11a87a684c71af1459e671860aec046d9568e` | Quy trình AI gán + người dùng duyệt; chưa thực hiện bước nào |

## Đối chiếu provenance ngày 15/11/2026

- Manifest pilot giữ nguyên `guideline_status=PROPOSAL_NOT_APPROVED`, `status=DRAFT_GUIDELINE_SOURCE_MISSING`, pin `history/SENTIMENT_GUIDELINE_V3_1_PROPOSED.md`, SHA `f079ce7b5ecedd6242d99808ee0b010b28ea6f8b8afc4ba01f7cf86552d08433`. Header workbook B ghi DRAFT và còn trỏ PROPOSED.
- Tuy nhiên, bộ giao A/B tại `bo_gui_gan_nhan/DOC_TRUOC_KHI_GAN.txt` yêu cầu đọc file kèm `SENTIMENT_GUIDELINE_V3_1.md`, SHA `2ba9f0ec3c755754181a194c3f7ef4bd9dde200d0f3726de7be7b20125583a81`, không dùng PROPOSED được nhắc trong Excel. File kèm đã kiểm đúng SHA đó. Người dùng xác nhận người gán đọc bản kèm. Đây là lệch giữa manifest/header và guideline thực được giao/đọc; không sửa manifest, không khẳng định Kappa kiểm chứng riêng một bản.
- `history/SENTIMENT_GUIDELINE_V3_1.md` là bản hợp nhất để rà soát `2ba9f0…`, khác bản người dùng nói có SHA bắt đầu `e3507aa3…` chưa có file gốc để đối chiếu. Bản `2ba9f0…` được giữ để truy xuất bộ đã giao A/B; không tự gán lại nguồn tác giả của file.
- V3.2 trong Git trước di chuyển có SHA `4cb3c49af3f342f186f0eefaf48bce1b87942cb66bcb3c8a991bd9bbace30602` (LF). Khi chuyển lịch sử đã giữ bản local CRLF, SHA `bc4fa55c8cadd052bd66b85243a50fc3a0649e8645fddfdcdb8c6f97c43e199a`: nội dung sau chuẩn hóa CRLF thành LF giống hệt. Đã phục hồi file lịch sử đúng byte Git cũ và SHA `4cb3c49a…`; không có manifest lượt gán nào được tìm thấy pin V3.2. `.gitattributes` giữ nguyên byte khi checkout về sau.
- Không sửa manifest, nhãn, kết quả Kappa hoặc phê duyệt ngược bất kỳ lượt cũ nào. Trạng thái prepare/giao được ghi riêng theo lượt thực tế, không suy chỉ từ tên mốc trong changelog.

## Kế hoạch A/B đã thay thế

- Batch 1 đã prepare theo snapshot SHA `b25482675c3a6387321f281579e318565999fd3a579e12dadc3897938bb39714`, **không giao**, không dùng để tiếp tục gán A/B. Kế hoạch năm batch và bước dự phòng bổ sung nguồn nhỏ đã thay bằng [quy trình AI gán + người dùng duyệt](../annotation/QUY_TRINH_GAN_NHAN.md).
- Selection 1.000 ID trong `annotation_round_01`, manifest và snapshot cũ giữ nguyên để quy trình mới dùng lại. Chưa tách E/C/T/U, chưa xuất chunk, chưa gọi AI hoặc train.
- Trước khi thay guideline, đã lưu nguyên byte bản cũ vào `history/SENTIMENT_GUIDELINE_b2548267.md`. File quy trình người dùng gửi còn ghi SHA b254 của bản cũ; chỉ metadata SHA trong mục cố định được cập nhật theo file mới, không đổi bước hay thứ tự.
