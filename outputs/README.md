# Dữ liệu V2 và đầu vào thực nghiệm

| Thư mục | Nội dung |
| --- | --- |
| [01 · T2 và các lượt gán](01_T2_va_cho_gan/) | 652 quyết định người gán, tập chấm 613 câu và kết quả gán nhãn AI theo lượt. |
| [02 · Dữ liệu và nhãn](02_Du_lieu_va_nhan/) | [Workbook chính](02_Du_lieu_va_nhan/01_Crawl_va_nguon_goc/Cmt_V2_ban_chuan.xlsx), dữ liệu crawl, nhãn nguồn và snapshot kỹ thuật. |
| [03 · Đầu vào chính](03_Dau_vao_chinh_thuc/) | `normalize_v2` cho 4.945 câu train và 613 câu T2. |
| [04 · Đầu vào phụ](04_Dau_vao_phu/) | Cùng ID và nhãn với bản chính, giữ cách viết gốc sau làm sạch kỹ thuật. |
| [06 · Dữ liệu cuối V2](06_Du_lieu_cuoi_V2/) | 7.864 câu train từ nhãn AI đồng thuận 3/3 và nhãn E/C/U đã chốt, sau khi kiểm tra rò rỉ với T2. |
| [07 · Mô hình cuối V2](07_Mo_hinh_cuoi_V2/) | Bốn baseline cục bộ và biên nhận checkpoint PhoBERT, ViSoBERT trên Modal. |
| [08 · Đánh giá T2](08_Danh_gia_T2_V2_chi_tiet/) | Accuracy, Macro-Precision, Macro-Recall, Macro-F1 và 18 ma trận nhầm lẫn của sáu mô hình qua ba seed. |

Bộ train cuối dùng 9.772 câu đồng thuận trong 12.758 câu từng qua ba AI, cộng 957 câu E/C/U đã chốt. Sau khi loại 2.842 câu cùng bài với T2 và 23 câu trùng văn bản với T2, còn 3.261 NEG, 2.844 NEU và 1.759 POS. T2 giữ nguyên 613 câu để chấm.

[Sheet nhập link Facebook và mã phim](../test_posts.xlsx) dùng cho đợt bổ sung. Lượt crawl V2 dùng danh sách 114 link ở `data/posts_v2.csv`. Các CSV chia đợt cũ có cùng link, mã phim và nguồn. Chúng chỉ khác giới hạn số bình luận ở một số link.

[Hướng dẫn crawl Python](../docs/CRAWLER.md) · [Chuẩn hóa Excel hoặc một câu](../scripts/chuan_hoa_binh_luan_v2.py) · [Nối lại dữ liệu crawl và nhãn](../scripts/prepare_v2_normalized.py) · [Đóng băng đầu vào chính thức](../scripts/freeze_v2_official.py)

Các lượt gán dùng CSV đã qua `normalize_v2`. [Script xuất lô](../scripts/export_v2_annotation_batches.py) giữ ID gốc và xuất 1.726 câu có nội dung từ 1.731 câu trong hàng chờ ban đầu. Các dòng rỗng được ghi nhận trong manifest.

Kết quả các lượt thử C, E+C, learning curve, ablation và thử trên 424 câu nằm trong [báo cáo BTL](../docs/BAO_CAO_BTL.md) và [báo cáo gán nhãn](../docs/annotation/BAO_CAO_THUC_NGHIEM_V2_C_3_SEED.md). `gold` và `phase_g/blind_test` giữ các tệp kiểm tra rò rỉ do crawler và code dữ liệu sử dụng. Đã đối chiếu SHA của danh sách 31 bài được bảo vệ sau khi rút gọn hồ sơ. Bình luận, nhãn và manifest chứa dữ liệu cục bộ nằm ngoài Git.
