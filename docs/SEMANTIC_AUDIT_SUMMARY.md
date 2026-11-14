# Kiểm tra sơ bộ dữ liệu Facebook V2

Ngày: 15/11/2026. Repo: `sou1406-ver/cmt-tag` (người dùng thông báo đã chuyển public).

## Mục tiêu và dữ liệu

Bài toán V2 hiện là phân loại **cảm xúc chung của bình luận**, không chỉ sentiment hướng vào phim. Đợt này chỉ audit phụ trợ xem comment có liên quan đến phim và có đọc hiểu độc lập được không; chưa gán sentiment, chưa train hoặc đánh giá mô hình.

Run mới có 2.521 bình luận từ 28 bài, 22 phim, 3 nguồn. Làm sạch kỹ thuật cho kết quả 2.384 KEEP, 25 REVIEW, 112 EXCLUDE. KEEP chỉ có nghĩa còn văn bản sử dụng được, không khẳng định liên quan phim hoặc đủ ngữ cảnh để gán sentiment.

Từ KEEP chọn 300 câu: 240 ngẫu nhiên phân tầng theo bài × comment/reply và 60 câu có chủ đích để kiểm tra trường hợp khó. Seed 20261114. Một người đã gán 107 câu, còn 193 câu chưa gán.

## Kết quả đã quan sát

| Nhóm đã gán | RELEVANT | IRRELEVANT | UNCERTAIN | Tổng |
|---|---:|---:|---:|---:|
| Ngẫu nhiên | 61 (68,5%) | 11 (12,4%) | 17 (19,1%) | 89 |
| Có chủ đích, trường hợp khó | 7 | 4 | 7 | 18 |
| Tổng | 68 | 15 | 24 | 107 |

Đây là số đếm và tỷ lệ trong **phần đã gán**, không phải ước lượng tỷ lệ sạch của toàn bộ dữ liệu. Chưa hoàn thành mẫu ngẫu nhiên; không tính CI hoặc gộp nhóm khó để suy rộng.

Có 23/107 câu được người gán đánh dấu cần ngữ cảnh. Trong 24 UNCERTAIN, 22 câu có needs_context=YES, 2 câu có NO; giữ nguyên các quyết định này, chưa tự sửa. Ví dụ minh họa do người dùng nêu: “em cũng thấy thế” — đọc riêng không biết đang đồng tình với điều gì, có liên quan phim hay không; cũng chưa đủ căn cứ suy sentiment.

Workbook không kèm nội dung comment cha hoặc bài viết. Trong toàn bộ KEEP, 306/1.235 reply có parent không nằm trong export. Con số này mô tả thiếu ngữ cảnh tiềm năng, không đồng nghĩa tất cả 306 câu đều không dùng được.

## Giới hạn và tình trạng lưu nhãn

- Cả 300 ID và text_clean vẫn khớp mẫu gốc; checksum file nguồn không đổi.
- 39 quyết định IRRELEVANT/UNCERTAIN chưa ghi lý do. Người dùng xác nhận khó giải thích ngoài việc không hiểu khi thiếu ngữ cảnh. Không tự bịa lý do; UNCERTAIN + YES được hiểu là cần ngữ cảnh, không tự áp dụng cho các trường hợp khác.
- Tab Đối chiếu có 2 ô text_raw lệch một khoảng trắng so với CSV gốc. Raw nguồn không đổi. Import chính thức hiện vẫn bị chặn bởi kiểm tra toàn vẹn và yêu cầu lý do; số liệu trên được đọc để kiểm tra sơ bộ, chưa phải import thành công.
- Relevance không phải sentiment. IRRELEVANT với phim chưa tự động bị loại khỏi bài toán cảm xúc chung; UNCERTAIN cũng không tự chuyển thành NEU hay EXCLUDE.

## Quyết định và bước tiếp theo

Dừng audit relevance ở 107 câu theo trao đổi với người dùng; giữ 193 câu còn lại chưa gán. Chưa có bằng chứng rằng bắt buộc hoàn thành 300 câu mới tiếp tục được, nhưng phần hiện có cũng chưa đủ để kết luận toàn bộ dataset đã sạch.

Ưu tiên làm rõ quy tắc gán sentiment cho câu thiếu ngữ cảnh. Nếu cung cấp comment cha khi gán, phải quy định nhất quán dữ liệu mà mô hình sẽ nhận lúc suy luận; ngữ cảnh hỗ trợ người gán không được ngầm coi là đầu vào sẵn có của mô hình. Câu không đủ căn cứ thì giữ REVIEW theo guideline được chốt, không ép thành NEU.

Không thay raw, nhãn người, canonical hoặc Gold Test; không crawl thêm, train hay gọi API trong bước tổng hợp này. Chưa có kết quả sentiment V2 từ audit này.

**Đề nghị GPT review:** Với mục tiêu cảm xúc chung, có nên dừng audit relevance và chuyển sang chuẩn bị gán sentiment? Cần quy tắc tối thiểu nào cho reply thiếu ngữ cảnh, để không đánh đồng “ngoài lề phim” với “không có sentiment” và không tạo lệch giữa dữ liệu gán nhãn với đầu vào mô hình?
