# Rà soát bộ đa phim đã gán

Đã đọc đủ 200 câu và rà riêng cả 20 câu POS. Giữ nguyên workbook và mọi nhãn người.

## Tình trạng điền nhãn

- Đủ 200/200 nhãn: 20 POS, 137 NEG, 22 NEU, 20 EXCLUDE, 1 REVIEW.
- Không thiếu/trùng ID; không có từ ngữ comment bị thay đổi.
- Dòng Excel 155 (`spoil =))`) là REVIEW nhưng chưa có review_reason.
- Dòng 58, 59, 80, 180 chỉ mất một dấu cách cuối. Khôi phục từ task trong bản chuẩn hóa sau này; không cần gán lại.
- Status còn trống ở 198 dòng không đồng nghĩa sót nhãn. Bước chuẩn hóa có thể tự điền/chuyển trạng thái từ nhãn đã nhập.

## Cách hiểu POS sau khi người gán làm rõ

A clearly positive emotional impact, empathy or valued viewing experience may count as POS without an explicit statement that the film is good. Do not mechanically relabel crying or fear as wrong POS. Ambiguous emotional words alone still do not establish positive impact.

Cách hiểu này rộng hơn câu chữ R06 hiện tại. Guideline và task gốc không bị sửa. Cần ghi nhận cách áp dụng nhất quán trước khi tạo release chính thức.

Không phát hiện ca POS nào rõ ràng phải đảo sang NEG. Dòng 87 có thể giữ POS theo tiêu chí tác động cảm xúc tích cực. Các trường hợp còn mơ hồ không bị tự động coi là gán sai.

## Những dòng nên ưu tiên kiểm lại

| Dòng Excel | Hiện tại | Gợi ý để người gán chốt | Lý do |
|---:|---|---|---|
| 26 | NEG | POS | Đang giải thích và bênh lựa chọn phục trang/ẩn dụ của phim, kết luận “Đó kh phải lỗi, đó là tính năng”; không phải lời chê phim. |
| 77 | NEG | POS hoặc REVIEW(REV_MIXED) | Với phim đang xét, tác giả nói “trung bình, xem được”, quảng cáo không lố; lời công kích mạnh nhắm bộ phim khác. Nghiêng POS nhẹ theo R01; không tự áp NEG từ phần ngoài lề. |
| 139 | NEU | POS | Có điểm trừ nhưng khẳng định “Điểm cộng: những cái còn lại” và đánh giá tổng thể 8/10. Không phải câu chỉ tường thuật thông tin trung tính. |
| 6 | NEU | NEG | Nhận định tính khoa học của kịch bản không cao và việc một người trộm vặt thành nhà khoa học lượng tử là phê bình cách xây dựng, không chỉ kể nội dung. |
| 190 | NEU | NEG | Kết luận “phim 5đ vì k có gì đặc sắc thật” thể hiện đánh giá không hài lòng; không phải thông tin thuần túy. |
| 40 | NEG | EXCLUDE | Nhận xét/dạy đời người viết bài hoặc người đọc; không có nhận xét về tác phẩm trong chính comment. |
| 161 | NEG | EXCLUDE | “như m combat ... trình độ của bản thân t” chê đối phương tranh luận; chữ “chê” không làm nó thành sentiment NEG về phim. |
| 112 | EXCLUDE | NEU | Nói về phim được đặt sản xuất, doanh thu, đi tranh giải và phát hành trên nền tảng mạng. Đây là thông tin trong miền phim, chưa có đánh giá chất lượng. |

## Các ca POS còn phụ thuộc cách hiểu/ngữ cảnh

| Dòng Excel | Hiện tại | Nhận xét |
|---:|---|---|
| 55 | POS | “ám ảnh cảnh đó cả tháng” có thể là tác động phim mong muốn hoặc trải nghiệm tiêu cực. Parent xác thực nói sợ cảnh người chồng bà quản gia dưới tầng hầm. Không tự kết luận POS sai; tác động tích cực chưa được nói rõ. Giữ POS nếu m xác nhận đang trân trọng tác động phim; nếu chỉ sợ/ám ảnh thì REVIEW(REV_OTHER). |
| 150 | POS | Câu hỏi “phim nào ... choáng ngợp hơn Avatar 2” có thể là tu từ hoặc xin so sánh. Parent trực tiếp được lưu đang khen Avatar 2, nên không dùng riêng emoji để xác định mỉa mai hoặc lấy nhãn parent áp sang reply. POS nếu là lời bênh kỹ xảo; NEU nếu hỏi thật; REVIEW(REV_CONTEXT) nếu chưa xác định. |
| 180 | POS | Khen cảnh quay/diễn viên “cực kì tuyệt vời”, đồng thời chê nội dung rời rạc và kết nhạt/hụt hẫng. POS có thể bảo vệ được theo trọng tâm m chọn; không có căn cứ tự đổi thẳng NEG. POS nếu trọng tâm là khen; REVIEW(REV_MIXED) nếu hai phía không phân giải được. |
| 195 | POS | Chưa xem trọn phim, chỉ nói lướt TikTok và “suy” với nhân vật. Có thể thể hiện gắn bó tích cực, nhưng riêng chữ “suy” không tự xác định thái độ với phim. Giữ POS nếu đây là tác động tích cực m đọc được; nếu không rõ thì REVIEW(REV_OTHER). |

## Các dòng khác có thể xem sau

- **Dòng 62 (NEU):** Có phê bình diễn xuất/chuyển thể và lời khen rõ, điểm 8,5. Có đánh giá thực sự nên không mặc định NEU vì khen/chê cùng xuất hiện. Gợi ý: REVIEW(REV_MIXED) hoặc nhãn chủ đạo sau khi đọc lại.
- **Dòng 91 (NEG):** Parent xác thực đang phản bác người review chê Dune nhiều thoại. Reply tiếp tục bình phẩm nhận xét đó; chưa có lời chê trực tiếp phim từ chính tác giả reply. Gợi ý: EXCLUDE hoặc REVIEW(REV_TARGET).
- **Dòng 124 (NEU):** “có ... thì tuyệt đối điện ảnh” mang đánh giá/kỳ vọng, không hẳn chỉ hỏi hoặc kể dữ kiện. Không dùng hiểu biết ngoài để quyết định cameo có thật hay không. Gợi ý: POS nếu là kỳ vọng mong muốn cameo; REVIEW(REV_SARCASM) nếu đang mỉa mai.
- **Dòng 165 (NEG):** “ráng rặn được vài câu ... như cc” không nêu rõ phim hay bài/comment. Parent đang nói seeding/truyền thông; cần phân biệt chê nội dung viết với chê phim. Gợi ý: REVIEW(REV_TARGET) trước khi ép NEG.
- **Dòng 178 (NEU):** “phim hài nhảm rác mức dưới trung bình” là đánh giá tiêu cực/dự báo chất lượng, không phải lời kể trung tính; cần chốt phạm vi đối tượng nếu đang nói chung ngành phim. Gợi ý: NEG hoặc REVIEW(REV_TARGET).
- **Dòng 181 (NEG):** Yêu cầu người review chê các phim cho sòng phẳng, chưa thể hiện chính tác giả đang đánh giá chất lượng phim thế nào. Gợi ý: EXCLUDE hoặc REVIEW(REV_TARGET).
- **Dòng 49 (NEG):** Khen kết/độ vui/cặp diễn viên, chê một vai và nói gần bản Hàn. Không thấy kết luận tiêu cực rõ để tự xem mọi nhận xét trong câu là NEG. Gợi ý: POS hoặc REVIEW(REV_MIXED), cần xác định trọng tâm.
- **Dòng 74 (NEG):** Vừa chê nội dung/CGI vừa khen hình ảnh, âm thanh “gánh nguyên film”; không chọn NEG chỉ vì câu mở đầu có lời chê. Gợi ý: REVIEW(REV_MIXED) nếu chưa rõ đánh giá tổng thể.

## Nội dung đầy đủ cho các đề nghị

### Dòng 26 — NEG

Peter Hoàng sạch và trắng là vì cổ là tiểu thư khuê các, đi đâu cũng chăm chút ngoại hình, chiến tranh vẫn có thể áo gấm lụa là, trc còn có nhà 3 tầng phố cổ có đàn piano. Thứ 2 là cổ mới ngủ dậy, đang hàn huyên với ngyeu thì gặp địch đến, sau giây phút ngắn ngủi lo sợ thì cổ liều chet lao vào xe tăng luôn chứ không có xô xát. Đó là lý do đồ cổ trắng bóc vậy, nhưng mình nghĩ đó cũng là hình ảnh ẩn dụ tạo nên sự tương phản giữa sự trong sạch của tấm lòng ng dân yêu nước với chiến tranh tang tóc đau thương. Đó kh phải lỗi, đó là tính năng =))))))))))))

Nhận xét: Đang giải thích và bênh lựa chọn phục trang/ẩn dụ của phim, kết luận “Đó kh phải lỗi, đó là tính năng”; không phải lời chê phim.

### Dòng 77 — NEG

Hay cũng được, dở cũng được. Chỉ cần hay hay dở cũng có bản lĩnh tự sinh tự diệt, không khóc tu tu bao biện, bơm thổi rồi tìm mọi cách lùa gà ra rạp như bộ-phim-nào-đó-full-suất-chiếu để ăn doanh thu bất chấp là khán giả đã thông cảm cho rồi.
Cá nhân tui thấy phim này ở mức trung bình, xem được. Nhất là quảng cáo sao, phim vậy, không lố quá. Tuy nhiên một số chi tiết gượng ép.

Nhận xét: Với phim đang xét, tác giả nói “trung bình, xem được”, quảng cáo không lố; lời công kích mạnh nhắm bộ phim khác. Nghiêng POS nhẹ theo R01; không tự áp NEG từ phần ngoài lề.

### Dòng 139 — NEU

Điểm trừ: kĩ xảo lỏ, khúc cuối thấy hơi hụt, đoạn gia tiên đỡ cho kiếp nạn ảo như phim siêu nhưn
Điểm cộng: những cái còn lại =)))
Cũng cũng 8/10 đối với t, mém khóc trong rạp

Nhận xét: Có điểm trừ nhưng khẳng định “Điểm cộng: những cái còn lại” và đánh giá tổng thể 8/10. Không phải câu chỉ tường thuật thông tin trung tính.

### Dòng 6 — NEU

Lý thuyết lượng tử rất khó và chưa có nhiều nghiên cứu đột phá, nên tính khoa học của kịch bản nó không cao. Chưa kể từ từ 1 trộm vặt được boot lên thành nhà khoa học lượng tử luôn.

Nhận xét: Nhận định tính khoa học của kịch bản không cao và việc một người trộm vặt thành nhà khoa học lượng tử là phê bình cách xây dựng, không chỉ kể nội dung.

### Dòng 190 — NEU

cuối phim đâu có đề cập ông sông hay chết .tóm lại phim 5đ vì k có gì đặc sắc thật

Nhận xét: Kết luận “phim 5đ vì k có gì đặc sắc thật” thể hiện đánh giá không hài lòng; không phải thông tin thuần túy.

### Dòng 40 — NEG

Đọc cũng được nhưng chớ dạy đời người đọc phải làm gì, nên liên hệ bản thân thôi

Nhận xét: Nhận xét/dạy đời người viết bài hoặc người đọc; không có nhận xét về tác phẩm trong chính comment.

### Dòng 161 — NEG

như m combat đúng là kéo thấp trình độ của bản thân t 🙂 chê nha má

Nhận xét: “như m combat ... trình độ của bản thân t” chê đối phương tranh luận; chữ “chê” không làm nó thành sentiment NEG về phim.

### Dòng 112 — EXCLUDE

Minh Duy Võ kp nha, phim nhà nước đặt sx nên doanh thu sao cũng đc chỉ để đủ kpi đi tranh giải thôi. với sau là chiếu trên các nền tảng mạng chứ k bán.

Nhận xét: Nói về phim được đặt sản xuất, doanh thu, đi tranh giải và phát hành trên nền tảng mạng. Đây là thông tin trong miền phim, chưa có đánh giá chất lượng.

### Dòng 55 — POS

t bị ám ảnh cảnh đó cả tháng luôn á tr

Nhận xét: “ám ảnh cảnh đó cả tháng” có thể là tác động phim mong muốn hoặc trải nghiệm tiêu cực. Parent xác thực nói sợ cảnh người chồng bà quản gia dưới tầng hầm. Không tự kết luận POS sai; tác động tích cực chưa được nói rõ.

### Dòng 150 — POS

vậy phim nào theo bạn kỹ xảo đồ hoạ siêu đỉnh và choáng ngợp hơn Avatar 2 thế ạ? 🌝

Nhận xét: Câu hỏi “phim nào ... choáng ngợp hơn Avatar 2” có thể là tu từ hoặc xin so sánh. Parent trực tiếp được lưu đang khen Avatar 2, nên không dùng riêng emoji để xác định mỉa mai hoặc lấy nhãn parent áp sang reply.

### Dòng 180 — POS

Nguyễn Gia Hưng nội dung thì rời rạc thật nhưng mình thấy cảnh quay và diễn viên thì cực kì tuyệt vời nè... chỉ có điều xem xong kết khá là nhạt nên hơi hụt hẫng thôi

Nhận xét: Khen cảnh quay/diễn viên “cực kì tuyệt vời”, đồng thời chê nội dung rời rạc và kết nhạt/hụt hẫng. POS có thể bảo vệ được theo trọng tâm m chọn; không có căn cứ tự đổi thẳng NEG.

### Dòng 195 — POS

ở nước ngoài không xem đc hicc mà lướt tiktok suy ngang với Cường Quang huhu 😭😭😭

Nhận xét: Chưa xem trọn phim, chỉ nói lướt TikTok và “suy” với nhân vật. Có thể thể hiện gắn bó tích cực, nhưng riêng chữ “suy” không tự xác định thái độ với phim.

### Dòng 62 — NEU

Đồng ý là overrated, nhưng theo mình là ở phần diễn xuất, thiết lập của 2 nhân vật Paul vs Chani không đủ để người xem có sự đồng cảm. Một số tình tiết thay đổi so với truyện gây nên sự khó hiểu/không đúng cảm nhận về nhân vật. Đối với mình người xuất sắc nhất là Lệnh bà Jessica, nhưng phần phản ánh về tôn giáo chưa đủ hay ở 2 phần Dune 1 và 2. Mình chỉ chấm 8,5đ.

Nhận xét: Có phê bình diễn xuất/chuyển thể và lời khen rõ, điểm 8,5. Có đánh giá thực sự nên không mặc định NEU vì khen/chê cùng xuất hiện.

### Dòng 91 — NEG

nghe thoại nhiều cái bật ngửa, cỡ này xem Oppenheimer chắc xỉu ngang trong rạp 🤤

Nhận xét: Parent xác thực đang phản bác người review chê Dune nhiều thoại. Reply tiếp tục bình phẩm nhận xét đó; chưa có lời chê trực tiếp phim từ chính tác giả reply.

### Dòng 124 — NEU

after credit có quả Leon Kennedy do Robert Pattinson đóng chạy ra thì tuyệt đối điện ảnh

Nhận xét: “có ... thì tuyệt đối điện ảnh” mang đánh giá/kỳ vọng, không hẳn chỉ hỏi hoặc kể dữ kiện. Không dùng hiểu biết ngoài để quyết định cameo có thật hay không.

### Dòng 165 — NEG

cũng ráng rặn được vài câu. Nhưng nó như cc vậy á.

Nhận xét: “ráng rặn được vài câu ... như cc” không nêu rõ phim hay bài/comment. Parent đang nói seeding/truyền thông; cần phân biệt chê nội dung viết với chê phim.

### Dòng 178 — NEU

z thì mỗi năm sẽ càng nhiều phim hài nhảm rác mức dưới trung bình và điển ảnh việt ko ngóc đầu lên nổi

Nhận xét: “phim hài nhảm rác mức dưới trung bình” là đánh giá tiêu cực/dự báo chất lượng, không phải lời kể trung tính; cần chốt phạm vi đối tượng nếu đang nói chung ngành phim.

### Dòng 181 — NEG

Chê Lật Mặt 8 thậm tệ thì mi nhớ cũng sòng phẳng với phim Phan Tểu, thầy của mi y vậy nha chưa.

Nhận xét: Yêu cầu người review chê các phim cho sòng phẳng, chưa thể hiện chính tác giả đang đánh giá chất lượng phim thế nào.

### Dòng 49 — NEG

Phim gần như copy nguyên bản Hàn. Có phần kết có vẻ tích cực hơn, phần diễn của Thu Trang khiến phim vui hơn. Đoạn của Hứa Vĩ Văn lúc trả lời đt của con gái hơi kém, cảm xúc ko tới đc như bản Hàn. Phim này đóng tốt nhất là cặp Bình Quỳnh

Nhận xét: Khen kết/độ vui/cặp diễn viên, chê một vai và nói gần bản Hàn. Không thấy kết luận tiêu cực rõ để tự xem mọi nhận xét trong câu là NEG.

### Dòng 74 — NEG

Nội dung dễ đoán, quá nhàn
Hình ảnh ấn tượng, CGI đánh đấm bị khựng vài chỗ, không mượt bằng A1 
Âm thanh, hiệu ứng ok gánh nguyên film

Nhận xét: Vừa chê nội dung/CGI vừa khen hình ảnh, âm thanh “gánh nguyên film”; không chọn NEG chỉ vì câu mở đầu có lời chê.

Mọi gợi ý là đề nghị rà soát, không phải nhãn người đã xác nhận. Không sửa workbook, không train, không đưa nhãn người lên Git.
