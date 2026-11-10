# Cào bài nhiều bình luận và sửa mention group — 10/11/2026

Đợt sau bản vá thu **2.929 observation có ID**, từ một run độc lập
`fb_1c5e839302294c23a80244ea4315320d`. Bản chia sẻ có **2.277 dòng text mới**,
đều thuộc hai bài Mai, không giao ID với 2.159 dòng đã chia sẻ trước.

## Kiểm tra lỗi trước khi sửa

DOM thật của bài nhóm cho thấy node link trong body reply có đường dẫn
`/groups/<group_id số>/user/<user_id số>/`. Đã kiểm tra nó nằm trong message,
không phải header tên tác giả. Không công bố URL danh tính trong dataset/report.

`accountLink()` thiếu đúng pattern này. Bản vá thêm một regex, giữ toàn bộ
guard domain/protocol/permalink và quy tắc chọn body. So sánh cùng DOM:
`text_raw` không đổi; tổng mention được bỏ từ 0 thành 1.401. Có 902 link dạng
này trong các reply đã xác minh ở snapshot chẩn đoán.

Hai regression fixture trước vá: ca group-user fail, ca link thường pass.
Sau vá, `python -m unittest discover -s tests`: **121 test pass**. Link ngoài
Facebook, link group/post, đường dẫn user chưa đủ/không phải số, permalink có
comment ID, tên dạng text, phủ định và emoji đều được bảo vệ. Không thêm
author_name/author_id, regex chữ hoa hoặc suy tên từ comment cha.

Raw trước bản vá được giữ local để đối chiếu; không sửa lịch sử raw. Đợt chia
sẻ này được cào mới sau khi reload extractor đã vá và test thành công.

## Chọn nhóm và bài

Giao diện tìm nhóm hiển thị Maybe You Never Watched This Movie khoảng 1,6 triệu
thành viên, Thần Kinh Phim khoảng 288 nghìn, Hội Mê Phim Chiếu Rạp khoảng 573
nghìn và Hội Những Người Mê Phim khoảng 293 nghìn. Chỉ chọn nguồn công khai.
Trong các kết quả đã kiểm tra ở những nhóm khác, chưa chọn được thêm bài phù
hợp có nhiều bình luận; không thu nội dung lệch chủ đề để tăng số lượng.

Các bài Mai được chọn có review/thảo luận cụ thể và số bình luận cao trong
những ứng viên đã xem. Không xác nhận đây là bài cao nhất toàn nhóm. Hai bài
Mưa Đỏ được cào lại để tạo pool pilot cùng phim với fanpage, không phải để tăng
số comment mới.

| Bài nguồn | Bình luận hiển thị lúc khảo sát | Raw thu được | Dòng text mới chia sẻ | Thời gian cào bài |
|---|---:|---:|---:|---:|
| [Topic Mưa Đỏ](https://www.facebook.com/groups/youneverwatchedthismovie/permalink/1909400102999925) | 118 | 117 | 0 | 32 giây |
| [Review Mưa Đỏ](https://www.facebook.com/groups/youneverwatchedthismovie/posts/1898631627410106) | 46 | 24 | 0 | 24 giây |
| [Phê bình Mai](https://www.facebook.com/groups/youneverwatchedthismovie/posts/1488490685090871) | 2.212 | 2.103 | 1.753 | 675 giây |
| [Review Mai](https://www.facebook.com/groups/youneverwatchedthismovie/posts/1486195815320358) | 767 | 685 | 524 | 112 giây |

Thời gian đo bằng monotonic quanh từng lần gọi `run_posts`, gồm điều hướng,
chờ, mở rộng, extract và cuộn; không gồm chọn nguồn, viết code/test hoặc xuất
file. Không dùng thời gian giữa hai lần nhập link làm thời gian xử lý crawler.
Chưa tối ưu Selenium/DOM hoặc thêm logging chi tiết từng bước; phần đó vẫn P1.

Lượt pilot trước đặt trần 150 dòng/bài, làm hai bài Mai dừng ở giới hạn. Lượt
này dùng chính Store/run_posts hiện có, trần 3.000/bài, timeout 900 giây/bài,
settle 2.000 ms và idle 8 vòng. Không viết crawler mới hoặc thay kiến trúc.

## Đối soát dữ liệu

- Raw có 2.929 dòng; 0 lỗi schema và 0 trùng source ID trong run.
- 432 dòng không rỗng có ID đã chia sẻ bị loại khỏi bản mới; 220 dòng rỗng sau
  chính sách tách mention/giữ emoji cũng bị loại. Hai lý do này không chồng nhau
  trong manifest. Raw vẫn giữ tất cả để audit.
- Bản mới: 2.277 dòng = 1.235 comment gốc + 1.042 reply; có `source`,
  `movie_id`, `post_id`, `post_url`, `source_group` và liên kết về run/raw.
- Toàn run bỏ 1.863 node mention; đây là số node, không phải số người duy nhất.
- Ba bài còn partial; một bài `visible_dom_exhausted`. Có 1.224 quan sát DOM
  chưa parse được, có thể lặp lại qua nhiều vòng; không suy ra số comment mất.
  Số Facebook hiển thị không chứng minh độ bao phủ, chưa gọi là cào đủ.
- Đối chiếu nguyên văn text đã tách mention và metadata với raw; importer đọc
  được 2.277 dòng. Đối chiếu toàn bộ 43.282 ô Excel với CSV, ID lưu dạng text,
  không có công thức phát sinh từ comment; đã xem render.

CSV/Excel trong [thư mục dữ liệu mới](../data/imports/facebook_high_activity_20261110/)
chỉ chứa text không rỗng và ID chưa chia sẻ. Manifest ghi source/giới hạn,
checksum raw/CSV/Excel và checksum JS extractor. Bản cũ giữ nguyên để audit;
không đoán sửa mention từ CSV cũ thiếu DOM. Tên dạng text không phân biệt chắc
với nội dung vẫn giữ, nên không gọi dữ liệu là ẩn danh hoàn toàn.

## Pilot người gán là P0

[Hai file pilot và hướng dẫn](../data/tasks/source_quality_pilot_20261110/README.md)
đã có 70 fanpage + 130 group, lấy ngẫu nhiên seed 42, cùng phim Mưa Đỏ, không
lọc theo nhãn luật hoặc độ dài. Pool group 141 dòng là snapshot mới sau bản vá;
raw pool đã bỏ 55 mention. File A/B cùng 200 ID/text nhưng thứ tự khác, không
hiện nguồn hoặc nhãn máy. Coordinator giữ mapping và provenance.

Nhãn vẫn trống. Chưa có Kappa hoặc tỷ lệ POS/NEG/NEU/usable từ người thật. Dùng
CLI import/agreement/adjudication Phase C hiện có, báo riêng mỗi nguồn; giữ
REVIEW/EXCLUDE là trạng thái. Không sửa src/annotation, src/baseline, src/data,
guideline, split hoặc artifact Phase B hiện có. Chuẩn bị pilot dùng output
riêng dưới outputs, không tạo model holdout hoặc release gold.

Đợt bulk mới chỉ bổ sung Mai từ một nhóm; không coi đây là corpus đại diện cho
sentiment phim nói chung hoặc dùng độ dài/số tương tác thay cho nhãn người.
