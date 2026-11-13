# Dữ liệu và kết quả local

Mở `../cmt-tag.code-workspace` trong VS Code để thấy code và các thư mục đang dùng
thành những mục riêng. Những đường dẫn bên dưới giữ nguyên; không chuyển active pointer.

| Mục đang dùng | Đường dẫn | Trạng thái |
|---|---|---|
| Dataset sau lọc | [comments.csv](canonical/versions/filtered_20261112_final/comments.csv) | 25.810 câu, 425 nhãn sentiment người; bất biến |
| Candidate quality | [comments.csv](canonical/versions/filtered_20261113_quality_v1/comments.csv) | Giữ mọi record + flags; 315 tag-only EXCLUDE, 154 REVIEW; chưa approved |
| Pilot 600 để tải web | [pilot_600.json](ai_labeling/pilot_20261113/web_upload/pilot_600.json) | Một file mù, cùng prompt cho 3 AI |
| Kết quả 3 AI | [REPORT.md](ai_labeling/pilot_20261113/REPORT.md) | Đã nhập đủ 1.800 quyết định; 184 silver candidate chưa approved |
| Người duyệt tiếp | [review_blind.xlsx](ai_labeling/pilot_20261113/review_blind.xlsx) | 100 câu: 50 đồng thuận + 50 bất đồng, ẩn nhãn AI |
| Bạn gán phần còn lại | [review_friend_350.xlsx](ai_labeling/pilot_20261113/friend_share/review_friend_350.xlsx) | 350 câu riêng, không trùng 100 câu review; có guideline cạnh file |
| Preprocessing CV | [REPORT.md](preprocessing_experiments/REPORT.md) | Kết quả development, không phải independent test |
| Quality filter | [REPORT.md](quality_filter_review/REPORT.md) | Ví dụ raw/DOM/view và kiểm tra rule local |
| Gold đã evaluate | [thư mục](gold/) | Khóa/receipt/results giữ nguyên; không dùng lại để tune |

Pool pilot riêng sau mở post development: 12.308 KEEP (5.372 Facebook, 6.936 legacy).
Điều này không thay pool eligible hoặc trạng thái approved của các version cũ.
150 câu calibration có nhãn người không vào silver. 3/3 agreement không phải accuracy.

Các thư mục phase cũ, raw, nhãn, model, split và canonical version được manifest pin
vẫn ở nguyên vị trí để tái lập. Chỉ dọn cache/junction và bản sao verification có
payload trùng SHA với bản giữ lại, không có tham chiếu bên ngoài. Bản ghi cleanup
local: `local_cleanup_20261113.json`. Không coi các phase cũ là bước phải chạy lại.

Không commit comment, prediction hoặc workbook mới. Clone repo không tự có toàn bộ
các file local này. Quy trình chính: [README](../README.md).
