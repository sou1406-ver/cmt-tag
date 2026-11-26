# Dữ liệu V2 và đầu vào thực nghiệm

| Thư mục | Nội dung |
| --- | --- |
| [01 · T2 và chờ gán](01_T2_va_cho_gan/) | 652 quyết định người gán, tập chấm 613 câu và 18 lô cho 1.731 câu chờ. |
| [02 · Dữ liệu và nhãn](02_Du_lieu_va_nhan/) | [Workbook chính](02_Du_lieu_va_nhan/01_Crawl_va_nguon_goc/Cmt_V2_ban_chuan.xlsx), dữ liệu crawl, nhãn nguồn và snapshot kỹ thuật. |
| [03 · Đầu vào chính thức](03_Dau_vao_chinh_thuc/) | Train 4.945 câu, T2 613 câu, cấu hình và SHA-256. Chưa chạy chấm. |

[Sheet nhập link Facebook và mã phim](../test_posts.xlsx) dùng cho đợt bổ sung. Lượt crawl V2 dùng danh sách 114 link ở `data/posts_v2.csv`. Các CSV chia đợt cũ có cùng link, mã phim và nguồn. Chúng chỉ khác giới hạn số bình luận ở một số link.

[Hướng dẫn crawl Python](../docs/CRAWLER.md) · [Chuẩn hóa Excel hoặc một câu](../scripts/chuan_hoa_binh_luan_v2.py) · [Nối lại dữ liệu crawl và nhãn](../scripts/prepare_v2_normalized.py) · [Đóng băng đầu vào chính thức](../scripts/freeze_v2_official.py)

Kết quả các lượt thử C, E+C, learning curve, ablation và thử trên 424 câu nằm trong [báo cáo BTL](../docs/BAO_CAO_BTL.md) và [báo cáo gán nhãn](../docs/annotation/BAO_CAO_THUC_NGHIEM_V2_C_3_SEED.md). `gold` và `phase_g/blind_test` giữ các tệp kiểm tra rò rỉ do crawler và code dữ liệu sử dụng. Đã đối chiếu SHA của danh sách 31 bài được bảo vệ sau khi rút gọn hồ sơ. Bình luận, nhãn và manifest chứa dữ liệu cục bộ nằm ngoài Git.
