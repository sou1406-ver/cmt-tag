# Phase 0 — audit local, 09/11/2026

## Bằng chứng

`../data_module1.csv`: 5.681.919 bytes, SHA-256
`4cfe4a00d7a95c46909755b3255e7bc504a7728f503f4b30a68abba7ff9b17b7`.
CSV UTF-8 đọc được bằng csv.DictReader: 29.688 dòng, cột id/comment/overall.
Không thiếu giá trị, không trùng ID; không trùng text chính xác hoặc sau
NFC/whitespace/casefold. Nhãn gốc: NEU 16.611, POS 6.794, NEG 6.283.
Độ dài ký tự min/median/p95/max: 2 / 78 / 455 / 6.729. Độ dài ngắn không tự
chứng minh dữ liệu rác; chưa chạy lọc hoặc sửa nội dung. Chưa tính near-duplicate
toàn corpus và chưa khẳng định sạch paraphrase/trùng nguồn.

Không có post/movie/collection metadata, annotator/model/guideline/license.
ID số chỉ là ID file, không được coi là Facebook comment_id.
Xem mẫu ngẫu nhiên seed 42 tại local cho thấy nội dung thảo luận phim cùng
người làm phim và ngoài lề; không chứng minh cả corpus thuộc miền phim hoặc
nhãn tương thích guideline. Không đưa text thật hoặc thông tin cá nhân lên Git.
Mẫu có token nối bằng dấu gạch dưới và emoji chuyển thành tên tiếng Anh; có dấu
hiệu đã xử lý văn bản. Không gọi cột comment là nguyên văn Facebook đã xác minh.

Người dùng xác nhận file nhận từ bạn; chưa biết nguồn ban đầu, cách tạo nhãn,
guideline hoặc quyền gửi API. Không có bằng chứng về contamination pretrain/
fine-tune/benchmark; thiếu nguồn khiến không thể xác nhận hay loại trừ overlap.
Không truy vấn comment thật lên web/API để tìm nguồn. Cần đối chiếu source và
benchmark bằng quyền truy cập phù hợp sau khi người dùng xác minh.

Guideline local được tìm thấy ở file tên `MOVIE_SENTIMENT_LABELING_GUIDELINE_V2_1 (1).md`,
nhưng tiêu đề nội dung khai báo **V2.0**. Dùng toàn văn byte nguyên vẹn với checksum,
không tự nâng version theo tên file. Không tìm thấy pilot người gán sẵn trong repo.

## Quyết định trước triển khai C/D

**Nhánh B, phát triển trên fixture**: overall là nhãn chưa xác minh, không phải
gold và cũng chưa đủ bằng chứng để coi là silver từ LLM. Giữ nguyên file/nhãn,
không nhập làm corpus train, không gửi bất kỳ comment thật nào ra dịch vụ ngoài.
Xây workflow gold/silver, blind pilot/Kappa/adjudication và release; Phase D chạy
fixture tổng hợp riêng. Không công bố metric fixture như kết quả nghiên cứu.
Nguồn thật chỉ được sử dụng sau khi provenance, quyền sử dụng, miền và định nghĩa
nhãn được xác minh. Chưa có gold dev 200/test 300 hoặc Kappa thật.
