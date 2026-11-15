# Đánh giá sơ bộ corpus crawl Facebook V2

Ngày 15/11/2026. Audit dữ liệu, không phải đánh giá model hoặc sentiment Gold. Không gán nhãn tự động, không train, không sửa raw/cleaning/canonical/Gold.

## Tổng quan

- 12,795 comment ID; 89 bài có dữ liệu, 67 movie_id, 5 nguồn.
- ID trùng: 0. KEEP là đạt làm sạch kỹ thuật, chưa bảo đảm liên quan phim, hiểu độc lập hoặc đủ điều kiện train.
- movie_id là metadata người dùng nhập, có cả phim dài tập/anime và tên chưa chuẩn hóa; không coi số mã là số tác phẩm đã xác minh.

| clean_status | Số câu | Tỷ lệ |
|---|---:|---:|
| KEEP | 12,066 | 94.30% |
| REVIEW | 148 | 1.16% |
| EXCLUDE | 581 | 4.54% |

## Nguồn và mức tập trung

| Nguồn | Số câu | Tỷ lệ |
|---|---:|---:|
| Maybe You Never Watched This Movie | 9,346 | 73.04% |
| Chê Phim Review | 3,125 | 24.42% |
| XEM PHIM & BÌNH PHIM | 228 | 1.78% |
| Cuồng Phim | 52 | 0.41% |
| KhenPhim | 44 | 0.34% |

Top 2 nguồn chiếm 97.47%; top 5 movie_id chiếm 27.02%; top 5 bài chiếm 17.98%.

| movie_id (top 10) | Số câu |
|---|---:|
| mai | 1,601 |
| jujutsu_kaisen | 500 |
| nhu_y_truyen | 500 |
| nha_ba_nu | 449 |
| obsession | 407 |
| tam_cuu_ho_trai_tim | 400 |
| saint_oni_san | 398 |
| dao_pho_va_piano | 356 |
| dr_strange | 318 |
| ant_man_and_the_wasp_quantumania | 310 |

## Độ dài và tín hiệu văn bản

| Phạm vi | Trung vị ký tự | p90 ký tự | Dài nhất | Trung vị từ | p90 từ |
|---|---:|---:|---:|---:|---:|
| Toàn bộ | 57 | 248 | 5666 | 14 | 58 |
| KEEP | 62.0 | 256 | 5666 | 15.0 | 60 |

Số từ tách theo whitespace, không phải word segmentation tiếng Việt; p90 dùng nearest-rank. Đếm emoji/ký hiệu là proxy theo vùng Unicode, teencode/phủ định là dấu hiệu từ vựng, không phải nhãn POS/NEG.

| Chỉ báo | Toàn bộ | Trong KEEP |
|---|---:|---:|
| empty_clean | 563 (4.40%) | 0 (0.00%) |
| url_remaining | 3 (0.02%) | 0 (0.00%) |
| html_entity | 0 (0.00%) | 0 (0.00%) |
| not_nfc | 32 (0.25%) | 32 (0.27%) |
| replacement_character | 0 (0.00%) | 0 (0.00%) |
| control_character | 1 (0.01%) | 1 (0.01%) |
| underscore | 13 (0.10%) | 13 (0.11%) |
| emoji_symbol | 2,797 (21.86%) | 2,730 (22.63%) |
| emoticon | 2,524 (19.73%) | 2,459 (20.38%) |
| teencode | 2,762 (21.59%) | 2,761 (22.88%) |
| negation | 4,251 (33.22%) | 4,249 (35.21%) |
| short_2_words | 779 (6.09%) | 619 (5.13%) |
| very_long | 93 (0.73%) | 93 (0.77%) |
| with_media | 250 (1.95%) | 247 (2.05%) |
| with_removed_mentions | 7,383 (57.70%) | 6,702 (55.54%) |
| with_removed_urls | 10 (0.08%) | 9 (0.07%) |
| raw_clean_changed | 7,671 (59.95%) | 6,990 (57.93%) |
| keep_without_letters | 0 (0.00%) | 0 (0.00%) |

Control codepoints trong text_clean: {'U+0008': 1}. Không sửa hoặc loại dòng trong audit.
Metadata ghi nhận 7,507 mention và 22 URL/link đã loại. Đây là số do crawler ghi, không phải precision/recall xóa mention. Không đoán tên người từ chữ hoa để tự cắt text.

## Metadata và ngữ cảnh

| Trường | Thiếu |
|---|---:|
| comment_id | 0 (0.00%) |
| post_id | 0 (0.00%) |
| post_url | 0 (0.00%) |
| parent_comment_id | 6,029 (47.12%) |
| movie_id | 0 (0.00%) |
| source_name | 0 (0.00%) |
| source_type | 0 (0.00%) |
| collected_at | 0 (0.00%) |
| crawl_run_id | 0 (0.00%) |
| comment_created_at | 12,795 (100.00%) |
| reaction_count | 12,795 (100.00%) |

Comment/reply: {'reply': 6766, 'comment': 6029}. Trong 6,766 reply, 429 (6.34%) không tra được parent trong 4 export; 0 parent tìm thấy nhưng khác bài.
parent_comment_id rỗng ở comment gốc là hợp lệ; không dùng tỷ lệ thiếu parent trên toàn bộ làm tỷ lệ lỗi. Không suy thời điểm đăng từ collected_at, không điền reaction giả.
Guideline V3.1 đang được rà soát quy định text-only: không đưa parent/post vào đầu vào chỉ để cứu câu mơ hồ. Thiếu parent là chẩn đoán dữ liệu, không tự động EXCLUDE; câu không quyết định được từ chính text cần xử lý theo guideline đã chốt.

## Trùng văn bản và bảo vệ test

- Exact sau NFC + casefold + gộp whitespace: {'groups': 89, 'members': 261, 'excess': 172, 'short_groups': 83, 'cross_post_groups': 60}. Bỏ qua text trống khi đếm.
- Near duplicate trực tiếp: {'distinct_text_pairs': 6, 'records_involved': 10, 'cross_post_record_pairs': 2}. Trigram token Jaccard ≥0,9, độ dài normalized ≥40 ký tự; loại cặp exact khỏi chỉ số near.
- Không nối bắc cầu thành giant component. Câu ngắn giống nhau có thể là ý kiến độc lập; near là cờ cần kiểm tra, không phải bằng chứng sao chép và không tự xóa.
- Cờ so với test/reserved/holdout qua guard hiện có: {'EXACT_RESERVED_TEXT': 16}. Chỉ so fingerprint/metadata nguồn được bảo vệ, không đọc nhãn Gold hoặc chạy model trên Gold.
- Các cờ này chưa phải tập train được duyệt. Giữ post/ID và duplicate protection khi chia train/dev; toàn bộ corpus đã audit là nguồn phát triển, không tự coi một phần tách lại là independent Gold.

## Giới hạn thu thập

Tổng từ journal/report của 4 run: {'requested_posts': 108, 'posts_without_result': 0, 'raw_validation_errors': 0, 'dom_parse_observations': 2283, 'posts_success': 56, 'posts_failed': 0, 'posts_partial': 52, 'posts_blocked': 0}. DOM parse observations có thể lặp cùng một lỗi; không phải số comment duy nhất bị thiếu.
Thu thập bị giới hạn theo bài, số vòng và timeout; không phải lấy mẫu ngẫu nhiên từ Facebook. Success có thể là đạt cap hoặc hết DOM đang tải được, không chứng minh coverage toàn bài. Bài không đóng góp comment mới có thể liên quan dedup hoặc khả năng truy cập/DOM; không suy nguyên nhân chỉ từ số 0.

## Kết luận và việc tiếp theo

**READY_WITH_LIMITATIONS** để chuẩn bị gán nhãn/phát triển, không phải tuyên bố corpus đã sạch ngữ nghĩa hay sẵn sàng train có giám sát.
1. Giữ nguyên nguồn. Kiểm tra cờ control/URL/encoding nếu có trên bản làm việc riêng trước khi thay preprocessing; không tự sửa artifact đã khóa.
2. Chốt đúng byte guideline V3.1, rồi A/B gán pilot 200 độc lập; người dùng adjudicate. Đếm KEEP không thay thế nhãn sentiment.
3. Rà text-only cho câu ngắn/mơ hồ; không mặc định NEU hoặc bỏ toàn bộ reply. Lấy mẫu kiểm tra cả trường hợp không bị flag, không suy chất lượng từ độ dài.
4. Kiểm soát tập trung nguồn/phim, nhóm theo post và cặp duplicate khi thiết kế dev; không giả định đã cân bằng POS/NEG/NEU.
Audit relevance 107 câu trước là audit phụ trợ, chưa hoàn thành mẫu ngẫu nhiên và chỉ thuộc một phần nguồn: không suy rộng tỷ lệ liên quan của audit đó lên 12k câu này. Không có Macro-F1/Kappa sentiment V3.1 mới trong báo cáo.

## Tái lập và bảo toàn

`python scripts/sample_audit.py inventory` đọc đúng 4 export gốc, không cộng thêm CSV gộp (sẽ nhân đôi ID). Dữ liệu local/diagnostics không commit; báo cáo public không có text, tên người, ID comment/post hoặc URL nguồn cá nhân.

| Export | Dòng | SHA256 CSV |
|---|---:|---|
| data/imports/fb_54e6c18b6c514f9ab822354611ab3316/comments.csv | 2,521 | `2f108e3f5ecf83652e206ad13254c92e1ac30fa8737700e431621ab0fdff1c65` |
| data/imports/fb_541bedc5adb54db295e456ed1a5dc62c/comments.csv | 4,851 | `4ae7533a37de8f86c603ca481cd7a0c9a504fee54f362a1dce29405b352242bc` |
| data/imports/fb_cc583df7d16947a2aef7949550fa276d/comments.csv | 2,351 | `588955e2c46c09117106e618266a8848fd6c140358fc690583935ae4392215e6` |
| data/imports/fb_a767303a5ad8426d8fad5accb8a313cb/comments.csv | 3,072 | `8c779cf34cd86fefa0f0566db2b36d72b10e0c78c7d86faff9fee51f94798ce5` |
