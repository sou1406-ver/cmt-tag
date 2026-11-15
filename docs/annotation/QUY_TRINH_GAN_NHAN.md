# Quy trình gán nhãn V2 (chốt 15/11/2026)

Áp dụng thay cho kế hoạch 5 batch người gán. Không giao thêm batch cho annotator A/B. Không tự thêm bước, không đổi thứ tự.

## Cố định trước khi bắt đầu

- Guideline: `docs/guidelines/SENTIMENT_GUIDELINE.md`, SHA `2e4ba18c3c12c97b3bf4c33f39e11a87a684c71af1459e671860aec046d9568e`. Mỗi tập chép snapshot như hiện có.
- Prompt AI: `docs/annotation/AI_LABEL_PROMPT.md` (người dùng cung cấp), pin SHA vào manifest. Đổi prompt giữa chừng thì tập đang gán phải gán lại toàn bộ.
- 3 AI chạy trên web do người dùng tự thao tác: ChatGPT, Claude, Gemini. Không gọi API.
- Không commit comment text, workbook, nhãn. Không ghi đè output cũ; mỗi bước một thư mục mới.

## Bốn tập

| Tập | Nguồn | Cỡ | Dùng để |
|---|---|---|---|
| E — ví dụ | Pilot đã đối soát | ~50 | Đưa vào prompt AI |
| C — hiệu chuẩn | Phần pilot còn lại | ~150 | Đo AI so với nhãn người; không đưa vào prompt |
| T — test | `annotation_round_01`, chọn theo post | ~200 | Chấm mô hình; người dùng duyệt 100% |
| U — train | Phần còn lại của `annotation_round_01` | ~800 | AI gán, người dùng duyệt một phần |

## Các bước

### 1. Tách tập (Codex)

- E: người dùng gửi danh sách `comment_id`; Codex chỉ ghi lại, không tự chọn. C = pilot trừ E.
- T và U chia lại 1.000 ID đã chọn của `annotation_round_01` **theo post**, không theo câu: chọn ngẫu nhiên (seed cố định) từng post, phân tầng theo nguồn, đưa vào T đến khi đạt ~200 câu; post còn lại vào U. Không post nào có mặt ở cả T và U. Báo phân bố nguồn/post/movie của T và U.
- Batch 1 cũ của `annotation_round_01` bỏ, không giao. Ghi lại trong README là đã bỏ.

### 2. Người dùng gán mù 50 câu của T (trước khi AI thấy T)

- Codex xuất workbook 50 câu ngẫu nhiên của T, chỉ `comment_id`, `text_clean`, cột nhãn/note trống.
- Người dùng gán theo guideline, không xem AI. Codex import, khóa hash.

### 3. Xuất file cho AI (Codex)

- Mỗi tập C, T, U tách thành các chunk 100 câu, xáo thứ tự, chỉ 2 cột `comment_id,text_clean`. Đặt tên `<tập>_chunk_<nn>.csv`.
- Không kèm nhãn, nguồn, post, movie.

### 4. AI gán (người dùng)

- Mỗi chunk dán vào một cuộc chat mới với prompt cố định, cho cả 3 AI.
- Lưu kết quả thành `ai_<chatgpt|claude|gemini>_<tập>_chunk_<nn>.csv`, cột `comment_id,label,note`.
- Thứ tự: C trước, rồi T, rồi U.

### 5. Import và kiểm tra (Codex)

- Mỗi file AI: đủ ID của chunk, không thừa, không trùng, nhãn thuộc POS/NEG/NEU/REVIEW/EXCLUDE. Sai thì báo chunk nào để người dùng chạy lại chunk đó, không tự sửa.
- Ghi model, ngày, SHA prompt, SHA file.

### 6. Hiệu chuẩn trên C (Codex)

- Mỗi AI so với nhãn người: agreement, Kappa 5 quyết định, Kappa 3 nhãn, ma trận 5×5.
- Đồng thuận 3/3 của AI so với nhãn người: tỷ lệ phủ và độ chính xác.
- Chỉ báo cáo, không tự dừng hay đổi prompt. Người dùng quyết định có đi tiếp U không.

### 7. Chốt T (người dùng duyệt 100%)

- Codex xuất bảng 200 câu: nhãn 3 AI, nhãn mù của người dùng (50 câu), cột `final_label`, `note` trống.
- Người dùng chốt tất cả 200. Không câu nào tự lấy nhãn AI.
- Báo: agreement giữa nhãn mù và nhãn cuối trên 50 câu; agreement giữa AI 3/3 và nhãn cuối.

### 8. Chốt U (người dùng duyệt một phần)

- AI 3/3 đồng thuận → `label_source=AI_3OF3`.
- Không đồng thuận → vào bảng đối soát, người dùng chốt → `USER_ADJ`.
- Lấy ngẫu nhiên 10% câu 3/3 (seed cố định) vào bảng đối soát → `USER_AUDIT`; báo số câu bị sửa.
- Câu người dùng để trống → `PENDING`, không vào train.

### 9. Dataset cuối (Codex)

- Train: C + E (nhãn người pilot) + U (POS/NEG/NEU đã chốt). Test: T.
- REVIEW/EXCLUDE không vào train hay test.
- Một file nhãn dạng dài: `comment_id, label, label_source, set, guideline_sha256, prompt_sha256`.
- Kiểm tra cuối: không ID/post/exact/near duplicate nào của T xuất hiện trong train; không câu nào của T từng làm ví dụ trong prompt; không đụng Gold V1.
