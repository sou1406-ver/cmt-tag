# Đợt bổ sung đa dạng nguồn — 10/11/2026

Đã xuất **252 comment/phản hồi có ID mới**, từ **9 bài, 8 phim, 3 group công khai**.
Chưa đạt mục tiêu 20–30 bài. Không thêm bài lệch phạm vi để đủ số lượng.
Đây là dữ liệu chưa gán nhãn, không phải gold hoặc tập đánh giá độc lập.

## Chọn nguồn và kiểm mẫu

Đã xem 43 thẻ kết quả tìm kiếm trong Chê Phim Review, Maybe You Never Watched
This Movie, Xem Phim & Bình Phim và Khen Phim. Đây không phải 43 bài độc lập
đã xác minh: kết quả tìm kiếm có thể nhắc phim trong comment, nói về phim khác
hoặc chỉ là tin tức, danh sách phim, chương trình truyền hình.

Xác minh URL, đối tượng phim và nội dung 12 bài để chạy preview. Tại lúc kiểm tra,
các nhóm có trạng thái công khai; các nhóm được chọn crawl sâu là Chê Phim Review
(256,7K thành viên), Maybe You Never Watched This Movie (1,6 triệu), Xem Phim &
Bình Phim (16,5K). Số thành viên chỉ mô tả cộng đồng, không chứng minh chất lượng.
Không tham gia nhóm riêng tư, không tương tác với bài hoặc tài khoản.

Preview dùng đúng `crawl-batch`, giới hạn 40 bản ghi/bài, 75 giây/bài, tối đa
100 vòng tải. Đọc tối đa 30 trích đoạn comment đã bỏ node mention, lần lượt qua
các nhóm thread quan sát được trong preview. Đây là screening định tính của
agent, **không phải nhãn người độc lập, nhãn sentiment, hoặc ước lượng tỷ lệ usable**.
Mỗi bài được nhận crawl sâu có 30 mẫu từ nhiều thread; một parent ngoài preview
ở bài Avatar 2 không chứng minh được toàn bộ cây hội thoại.

Crawler lấy theo thứ tự DOM sau thao tác chọn bộ lọc comment hiện có. Việc rải
thread chỉ áp dụng lúc **chọn mẫu để đọc**, không thay đổi cách crawler thu thập.
Không lấy mẫu ngẫu nhiên hoặc cam kết các thread có xác suất thu thập bằng nhau.

Ba bài chưa crawl sâu:

- Quật mộ trùng ma: 30 mẫu từ 10 nhóm thread; nhiều trao đổi về ngoại hình/gu
  diễn viên và tranh cãi cá nhân. Giữ preview, không ưu tiên đợt này.
- Đêm tối rực rỡ: chỉ thu được 16 comment văn bản không rỗng, chưa đủ mức kiểm
  mẫu 20–30. Giữ preview và chờ kiểm thêm.
- Một bài Resident Evil: nhiều công kích người viết và tranh luận game; ưu tiên
  bài review Resident Evil còn lại. Không loại vì bài phê bình hoặc ý kiến chê.

[Danh sách 12 nguồn và quyết định screening](../data/imports/facebook_diversity_batch_20261110/source_list.csv)
ghi URL, số bình luận hiển thị, số mẫu/thread, lý do giữ hoặc hoãn, kết quả và
thời gian từng bài. Một bài Avatar 2 hiển thị 339 bình luận, vượt khoảng ưu tiên
50–300 nhưng phù hợp nội dung; vẫn áp dụng giới hạn thu thập như các bài khác.

## Kết quả crawl sâu

| Phim | Post ID | Raw | Xuất | Giây | Status / reason |
|---|---|---:|---:|---:|---|
| Avatar 2 | 2297290933784492 | 26 | 26 | 18,829 | success / visible_dom_exhausted |
| Avatar 2 | 2296687523844833 | 55 | 55 | 20,000 | success / visible_dom_exhausted |
| Người vợ cuối cùng | 1426423294630944 | 31 | 30 | 19,625 | success / visible_dom_exhausted |
| Joker | 567021170702186 | 20 | 20 | 21,093 | success / visible_dom_exhausted |
| Jojo Rabbit | 682094415861527 | 27 | 27 | 18,797 | success / visible_dom_exhausted |
| Lật mặt 8 | 2942599919253587 | 36 | 35 | 19,235 | success / visible_dom_exhausted |
| Lật mặt 6 | 2399719946874923 | 20 | 20 | 18,891 | success / visible_dom_exhausted |
| Parasite | 1469878066952133 | 21 | 19 | 18,734 | success / visible_dom_exhausted |
| Resident Evil (2026) | 3457104084469832 | 21 | 20 | 19,875 | success / visible_dom_exhausted |

Crawl sâu dùng crawler Selenium hiện có, tối đa **150 comment/bài**, 150 vòng,
150 giây, 20 thao tác mở rộng/vòng, idle 5 vòng, settle 2 giây, không retry.
Không sửa kiến trúc hoặc mã crawler. Timing wrapper local chỉ gọi collector
hiện có và đo thời gian thực thi từng bài, bao gồm điều hướng/chờ/mở rộng.
Tổng collector preview 90,563 giây; crawl sâu 175,079 giây. Các số này không
bao gồm thời gian tìm nguồn, đọc kiểm mẫu và tạo/kiểm tra bản xuất.

**Success không có nghĩa cào đủ toàn bộ Facebook.** Cả 9 bài kết thúc khi DOM
quan sát được hết tiến triển; một số bài lượt sâu có ít bản ghi hơn preview.
Đây là hạn chế độ phủ thực tế, không khẳng định đã lấy hết số comment hiển thị.
Không đổi trạng thái journal để che hạn chế đó. Không đạt 150 bản ghi/bài không
có nghĩa bài không còn comment.

- Raw sâu: 257; xuất: 252 (86 comment gốc, 166 reply).
- 5 bản ghi không có text sau bỏ mention: **1,95% raw**, giữ nguyên trong journal.
- Lỗi validation JSONL: 0; quan sát lỗi parse DOM: 0. Không suy ra DOM đã phủ hết bài.
- Trùng comment ID trong raw: 0. Giao ID với toàn bộ baseline trước đợt này: 0.
- Dư lượng trùng nguyên văn trong 252 text xuất: 0; không lọc gần trùng theo text.
- Loại 150 node mention tài khoản; tên chỉ còn ở text thường có thể vẫn tồn tại.

Preview run `fb_bf023e6cb06045909230d11d61902ff4` giữ local. Bản xuất chỉ lấy
deep run `fb_78eae52277ee4110be0242e51afe59e4`, **không merge preview hoặc bản cũ**.
Những comment chỉ có trong preview vẫn nằm nguyên trong journal preview.

## Chất lượng sơ bộ và giới hạn sử dụng

Avatar 2, Joker, Người vợ cuối cùng và Parasite có thảo luận cụ thể về kịch bản,
diễn xuất, bố cục hình ảnh, nhịp kể và trải nghiệm xem. Các nguồn cũng có ý kiến
trái chiều, so sánh phim và cảm xúc cần phân biệt với đánh giá tác phẩm.

Jojo Rabbit còn nhiều nhánh Oscar/phim khác; Lật mặt 6/8 có công kích người
review, doanh thu/suất chiếu; Resident Evil có trao đổi về game/chuyển thể. Vì
vậy không coi toàn bộ 252 dòng là dữ liệu sentiment dùng trực tiếp. `movie_id`
chỉ là phim của bài nguồn, không chứng minh mọi comment nhắm đến phim đó.
Cần gán nhãn người để biết tỷ lệ liên quan, POS/NEG/NEU và trường hợp REVIEW.
Không dùng kết quả screening này làm ground truth hoặc kết luận group tốt hơn
fanpage. Không train model trong đợt này.

## Provenance và kiểm tra

[Thư mục dữ liệu](../data/imports/facebook_diversity_batch_20261110/) có CSV,
Excel đã wrap/filter/freeze, `import_config.json`, `export_manifest.json` và
`source_list.csv`. Manifest ghi checksum, giới hạn, loại trừ và các chỉ số theo bài.
Config dùng đường dẫn từ thư mục gốc repo và map trường `text_raw` sang `text`.

Giữ comment/post/parent ID, URL bài, mã phim, nguồn, run và thời điểm thu thập.
Không thêm tên hoặc ID tác giả. Thiếu thời điểm tạo comment thì để trống,
không thay bằng thời điểm thu thập. Giữ emoji, phủ định và xuống dòng, dùng
`dom_text_v2`; không đoán tên bằng chữ hoa. Dữ liệu chưa được ẩn danh hoàn toàn.

Chống trùng theo snapshot **4.841 comment ID từ toàn bộ 17 raw run có trước đợt**,
bao gồm cả run local chưa chia sẻ. Checksum 17 raw cũ được đối chiếu giữ nguyên.
Raw, profile và dữ liệu pilot không đưa vào bản xuất. Hai file Excel pilot
format riêng theo yêu cầu người dùng; không sửa CSV, ID, text hoặc nhãn pilot.

Đã kiểm schema/import bằng hàm importer hiện có, tất cả **4.807 ô** của workbook
so với CSV, ID dạng text, không có comment bị biến thành công thức, checksum,
provenance và giao ID. Không chạy prepare/split, release, gán nhãn hoặc training.
Không sửa source pipeline hoặc artifact Phase B. 121 test hiện có đã pass ở
commit sửa mention trước đó; đợt dữ liệu này dùng các kiểm tra artifact nêu trên.
