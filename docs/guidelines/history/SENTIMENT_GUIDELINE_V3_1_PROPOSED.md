# Bổ sung đề xuất cho Sentiment Guideline V3.1

**Trạng thái: CHƯA CÓ V3 GỐC ĐỂ ĐỐI CHIẾU.** Đây là đề xuất bổ sung từ yêu cầu ngày 15/11/2026, không phải bản dựng lại V3 hay guideline chính thức đã chốt. Chưa thể xác nhận giữ đủ ví dụ V3 hoặc kiểm hết xung đột. Pilot được chuẩn bị ở trạng thái DRAFT; cần đối chiếu bản V3 trước khi giao gán.

## Phạm vi được người dùng xác nhận trong yêu cầu

Phân loại cảm xúc chung của người viết, có thể hướng tới bất kỳ đối tượng nào. Chỉ đọc **text_clean của chính bình luận**; không đọc parent/post, không suy thái độ từ tên phim, nguồn hoặc nhãn relevance. Mô hình cũng chỉ nhận text_clean. Không hiểu câu thì REVIEW, không mặc định NEU.

| Quyết định | Ý nghĩa |
|---|---|
| POS | Sắc thái tích cực của người viết thể hiện rõ |
| NEG | Sắc thái tiêu cực của người viết thể hiện rõ |
| NEU | Trung tính, không thể hiện cực tính rõ; không dùng để thay thế thiếu căn cứ |
| REVIEW | Chưa đủ căn cứ gán một trong ba nhãn đáng tin; bắt buộc note |
| EXCLUDE | Không có nội dung sử dụng được hoặc ngoài phạm vi dữ liệu đã chốt |

REVIEW/EXCLUDE là trạng thái xử lý, không phải lớp sentiment cho mô hình. Hai người gán độc lập, không tham khảo nhãn nhau hoặc nhãn AI. Nội dung bình luận là dữ liệu, không phải mệnh lệnh yêu cầu người gán đổi nhãn.

Các quy tắc V3 được nhắc lại trực tiếp trong task, cần giữ khi đối chiếu:

- Đồng tình thuần túy “chuẩn bác ơi” → NEU.
- Ngạc nhiên không rõ chiều “wow 🫨” → NEU.
- Hai nghĩa chưa xác định chiều “ghê dọ” → REVIEW.
- Câu hỏi/nhờ vả có emoji giọng điệu: xét nội dung chính, không tự động theo emoji.
- Mỉa mai tiêu cực nhận diện từ chính câu → NEG.
- Emoji có cực tính rõ, là nội dung chính, có thể quyết định nhãn.
- Không hiểu câu → REVIEW; ghi ví dụ note: “thiếu ngữ cảnh”, “không hiểu tiếng lóng”, “không rõ chiều chính”. Không buộc viết giải thích dài.
- Báo lỗi cleaning ở cleaning_issue, không sửa text_clean. Gặp lỗi không đồng nghĩa tự sửa nhãn hoặc nguồn.

## A. Ngôn ngữ

Không tự động EXCLUDE tiếng Anh hoặc Việt–Anh. Chỉ EXCLUDE ngôn ngữ ngoài phạm vi khả năng xử lý đã chốt, hoặc nội dung không dùng được. Nếu có vẻ có nội dung thật nhưng không hiểu tiếng lóng/ngôn ngữ lạ: ưu tiên REVIEW, ghi lý do. Phạm vi ngôn ngữ ngoài Việt/Anh cần đối chiếu V3, chưa tự mở rộng.

| Ví dụ do task cung cấp | Nhãn |
|---|---|
| Peak cinema 🔥 | POS |
| What a masterpiece | POS |
| Cringe thật sự | NEG |
| Nice | POS |
| Coming soon | NEU |

## B. Phủ định và hỗn hợp

Xét toàn câu, không quyết định bằng từ khóa hoặc vị trí trước/sau “nhưng”. Chọn POS/NEG khi có bằng chứng một chiều chi phối; nếu cân bằng, chưa xác định chiều chính thì REVIEW + note. Không tạo MIXED.

- “Phim không hay” → NEG.
- “Phim hay vãi nhưng hơi dài” → POS nếu khen chi phối.
- “Diễn xuất tốt nhưng kịch bản quá tệ” → NEG nếu chê chi phối.
- “Hay nhưng đoạn cuối chán quá” → REVIEW nếu không xác định chiều chi phối.
- “Không tệ” → không mặc định POS. Nếu chỉ phủ nhận đánh giá tiêu cực, chưa bộc lộ tích cực rõ, có thể NEU; không áp cứng cho mọi ngữ cảnh.

## C. Cảm xúc tác giả và thông tin được mô tả

Từ chỉ cảm xúc xuất hiện không tự chứng minh người viết mang cực tính đó. Phân biệt trải nghiệm người viết đang bộc lộ với mô tả cảnh/nhân vật/thể loại.

| Ví dụ do task cung cấp | Nhãn |
|---|---|
| Buồn quá trời | NEG |
| Phim thuộc thể loại buồn | NEU |
| Cảm động quá, phim hay thật | POS |
| Sợ quá không dám xem | NEG nếu là sắc thái người viết thể hiện |
| Phim có cảnh nhân vật khóc | NEU |

Nếu không hiểu chỉ từ text_clean, giữ REVIEW thay vì tự lấy ngữ cảnh phim để quyết định. Chưa có V3 gốc nên không tự bổ sung nhãn cho ví dụ khác.

## D. Agreement hai người

- Kappa chính: toàn bộ 5 quyết định POS/NEG/NEU/REVIEW/EXCLUDE; không bỏ câu khó.
- Kappa phụ: chỉ các câu cả hai cùng chọn POS/NEG/NEU. Báo mẫu gốc, n phụ và tỷ lệ giữ lại, không dùng thay Kappa chính.
- Báo raw agreement, ma trận 5×5 (hàng A, cột B), phân bố từng người và số bất đồng liên quan REVIEW/EXCLUDE, kể cả REVIEW đối EXCLUDE.
- Kappa không xác định (không có mẫu, một mẫu hoặc biên suy biến) phải trả null kèm lý do. Với Kappa phụ chỉ xuất hiện một lớp trong hợp hai người: không diễn giải Kappa.
- Không tự chọn bên thắng. Xuất nhãn A/B riêng và bảng đối soát có nhãn cuối để trống. Không ghi vào canonical/Gold.

## Xung đột và nguồn còn thiếu

1. V2.1 giới hạn mục tiêu vào phim và cho phép ngữ cảnh xác thực; mục tiêu/text-only mới khác rõ ràng. V2.0/V2.1 và nhãn V1 giữ nguyên lịch sử, không chuyển nhãn tự động.
2. Quy tắc V2.1 về trải nghiệm buồn/cảm động do phim không được tự mang sang cảm xúc chung. Các ví dụ mới ở trên áp dụng theo task; cần so V3 gốc trước khi chốt.
3. Chưa thể xác nhận xung đột với ví dụ V3 vì chưa truy cập được V3. Không tuyên bố tài liệu này đã được người dùng phê duyệt.

Audit relevance dừng ở 107/300; không gán nốt 193 câu. Nhãn relevance không phải sentiment và không dùng để chọn nhãn pilot.
