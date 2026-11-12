# Bổ sung phim và cộng đồng — 10/11/2026

Đợt tiếp theo dùng nguyên crawler đã vá `accountLink()` ở commit dcb97a8,
không sửa thêm mã nguồn, guideline, split hoặc artifact Phase B. Một run mới
`fb_3246b4f0f02a459e972fe5f44b441264`, raw giữ local; xuất 143 dòng text mới,
không giao ID với 4.436 dòng đã chia sẻ trước.

| Phim / bài | Nhóm | Bình luận Facebook hiển thị | Raw thu được | Text xuất | Thời gian cào |
|---|---|---:|---:|---:|---:|
| [Interstellar](https://www.facebook.com/groups/551234962149786/posts/1529586850981254) | Maybe You Never Watched This Movie | 194 | 15 | 15 | 26 giây |
| [The Dark Knight](https://www.facebook.com/groups/551234962149786/posts/1782122902394313) | Maybe You Never Watched This Movie | 163 | 91 | 87 | 29 giây |
| [Nhà Bà Nữ](https://www.facebook.com/groups/1489850877861839/posts/2325658017614450) | Chê Phim Review | 232 | 41 | 41 | 26 giây |

Hai nhóm đã xác minh công khai; giao diện hiển thị lần lượt khoảng 1,6 triệu
và 256,7K thành viên. Nhóm Maybe có alias numeric `551234962149786`, vẫn ghi
chung `source_group=youneverwatchedthismovie` với các run trước. Nhóm Chê Phim
Review ghi ID thật `1489850877861839`, tên dễ đọc nằm trong manifest nguồn.

Bài Interstellar bàn trải nghiệm xem lại; The Dark Knight phân tích nhân vật,
xung đột và khuyến nghị xem; Nhà Bà Nữ là review cụ thể về quay phim, diễn xuất,
kịch bản và nhạc. Không chọn bài game Joker, thanh lý sách, tin ngoài lề hoặc
fanpage chỉ vì có nhiều bình luận. Không gán sentiment từ thái độ bài gốc hay
tên nhóm. Các bài được chọn trong phạm vi đã khảo sát, không phải bảng xếp hạng
cao nhất toàn Facebook/nhóm.

147 raw observation có ID duy nhất, 0 lỗi schema, bỏ 120 node mention. Bốn
dòng rỗng sau xử lý mention/emoji không vào CSV; vẫn giữ raw. Bản xuất có 27
comment gốc và 116 reply. Text, source/post/movie metadata đã đối chiếu với raw;
importer đọc đủ 143 dòng; toàn bộ 2.736 ô Excel khớp CSV, ID lưu dạng text,
không sinh công thức từ comment; đã xem render.

Hai bài partial vì có quan sát DOM không parse được, một bài kết thúc ở
`visible_dom_exhausted`. Có 23 quan sát parse lỗi, có thể lặp qua nhiều vòng;
không suy ra 23 comment mất. Đã kiểm tra filter Tất cả bình luận và cuộn scope,
nhưng số truy cập được vẫn thấp hơn counter Facebook. Chưa có bằng chứng đủ
để sửa thêm pagination/selector; không suy đoán nguyên nhân hoặc cào đủ.

Thời gian trong bảng đo monotonic quanh engine, không gồm tìm/chọn nguồn,
chẩn đoán DOM hoặc xuất file. Không tối ưu tốc độ hoặc thay kiến trúc ở đợt này.

[Dữ liệu CSV/Excel và manifest](../../data/imports/facebook_diverse_sources_20261110)
có cùng 19 cột như đợt bulk. Chỉ bỏ link mention nhận dạng được trong body;
giữ nguyên tên dạng text mơ hồ, phủ định, emoji và xuống dòng. Không thu cột
tên/ID tác giả; không gọi là ẩn danh hoàn toàn. Không tạo nhãn hoặc gọi API LLM.

Cộng hai đợt sau bản vá là 2.420 dòng text mới. Chất lượng POS/NEG/NEU/usable
vẫn chờ [pilot người gán 70 fanpage + 130 group](../../data/tasks/source_quality_pilot_20261110/README.md),
không dùng số tương tác hoặc độ dài làm bằng chứng gold hay hiệu năng mô hình.
