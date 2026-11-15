# Hướng dẫn gán nhãn V3.2 — Cảm xúc chung của bình luận

Thay đổi so với V3.1 (sau pilot 200 câu, Kappa 5 nhãn 0,60, 3 nhãn 0,78): thu hẹp EXCLUDE; công kích người là NEG; tách tranh luận NEU và tranh luận NEG; mỉa mai mặc định đọc nghĩa đen; thu hẹp REVIEW.

## Nguyên tắc cốt lõi

Chỉ đọc `text_clean` của chính bình luận. Không xem comment cha, bài viết, tên phim, nguồn hay nhãn relevance cũ, và không suy ra cảm xúc của ý kiến mà câu đang đáp lại. Cảm xúc có thể hướng tới phim, diễn viên, người bình luận khác, group hay bất cứ đối tượng nào. Mô hình cũng chỉ nhận `text_clean`.

## Năm quyết định

| Nhãn | Khi nào |
|---|---|
| POS | Có tín hiệu tích cực rõ: khen, thích thú, hào hứng, hài lòng, xúc động tích cực |
| NEG | Có tín hiệu tiêu cực rõ: chê, bực, chửi, công kích, chế giễu, thất vọng, buồn, sợ, mỉa mai có dấu hiệu rõ |
| NEU | Hiểu được câu và câu không có từ hay biểu cảm nào mang cực tính: hỏi, kể, thông tin, rủ rê, hẹn hò, xã giao, đồng tình hoặc phản đối thuần túy, đính chính, ngạc nhiên không rõ chiều |
| REVIEW | (a) Không hiểu câu; (b) có từ mang cảm xúc nhưng hai nghĩa ngược nhau và không có gì trong câu để chọn; (c) khen và chê ngang nhau. Bắt buộc ghi `note` |
| EXCLUDE | Chỉ khi không có nội dung ngôn ngữ: chỉ tên người hoặc tiếng gọi, chỉ tag, spam, quảng cáo, ký tự vô nghĩa, ngôn ngữ ngoài tiếng Việt và tiếng Anh |

REVIEW và EXCLUDE là trạng thái xử lý, không phải lớp của mô hình.

## EXCLUDE chỉ dành cho câu không có nội dung

Câu ngắn, xã giao, chuyện riêng, không liên quan phim vẫn là câu có nội dung: gán NEU nếu không có cực tính. Mô hình sẽ gặp những câu này khi chạy thật nên cần học chúng.

| Câu | Nhãn |
|---|---|
| bye / thế à / sao em? / xem k | NEU |
| xin vía ạ 🥲🥲 / cùng đợi nhé!!! | NEU |
| m7 t mới vô lại sg đó nha / kèo t4 tp còn chưa trả :)) | NEU |
| xin clip bạn ơi, ib mình luôn nhé. Cảm ơn | NEU |
| Ủa tag thiếu / Vân nào? | NEU |
| 2 ơi 2 ơi | EXCLUDE (chỉ tiếng gọi) |
| tên người đứng một mình | EXCLUDE |

Sót tên tag ở đầu câu ("Người tham gia ẩn danh…", tên người): bỏ qua phần tên, gán theo phần còn lại, ghi `cleaning_issue`. Chỉ EXCLUDE khi bỏ tên đi không còn gì.

## Công kích, chế giễu người khác là NEG

Chê hay chửi bất kỳ ai (người bình luận, người viết review, group, fan) đều là NEG, dù không nói về phim.

| Câu | Nhãn |
|---|---|
| m chê mới dở á má | NEG |
| Loz viết bài review buồn cười vl, nằm đọc chê mà tưởng xem hài. | NEG |
| …dần dần tôi thấy group này cũng cực đoan quá… toxic ra sao nữa. | NEG |
| …ị 1 bãi vào mồm mấy thằng lol thượng đẳng… | NEG |
| …gu ông chắc xem nhiều clip tổng tài bá đạo ở tiktok… | NEG |
| …sao k đi hát đi mà ở đây review phim vậy c :)))) | NEG (chế giễu) |

## Tranh luận: NEU hay NEG

Tranh luận, đính chính, phản biện bằng lý lẽ mà không có từ chê hay giọng gắt → NEU. Có từ chê, chê đối phương, hoặc giọng gắt → NEG. Từ chê trong câu giả định hay nói chung chung ("nếu kịch bản tệ thì…") không tính.

| Câu | Nhãn | Lý do |
|---|---|---|
| Bạn ghi sai òy, các nv k phải thoại quá nhiều mà là thoại quá dài nghen | NEU | đính chính nhẹ |
| Vé số muốn số mấy là quyền của ngta mà bạn… | NEU | phản đối thuần túy |
| Bài này đăng bên… mình thấy mấy cái lí lẽ cứ như kiểu… | NEU | phản biện lý lẽ |
| mình chỉ phản bác lại ý kiến của b… nếu kịch bản tệ thì dv cũng k thể… | NEU | "tệ" là giả định |
| …theo đúng kịch bản thì vụ không tặc đó kết thúc trong 10p rồi. Ko có j để xem 😅 | NEU | giải thích |
| chắc bạn không coi phim… | NEG | chê đối phương, giọng gắt |
| …nó vừa sai về đọc hiểu lẫn cách lí luận… | NEG | chê đối phương |
| …p2 lại k có j "mới lạ" cho nên trở thành k như kì vọng… | NEG | thất vọng |
| …Thời gian khúc này cấn cấn có ai giải thích giúp mình với. | NEG | "cấn" là khó chịu, kể cả trong câu hỏi |

## Mỉa mai

Mặc định đọc nghĩa đen. Chỉ gán theo nghĩa mỉa mai khi câu có dấu hiệu rõ: hỏi tu từ, khen vô lý, "dạ… ạ" kèm ý móc, nói ngược với điều hiển nhiên. Không có dấu hiệu thì gán theo nghĩa đen, không REVIEW chỉ vì "có thể là mỉa mai".

| Câu | Nhãn | Lý do |
|---|---|---|
| Cám ơn vì không phải seeder | POS | nghĩa đen |
| Với bài viết này thì bạn xứng đáng được thưởng 100 lần xem phim kinh dị VN | NEG | "thưởng" xem phim bị chê là phạt |
| …chắc là phải lãi khủng lắm rồi nhỉ! | NEG | hỏi tu từ |
| dạ không phải ai cũng thích mua sub với add friend ảo ạ | NEG | "dạ… ạ" kèm móc |
| ok seeder. 😊 | NEG | quy kết |
| Tấu hài tốt:))) | REVIEW | khen hài hay chê "tấu hài" đều được |

## Câu hỗn hợp

Xét cả câu, chọn chiều chiếm phần lớn. Khen hoặc chê một phim khác chỉ để so sánh thì không tính bằng nhận xét chính. Chỉ REVIEW khi thật sự ngang nhau.

| Câu | Nhãn |
|---|---|
| Xem thiên đường máu hay thật nhưng phim này thấy nhiều bài chê quá nên vẫn chần chừ | POS |
| Chê t tán cho ý phim hay mà k biết thưởng thức | POS |
| cho 4 là cao r í, cố chê là 1. Khúc cuối xàm l nhưng tổng quan thì coi đc | NEG |
| …Thiên Đường Máu có cái hay… Còn phim này né luôn… | NEG |
| Phim hay vãi nhưng hơi dài | POS |
| Phim không hay / Diễn xuất tốt nhưng kịch bản quá tệ | NEG |
| Không tệ (không khen thêm) | NEU |

## Ranh giới NEU – REVIEW

1. Không hiểu câu (tiếng lóng, viết tắt lạ) → REVIEW, note ngắn. Không gán NEU chỉ vì không hiểu.
2. Hiểu, không có từ hay biểu cảm mang cực tính → NEU.
3. Có, xác định được chiều → POS/NEG.
4. Có, nhưng từ đó hai nghĩa ngược nhau và không có gì khác để chọn → REVIEW.

| Câu | Nhãn |
|---|---|
| con hợp thể / 50k để chuộc truyện | REVIEW (không hiểu) |
| ê ý là hai phe khen chê thảo luận đọc tẩm đá thế nhỉ =))))) | REVIEW (không hiểu "tẩm đá") |
| ghê dọ | REVIEW (hai nghĩa) |
| gravity đoạn từ vũ trụ về nổi cả da gà 😂 | POS (khen cảnh, có 😂) |
| …trúng Tú🤣🤣🤣 | POS (hào hứng) |
| ng miền nam dễ tính thiệt chứ bộ :))) | POS (khen) |
| mai mốt m lên bài phim mùi cỏ cháy cho xem này | NEU (rủ, không có cực tính) |
| wow 🫨 / chuẩn bác ơi | NEU |

## Cảm xúc người viết và nội dung được kể

- "Buồn quá trời", "Sợ quá không dám xem" → NEG. "Phim thuộc thể loại buồn", "Phim có cảnh nhân vật khóc" → NEU.
- "Cảm động quá, phim hay thật" → POS.

## Emoji, emoticon

- Emoji/emoticon đứng một mình hoặc là phần chính và có chiều rõ (😍 🥰 👍 → POS; 😡 🤬 👎 → NEG) → gán theo emoji.
- Emoji chỉ là giọng điệu trong câu hỏi, nhờ vả, kể chuyện → xét phần chữ.
- `:))`, `=))`, 🙃, 😇 không tự quyết định nhãn; đứng một mình → NEU.

## Tiếng Anh, Việt–Anh

Không tự động EXCLUDE. "Peak cinema 🔥", "Nice" → POS; "Cringe thật sự" → NEG; "Coming soon" → NEU.

## Cột workbook

`comment_id`, `text_clean`, `sentiment_label`, `note` (bắt buộc khi REVIEW), `annotator_id`, `cleaning_issue`.

Không dùng AI để quyết định nhãn hay viết note. Được tra nghĩa một từ lóng, ghi vào note là đã tra.

## Quy trình

1. Hai người gán độc lập, không xem nhãn của nhau hay nhãn AI.
2. Kappa chính trên 5 quyết định; Kappa phụ trên các câu cả hai cùng chọn POS/NEG/NEU.
3. Đối soát câu lệch; quy tắc chưa rõ thì bổ sung ví dụ, tăng phiên bản.