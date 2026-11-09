# Pilot bình luận nhóm phim — 10/11/2026

Thu được **504 bình luận/phản hồi mới**, từ 7 bài trong hai nhóm công khai
`binhphim` và `youneverwatchedthismovie`. Tất cả thuộc một run
`fb_cfe87db5d35f41088e494b585bfe97ec`, không ghép các run cũ.

| Phim | movie_id | Số dòng |
|---|---|---:|
| Ròm | rom | 19 |
| Mưa Đỏ | mua_do | 24 |
| Mai | mai | 300 |
| Quỷ Nhập Tràng 2 | quy_nhap_trang_2 | 95 |
| Đào, phở và piano | dao_pho_va_piano | 66 |

Dữ liệu gồm 177 comment gốc và 327 reply. `binhphim` đóng góp 19 dòng,
`youneverwatchedthismovie` đóng góp 485 dòng. Chưa có nhãn sentiment hoặc nhãn
liên quan do người xác nhận; chưa đóng băng split đánh giá và chưa huấn luyện
trên đợt này.

## Chọn nguồn và độ bao phủ

Đọc nội dung bài gốc để xác nhận phim và nội dung review/thảo luận; bỏ bài
quảng cáo poster, minigame, truyện kể và bài không xác định được phim mục tiêu.
Các bài đầu được chọn theo nội dung. Sau góp ý của người dùng, hai bài cuối
ưu tiên số bình luận hiển thị trong các ứng viên đã khảo sát. Giao diện nhóm
đã xem không cung cấp bảng xếp hạng toàn bộ bài; không khẳng định đây là các
bài tương tác cao nhất nhóm.

Hai bài Đào, phở và piano được chọn theo tiêu chí tương tác:

| Bài | Bình luận Facebook hiển thị | Chia sẻ hiển thị | Dòng thu được |
|---|---:|---:|---:|
| [Review Hà Nội chất chơi](https://www.facebook.com/groups/youneverwatchedthismovie/posts/1488365451770061) | 1.461 | 977 | 38 |
| [Phản biện những lời chê](https://www.facebook.com/groups/youneverwatchedthismovie/posts/1490824468190826) | 198 | 147 | 28 |

Các số tương tác được ghi nhận lúc thu thập, có thể thay đổi. Số Facebook
hiển thị không đồng nghĩa với số bình luận truy cập được qua DOM. Bốn bài kết
thúc `visible_dom_exhausted`; hai bài Mai dừng ở giới hạn 150 dòng/bài; bài
Quỷ Nhập Tràng 2 còn `unparsed_comments`. Có 20 quan sát DOM chưa parse được,
không phải 20 comment đã xác định là mất. Chưa xác minh độ bao phủ toàn bộ.

Đây là mẫu thuận tiện có chủ đích: lệch mạnh về một nhóm và phim Mai. Không
dùng làm ước lượng phân phối sentiment thực tế hoặc tập test đại diện. Quan
điểm của bài nguồn không được dùng để suy ra nhãn các comment. Bước tiếp theo
là pilot gán nhãn người theo guideline hiện có trước khi kết luận chất lượng.

## File và cách xử lý

[Thư mục dữ liệu](../data/imports/facebook_group_pilot_20261110/) có CSV, Excel,
`import_config.json` và `export_manifest.json`. Manifest lưu đủ 7 URL, mã phim,
nhóm, lý do chọn, trạng thái từng bài, giới hạn và checksum. CSV/Excel có
`source`, `movie_id`, `post_id`, `post_url`, `source_group` và ID bình luận.

Dùng nguyên crawler Selenium, Store và `run_posts` hiện có. Không thay mã
crawler, annotation, baseline, data pipeline hoặc artifact Phase B. Chỉ dùng
`dom_text_v2` sẵn có: bỏ node tag tài khoản nhận dạng được; giữ nguyên tên dạng
text thường không phân biệt chắc chắn với nội dung, emoji, phủ định và xuống
dòng. Không thêm `author_name`/`author_id`, không đoán tên bằng chữ hoa hoặc
tác giả comment cha, không gửi comment tới API LLM.

Raw journal, bản export audit đầy đủ và profile chỉ giữ local. Bản chia sẻ
chỉ có các trường phục vụ dữ liệu bình luận; text tự do vẫn có thể chứa tên
người chưa tách được. Không gọi bản này là dữ liệu đã ẩn danh hoàn toàn.

## Kiểm tra

- 504 dòng có ID duy nhất, không giao ID với hai bản chia sẻ trước (1.538 và 117 dòng).
- 504 dòng giữ nguyên `text_without_mentions` từ raw, đúng post/movie và đầy đủ metadata nguồn.
- 0 lỗi schema raw; importer Phase B đọc được đủ 504 dòng, không chạy lại split.
- Đối chiếu toàn bộ 9.595 ô Excel với CSV, không có công thức từ nội dung comment;
  ID dài lưu dạng text; đã xem bản render.
- Bộ test hiện có: `python -m unittest discover -s tests` — **119 test pass**.
