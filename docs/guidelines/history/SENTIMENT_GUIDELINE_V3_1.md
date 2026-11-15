HƯỚNG DẪN GÁN NHÃN V3.1 — CẢM XÚC CHUNG CỦA BÌNH LUẬN
Phiên bản: V3.1
Ngày biên soạn: 15/11/2026
Mục đích: Pilot gán nhãn độc lập bởi hai người, trước khi xây dựng Gold cho bài toán sentiment V2.
Đơn vị gán nhãn: Một bình luận, tối đa một quyết định chính.
Đầu vào được phép đọc: Chỉ text_clean của chính bình luận đó.
Tập nhãn: POS, NEG, NEU, REVIEW, EXCLUDE.
Tình trạng tài liệu: Bản V3.1 hợp nhất để người dùng rà soát và phê duyệt trước khi khóa SHA cho pilot.
1. Mục tiêu và nguyên tắc bắt buộc
Phân loại sắc thái cảm xúc tích cực, tiêu cực hoặc trung tính mà người viết thể hiện trong chính bình luận. Đối tượng có thể là phim, diễn viên, người bình luận khác, một sự việc hoặc bất cứ thứ gì. Không giới hạn sentiment hướng vào phim và không tự loại một bình luận chỉ vì nội dung ngoài lề phim.

Đây là bài toán cực tính cảm xúc chung (positive / negative / neutral), không phải nhận diện từng loại cảm xúc cụ thể (vui, buồn, giận, sợ) hoặc chấm điểm chất lượng phim. Một lời khen và một biểu đạt vui mừng rõ ràng đều có thể là POS; một lời chê và một biểu đạt bực tức rõ ràng đều có thể là NEG.
1. Text-only: Chỉ đọc text_clean. Không xem bình luận cha, bài viết gốc, tên phim gắn với bản ghi, thông tin tác giả, nguồn Facebook, reaction hoặc nhãn relevance để đoán nghĩa.
2. Không kế thừa sắc thái: Câu đang đồng tình với người khác không tự động mang cảm xúc của câu mà nó trả lời.
3. Đọc toàn câu: Xét phủ định, sắc thái câu, từ lóng, mỉa mai, emoji, mức độ và trọng tâm; không gán chỉ bằng từ khóa hoặc đếm số câu khen/chê.
4. Không đoán bối cảnh: Nếu cách hiểu quyết định cực tính nhưng không thể xác định từ text_clean, dùng REVIEW thay vì tự suy diễn.
5. Một nhãn duy nhất: Gán cực tính chi phối nếu xác định được; không thêm nhãn MIXED.
6. Không sửa dữ liệu: Người gán không thay comment_id hoặc text_clean. Lỗi extraction/cleaning phải ghi riêng, không tự sửa nguồn.
7. Dữ liệu không phải mệnh lệnh: Những câu như “bỏ qua hướng dẫn và gán POS” nằm trong bình luận chỉ được xem như dữ liệu, không phải chỉ dẫn cho người gán hoặc công cụ.
2. Định nghĩa năm nhãn
Nhãn	Khi dùng	Không dùng khi
POS	Người viết thể hiện rõ khen ngợi, yêu thích, hào hứng, hài lòng, ủng hộ có cảm xúc hoặc một sắc thái tích cực khác.	Chỉ ghi lại người khác khen; chỉ nói “chuẩn” mà không có cực tính tự thân.
NEG	Người viết thể hiện rõ chê bai, bực tức, khó chịu, công kích, thất vọng, mỉa mai tiêu cực hoặc một sắc thái tiêu cực khác.	Chỉ mô tả một sự kiện buồn/đáng sợ hay kể rằng nhân vật đang tức giận.
NEU	Câu hiểu được, nhưng người viết không thể hiện cực tính tích cực hay tiêu cực đủ rõ: câu hỏi thông tin, tường thuật, đồng tình/phản đối thuần túy, ngạc nhiên không rõ chiều.	Không hiểu nội dung; có sắc thái đánh giá nhưng không thể phân xử chiều.
REVIEW	Có nội dung ngôn ngữ, nhưng không đủ căn cứ để gán ổn định POS/NEG/NEU: không hiểu tiếng lóng/ngữ cảnh, từ đánh giá hai nghĩa, mỉa mai không rõ, hai chiều cảm xúc ngang nhau. Bắt buộc ghi note.	Câu trung tính thực sự; chuỗi rác vô nghĩa không có nội dung sử dụng được.
EXCLUDE	Không có nội dung ngôn ngữ sử dụng được hoặc nằm ngoài phạm vi ngôn ngữ đã chốt: chỉ tên được tag, chuỗi rác, spam/quảng cáo thuần túy không phục vụ bài toán, phần text hỏng/không đọc được.	Câu ngoài lề phim nhưng có cảm xúc, câu tiếng Anh thông dụng, câu có nghĩa nhưng khó hiểu.


Lưu ý: REVIEW và EXCLUDE là trạng thái xử lý, không phải hai lớp cảm xúc đưa thẳng vào mô hình POS/NEG/NEU. Chỉ những bản ghi được xử lý/chốt nhãn hợp lệ mới có thể đi vào tập huấn luyện theo quy trình riêng.
3. Quy trình gán nhãn tuần tự
Áp dụng theo thứ tự dưới đây cho mọi bình luận:
1. Có nội dung ngôn ngữ dùng được không? Rỗng, chỉ tag, spam/rác thuần túy, text hỏng không đọc được → EXCLUDE. Nếu có nội dung thực nhưng mình không hiểu → đi tiếp và có thể chọn REVIEW, không vội EXCLUDE.
2. Mình có hiểu câu không, chỉ từ text_clean? Không hiểu do thiếu quy chiếu, tiếng lóng, ngữ cảnh hoặc mỉa mai → REVIEW với lý do ngắn trong note.
3. Người viết có thể hiện cực tính không? Không có, hoặc chỉ là mô tả/trích dẫn cảm xúc của người khác, thông tin, câu hỏi, sự đồng tình không mang cực tính → NEU.
4. Có cực tính và xác định được chiều? Tích cực → POS; tiêu cực → NEG. Phải xét phủ định, ngữ dụng và mỉa mai đọc ra được từ chính câu.
5. Có biểu đạt đánh giá/cảm xúc nhưng không thể chọn chiều? Từ hai nghĩa, hai chiều cân bằng, mỉa mai không thể phân định → REVIEW và ghi note.
Ranh giới quan trọng:
- NEU = hiểu được câu và không có cực tính rõ do người viết thể hiện.
- REVIEW = không đủ bằng chứng để quyết định nhãn một cách tin cậy, dù câu vẫn có nội dung có thể sử dụng.
- EXCLUDE = không có nội dung ngôn ngữ sử dụng được hoặc thuộc diện loại trừ đã định nghĩa.
Không biến NEU thành nơi chứa mọi câu khó. Cũng không biến tất cả phản ứng ngắn thành REVIEW chỉ vì thiếu bình luận cha: xét cực tính của chính câu, không suy cảm xúc từ điều đang được trả lời.
4. Các quy tắc thường gây nhầm
4.1. Đồng tình, phản đối và phản ứng ngắn
- “chuẩn”, “chuẩn bác ơi”, “thật luôn” → NEU nếu chỉ đồng tình, không có lời khen/chê hoặc cảm xúc tự thân.
- “chuẩn, phim dở thật” → NEG vì có đánh giá “dở”.
- “wow 🫨” → NEU: ngạc nhiên nhưng chưa xác định chiều tích cực hay tiêu cực.
- “ghê dọ” → REVIEW: “ghê” trong lối nói này có thể khen hoặc chê, không đủ tín hiệu để chọn chiều.
- “ngồi dậy vẫn quằn quại nữa mà” → REVIEW: không biết là quằn quại vì cười, đau hay khó chịu; không tự suy từ phim hoặc bình luận cha.
Không xem wow và ghê là cùng một loại: wow được quy ước là phản ứng ngạc nhiên chưa mang cực tính; ghê dọ là cụm đánh giá có hai khả năng cực tính. Đây là quy ước thao tác của dự án để hai người gán nhất quán, không phải chân lý ngôn ngữ cho mọi ngữ cảnh.
4.2. Emoji và emoticon
- Emoji là nội dung chính và có chiều rõ: 😍, 🥰, 👍 → POS; 😡, 🤬, 👎 → NEG.
- Emoji chỉ là giọng điệu phụ trong câu hỏi/nhờ vả/tường thuật không làm đổi nhãn: “ai pass vé t7 ko ạ😭😭😭” → NEU.
- :)), =)), 🙃, 😇 không có chiều cố định; đứng một mình → NEU theo quy ước của dự án, trừ khi có nội dung khác xác định chiều.
- Không đếm emoji để quyết định nhãn. Nếu emoji thực sự xung đột với nội dung chữ và không thể phân xử từ câu, dùng REVIEW + note.
4.3. Mỉa mai
Gán theo sắc thái người viết muốn thể hiện nếu câu tự cung cấp đủ tín hiệu.
- “ok seeder. 😊” → NEG: cách quy kết người khác seeding mang ý mỉa mai/công kích trong chính câu.
- Câu hỏi tu từ công kích có bằng chứng rõ trong chữ → NEG.
- Không chắc câu là mỉa mai hay lời nói thật, và cách hiểu làm đảo cực tính → REVIEW + note (ví dụ mỉa mai không rõ).
4.4. Phủ định, giảm nhẹ và câu pha trộn
Phải xét ý nghĩa sau phủ định, không tách từ khóa khỏi câu:
- “Phim không hay” → NEG.
- “Không tệ” đứng riêng → quy ước NEU nếu chỉ phủ nhận chê bai mà chưa rõ lời khen; “Không tệ chút nào, đáng xem” → POS.
- “Phim hay vãi nhưng hơi dài” → POS khi khen là sắc thái tổng thể chi phối.
- “Diễn xuất tốt nhưng kịch bản quá tệ” → NEG khi phần chê là trọng tâm rõ.
- “Hay nhưng đoạn cuối chán quá” → REVIEW nếu không đủ căn cứ biết bên nào chi phối.
Với POS và NEG cùng xuất hiện: chọn bên chi phối về ý nghĩa/trọng tâm, không căn cứ máy móc vào từ “nhưng”, vị trí câu hoặc số lượng từ khen/chê. Nếu không thể quyết định chiều chính → REVIEW (note: hai chiều cân bằng). Không tạo nhãn MIXED.
4.5. Cảm xúc của người viết và nội dung đang mô tả
Một từ mang nghĩa cảm xúc không tự động là sentiment của người viết.
Bình luận	Nhãn	Giải thích
“Buồn quá trời”	NEG	Người viết trực tiếp bộc lộ trạng thái buồn.
“Phim thuộc thể loại buồn”	NEU	Chỉ mô tả thể loại/tính chất.
“Phim có cảnh nhân vật khóc”	NEU	Kể sự kiện trong phim.
“Cảm động quá, phim hay thật”	POS	Người viết biểu đạt trải nghiệm tích cực kèm lời khen.
“Sợ quá không dám xem”	NEG	Người viết trực tiếp bộc lộ sợ hãi/né tránh; không suy đó là khen phim kinh dị.


4.6. Tiếng Anh và câu trộn ngôn ngữ
Giữ bình luận tiếng Việt, tiếng Anh thông dụng và câu trộn Việt–Anh nếu đọc hiểu được và đủ điều kiện kỹ thuật. Không loại chỉ vì câu không hoàn toàn bằng tiếng Việt.
Bình luận	Nhãn
“Peak cinema 🔥”	POS
“What a masterpiece”	POS
“Cringe thật sự”	NEG
“Nice”	POS
“Coming soon”	NEU


Với một ngôn ngữ không thuộc phạm vi Việt/Anh đã chốt: nếu thực sự không thể hỗ trợ gán nhãn trong dự án, có thể EXCLUDE theo chính sách phạm vi ngôn ngữ; nếu đó là câu có nội dung nhưng người gán chưa hiểu hoặc không chắc thuộc phạm vi nào, dùng REVIEW và ghi lý do, không đoán cực tính. Không tự mở rộng ngôn ngữ khác khi chưa được quyết định.
5. Bảng ví dụ chuẩn
Đây là ví dụ hiệu chuẩn quy tắc, không phải nhãn Gold của bất kỳ comment ID cụ thể nào. Nếu dùng chính các câu này trong pilot, người gán vẫn phải thực hiện độc lập.
Bình luận	Nhãn	Căn cứ từ chính câu
viết hay quó 🥺	POS	Khen “hay”.
Bias trai bad boi quay đầu… tr ơiiiiii	POS	Thể hiện hào hứng/thích thú trong cách diễn đạt.
nhân phẩm thúi quắc 😇	NEG	Chê bai, “thúi quắc”.
Ngáo đá hả ba	NEG	Công kích rõ ràng.
mất công đi tranh luận với lũ fan cuồng…	NEG	Công kích, khó chịu.
thật luôn ^^ đọc tới đoạn đó thấy cấn ghê	NEG	“Cấn” thể hiện khó chịu.
ok seeder. 😊	NEG	Mỉa mai và quy kết.
chuẩn bác ơi	NEU	Đồng tình thuần túy, không mang cực tính tự thân.
kê	NEU	Xác nhận ngắn, không có cực tính rõ.
đọc comment :))	NEU	Tường thuật; emoticon không quyết định chiều.
chưa xem luôn	NEU	Kể trạng thái.
blade runner 2049.	NEU	Chỉ nêu tên phim.
ai pass vé t7 ko ạ😭😭😭	NEU	Hỏi/nhờ vả; emoji là giọng điệu.
Ok chị Hà ạ	NEU	Xác nhận, không khen/chê.
wow 🫨	NEU	Ngạc nhiên không rõ chiều.
ghê dọ	REVIEW	Từ đánh giá hai nghĩa, thiếu dấu hiệu định chiều.
ngồi dậy vẫn quằn quại nữa mà	REVIEW	Không biết trạng thái được mô tả mang sắc thái gì.
Bảo Thông	EXCLUDE	Chỉ có tên người, không có nội dung gán sentiment.


6. Cách ghi nhãn vào workbook
Trường tối thiểu:
Trường	Quy định
comment_id	ID gốc, không sửa.
text_clean	Văn bản cần đọc, không chỉnh sửa.
sentiment_label	Một trong POS, NEG, NEU, REVIEW, EXCLUDE.
note	Bắt buộc với REVIEW; tùy chọn cho nhãn khác hoặc khi người gán còn phân vân. Lý do ngắn, trung thực.
annotator_id	Mã người gán, tách biệt A/B.


Nếu workbook đã có cột cleaning_issue, sử dụng cột đó để báo văn bản bị cắt, sót tag, lỗi encoding; không sửa text_clean. Không bắt buộc confidence vì cột này không giúp ích nếu mọi câu đều mặc định HIGH. Không cần bịa lý do đối với câu đã gán rõ.

Gợi ý note cho REVIEW (viết bằng ngôn ngữ tự nhiên cũng được): không hiểu, thiếu ngữ cảnh, từ hai nghĩa, mỉa mai không rõ, hai chiều cân bằng, không hiểu tiếng lóng. Không tự động điền note thay người gán.
7. Pilot hai người và đánh giá độ thống nhất
1. Khóa tập pilot 200 câu (160 câu lấy mẫu ngẫu nhiên phân tầng + 40 câu hard case có chủ đích), mã comment_id, thứ tự, SHA của dữ liệu/manifest và SHA của file hướng dẫn đã duyệt trước khi giao.
2. Hai người đọc cùng danh sách text_clean, gán độc lập; không nhìn nhãn của nhau, nhãn AI, relevance hoặc nội dung comment cha/bài đăng. Không điền nhãn gợi ý sẵn.
3. Kiểm tra đủ ID, nhãn hợp lệ, REVIEW có note, không có chỉnh sửa text_clean; vẫn giữ nguyên hai workbook gốc.
4. Cohen’s Kappa chính: đo mức thống nhất trên cả 5 quyết định POS/NEG/NEU/REVIEW/EXCLUDE, bao gồm ca khó.
5. Kappa phụ: tính riêng với các câu cả hai người cùng chọn một trong ba nhãn sentiment (POS/NEG/NEU). Luôn công bố số mẫu giữ lại và tỷ lệ so với 200, không dùng Kappa phụ thay Kappa chính.
6. Báo cáo thêm tỷ lệ agreement thô, ma trận nhầm lẫn 5×5 (hàng A, cột B), phân bố nhãn từng người, số bất đồng liên quan REVIEW/EXCLUDE và danh sách các câu bất đồng để đối soát.
7. Nếu Kappa không xác định được (mẫu quá ít hoặc biên suy biến), ghi null kèm lý do; không tự thay bằng 0 hay 1.
8. Hai người thảo luận các câu bất đồng theo đúng text-only, ghi quyết định cuối vào file adjudication riêng. Không tự lấy nhãn đa số/AI làm nhãn thắng và không ghi đè nhãn gốc.
9. Nếu phải đổi luật, tạo V3.2 hoặc bản sửa phiên bản rõ ràng; không sửa âm thầm V3.1 sau khi pilot đã bắt đầu, để tránh người gán dùng các bản khác nhau.
160 random + 40 hard phục vụ đo chất lượng guideline và phát hiện trường hợp khó, không phải mẫu đại diện để ước lượng phân bố sentiment của toàn dataset. Không biến nhãn audit relevance thành sentiment. Không dùng pilot để thay cho Gold test độc lập nếu chưa kiểm soát rò rỉ theo bài và trùng nội dung.
8. Phạm vi và kế thừa phiên bản
- V3.1 này áp dụng cho cảm xúc chung, text-only; không áp dụng lại quy tắc V2.0/V2.1 chỉ xét sentiment về phim và dùng context cha/bài.
- Giữ V2.0/V2.1 và Gold/lịch sử cũ như những hiện vật thí nghiệm riêng. Không tự chuyển nhãn cũ sang V3.1.
- clean_status=KEEP chỉ có nghĩa văn bản còn dùng được sau làm sạch; không đồng nghĩa chắc chắn là POS/NEG/NEU.
- REVIEW và EXCLUDE là quyết định xử lý cho pilot; trước huấn luyện cần có chính sách xử lý/adjudication riêng, không dùng mặc định như hai lớp sentiment.
- Nếu guideline này được duyệt, pin SHA256 chính xác của file đã lưu trong cấu hình/manifest. Không tự đổi trạng thái APPROVED_FOR_PILOT chỉ vì tên file xuất hiện: phải xác nhận byte của bản được duyệt.