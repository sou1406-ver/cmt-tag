# Lịch sử guideline gán nhãn

Bản đang dùng: `docs/guidelines/SENTIMENT_GUIDELINE.md`. Mỗi lượt gán ghi SHA256 của file tại thời điểm giao trong manifest; nhãn thuộc về đúng SHA đó.

| Ngày | Mốc | Thay đổi | Lượt gán dùng |
|---|---|---|---|
| 10–14/11/2026 | V2.0, V2.1 | Cảm xúc hướng vào phim (V1 của dự án) | 425 nhãn người, Gold V1 |
| 15/11/2026 | V3.1 — PROPOSED | Chuyển sang cảm xúc chung, chỉ đọc `text_clean`; bản đề xuất do Codex soạn, chưa được duyệt | Pilot 200 câu dùng bản PROPOSED, SHA `f079ce7b5ecedd6242d99808ee0b010b28ea6f8b8afc4ba01f7cf86552d08433` (Kappa 5 quyết định 0,60; 3 nhãn 0,78 trên 158/200 câu) |
| 15/11/2026 | V3.2 | Thu hẹp EXCLUDE; công kích người là NEG; tách tranh luận NEU/NEG; mỉa mai đọc nghĩa đen | Không có |
| 15/11/2026 | V3.3 | Mọi đối tượng đều tính; cảm xúc thuật lại hoặc giả định không tính; chốt tín hiệu mỉa mai và đánh giá nhẹ ("không tệ" là POS); lời lịch sự không tính; spam/quảng cáo EXCLUDE; bỏ ví dụ còn tranh cãi | Batch 1 lượt chính thức |

## Đối chiếu provenance ngày 15/11/2026

- Manifest pilot ghi `guideline_status=PROPOSAL_NOT_APPROVED`, `status=DRAFT_GUIDELINE_SOURCE_MISSING` và pin bản `history/SENTIMENT_GUIDELINE_V3_1_PROPOSED.md` với SHA đầy đủ trong bảng. Workbook B cũng ghi DRAFT và trỏ bản PROPOSED. Kappa đo hai workbook của lượt này, không phải bằng chứng đã kiểm chứng bản V3.1 chính thức của người dùng.
- `history/SENTIMENT_GUIDELINE_V3_1.md`, SHA `2ba9f0ec3c755754181a194c3f7ef4bd9dde200d0f3726de7be7b20125583a81`, là bản hợp nhất để rà soát, không phải bản V3.1 người dùng xác nhận có SHA bắt đầu `e3507aa3…`. Chưa có file gốc để kiểm chứng SHA đầy đủ của bản đó. Không có lượt gán được xác minh dùng file `2ba9f0…`; giữ để tham chiếu, không coi là bản đã giao.
- V3.2 trong Git trước di chuyển có SHA `4cb3c49af3f342f186f0eefaf48bce1b87942cb66bcb3c8a991bd9bbace30602` (LF). Khi chuyển lịch sử đã giữ bản local CRLF, SHA `bc4fa55c8cadd052bd66b85243a50fc3a0649e8645fddfdcdb8c6f97c43e199a`: nội dung sau chuẩn hóa CRLF thành LF giống hệt. Đã phục hồi file lịch sử đúng byte Git cũ và SHA `4cb3c49a…`; không có manifest lượt gán nào được tìm thấy pin V3.2. `.gitattributes` giữ nguyên byte khi checkout về sau.
- Không sửa manifest, nhãn, kết quả Kappa hoặc phê duyệt ngược bất kỳ lượt cũ nào. Dòng “Batch 1 lượt chính thức” là mốc áp dụng theo changelog người dùng cung cấp, không tự xác nhận đã prepare/gán batch mới.
