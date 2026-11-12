# Patch crawler riêng sau Phase D

Không mở rộng thu thập hoặc thay selector. Sửa ba lỗi đã xác minh:

- Browser từng tính sum trên toàn bộ store.rows ở mỗi observation và pending
  flush. Thay bằng Counter post_url O(1), tăng chỉ sau append thành công, dựng
  lại đúng từ raw khi resume; duplicate không tăng count.
- Raw fsync mỗi dòng giữ nguyên để bảo đảm durability comment đã ghi. Chi phí
  đó có thật nhưng batching raw làm tăng cửa sổ mất dữ liệu khi máy tắt. Chỉ
  batch checkpoint mỗi 25 comment; checkpoint là optimization, không là nguồn
  authoritative. Kết thúc bài/ngắt/finish vẫn checkpoint. Không tuyên bố số đo
  throughput chưa benchmark trên bài thật.
- Finish trước đây đánh complete cả khi partial/failed, khiến resume bị từ chối.
  Giờ chỉ complete nếu mọi bài yêu cầu latest status success; còn lại interrupted
  để resume. Blocked cũng giữ resumable, không tự vượt giới hạn truy cập. Run
  đã complete vẫn bất biến. Chạm max_comments/round budget có thể cần run mới
  với giới hạn mới vì config run vẫn bất biến, không sửa ngầm khi resume.

Regression tests: lag checkpoint nhưng raw fsynced vẫn khôi phục đủ rows/Counter,
duplicate không tăng Counter; partial/failed/blocked qua resume tới success,
raw không lặp ID. Điều chỉnh test complete cũ để thực sự có bài success.
Không chạy smoke test Facebook thật, không đọc profile hoặc cookie.

Kiểm chứng trước commit patch: **66 tests PASS, không skip** (64 trước patch +
2 regression tests), compileall và diff check sạch. Checksum file 29k vẫn
`4cfe4a00d7a95c46909755b3255e7bc504a7728f503f4b30a68abba7ff9b17b7`.
