# CODEX HANDOFF — Phân loại sắc thái bình luận phim tiếng Việt

> Đây là đặc tả lịch sử. Điểm vào hiện tại: [pipeline](docs/CURRENT_PIPELINE.md),
> [quá trình phát triển](docs/PROJECT_EVOLUTION.md), [kết quả](docs/EXPERIMENT_RESULTS.md).
> Quy tắc bảo trì mới ưu tiên owner/module hiện có, shared utilities và subcommands.
> Trước khi tạo file, kiểm implementation/call sites/config/schema đã có; ghi rõ
> replacement, compatibility và cập nhật mục lục nếu trách nhiệm độc lập cần file mới.
> Không mặc định tạo phase mới, preprocessing version mới hoặc requirements/report mới.
> Cập nhật ba tài liệu tổng hợp tương ứng; frozen contracts/nhãn/raw không đổi.

**Trạng thái:** Đặc tả triển khai v1.0, ngày 07/11/2026  
**Mục tiêu:** Xây dựng pipeline ML gán nhãn bán tự động và huấn luyện mô hình phân loại `POS` / `NEG` / `NEU` cho **comment về phim nói chung**.  
**Ưu tiên:** Chất lượng dữ liệu, chống rò rỉ, thực nghiệm có thể tái lập; KHÔNG mở rộng sang lĩnh vực khác ở giai đoạn này.

## 0. Chỉ dẫn làm việc cho Codex

1. **Trước khi code**, kiểm tra repo hiện tại: `git status`, cây thư mục, README, dữ liệu, scripts crawl, notebook, dependencies, cấu hình và test. Tóm tắt ngắn những gì đã có, còn thiếu và kế hoạch chỉnh sửa. **Không giả định tên/path file; không ghi đè dữ liệu hay thành quả cũ.**
2. Nếu chưa có repo/dataset trong workspace, tạo scaffold tối thiểu + fixture giả lập để kiểm tra code, rồi chỉ rõ cần người dùng cung cấp file nào. **Không tự khẳng định đã train/evaluate trên 29k comment.**
3. Triển khai **từng phase nhỏ**, chạy test sau mỗi phase, lưu log/metrics/seed và báo file đã thay đổi. Không xây UI cầu kỳ trước khi pipeline dữ liệu và đánh giá đúng.
4. Chỉ tham khảo kiến trúc code của repo công khai `https://github.com/namPh06/Toxic_Detection_PTIT_Student_Comments`; **không sao chép nhãn/toxic model**, vì bài toán này là sentiment ba lớp, không phải toxic nhị phân.
5. Không tự thay phạm vi nghiên cứu, bộ nhãn hoặc tiêu chí đánh giá. Nếu quyết định kỹ thuật chưa được chốt, chọn phương án đơn giản, ghi rõ giả định, và để cấu hình thay được.

## 1. Bối cảnh và dữ liệu

- Nhóm đã thu thập khoảng **2–3k comment về phim Mưa Đỏ** (trong một số trao đổi có nhắc ~3.430 bản đã xử lý); cần **kiểm tra con số thực tế** trong file.
- Có khả năng nhận thêm khoảng **29k comment từ một người bạn**, nhưng **chưa xác nhận** đó là comment phim, có nhãn hay không, nguồn/metadata/điều kiện sử dụng thế nào. Kiểm tra trước khi hợp nhất.
- Một crawler cũ `fb_nhat_cmt.js` (nếu tồn tại) từng chỉ xuất `text`, làm mất `post_id/post_url/comment_id/time`. Không được tạo metadata giả cho dữ liệu cũ.
- Dữ liệu có thể lệch mạnh về POS, NEG hiếm; phải báo phân phối sau lọc, không ép cân bằng hay gán nhãn bằng từ khóa cho đủ số.
- Phạm vi chỉ là **comment về phim**; chưa xây hệ thống tổng quát cho mọi chủ đề.

## 2. Định nghĩa đầu ra và guideline gán nhãn

**Đơn vị:** Một comment hợp lệ → **một nhãn** dựa trên **sắc thái chủ đạo của các phần liên quan đến phim**. Giữ nguyên `text_raw`; không xóa vật lý các ý ngoài phim. Không xây mô hình aspect-based đa nhãn ở phiên bản này.

| Nhãn/trạng thái | Ý nghĩa |
|---|---|
| `POS` | Đánh giá/kỳ vọng về phim chủ đạo tích cực, kể cả khen nhẹ |
| `NEG` | Đánh giá/kỳ vọng về phim chủ đạo tiêu cực, kể cả chê nhẹ |
| `NEU` | Có nội dung thực sự về phim nhưng không biểu lộ đánh giá tích cực/tiêu cực rõ ràng |
| `REVIEW` | Trạng thái nội bộ: chưa xác định được nhãn tin cậy, **không phải lớp thứ tư** |
| `EXCLUDE` | Không liên quan đến phim, spam hoặc dữ liệu không hợp lệ, **không phải NEU** |

**Nguyên tắc ưu tiên để con người xử lý và làm cơ sở kiểm lỗi mô hình:**

1. Xác định phần có ý nghĩa liên quan đến phim. Có 5 ý, 4 ý ngoài phim và 1 ý khen phim → **vẫn POS**, không loại comment.
2. Hiểu nghĩa thực: phủ định, mỉa mai có bằng chứng, trích dẫn không phải quan điểm người viết; không đảo nhãn chỉ vì `:)))`.
3. Có **đánh giá tổng thể thật sự** về phim → ưu tiên hơn lời khen/chê một vài chi tiết; phân biệt kết luận với lời nhượng bộ.
4. Không có đánh giá tổng thể → xét **cường độ, trọng tâm, ngữ cảnh**, không đếm số ý POS/NEG hoặc mặc định vế sau từ “nhưng” quyết định.
5. Không đủ chứng cứ hoặc khen/chê ngang ngửa → `REVIEW`, **không nhét vào `NEU`**.

**Ví dụ kiểm thử nhãn:**

| Comment | Kỳ vọng |
|---|---|
| “Trời nóng, tắc đường, nhưng phim hay thật.” | `POS` |
| “Kịch bản tệ nhưng nhìn chung vẫn rất đáng xem.” | `POS` |
| “Hình ảnh ổn, diễn xuất khá nhưng nội dung quá tệ, xem xong thất vọng.” | `NEG` |
| “Phim hay quá, xem 15 phút ngủ luôn.” | `NEG` nếu thể hiện mỉa mai chê phim |
| “Phim hay quá :)))” | `POS` nếu không có bằng chứng mỉa mai khác |
| “Xem xong khóc hết nước mắt, phim cảm động thật.” | `POS` (buồn vì cốt truyện ≠ đánh giá phim tiêu cực) |
| “Phim chiếu lúc mấy giờ?” | `NEU` |
| “Đi xem phim thì bị mất điện thoại.” | `EXCLUDE` nếu không có nhận xét nào về phim |
| “Hình ảnh xuất sắc nhưng nội dung quá tệ.” | `REVIEW` nếu không có căn cứ xác định sắc thái chủ đạo |
| “Phần này cuốn hơn phần 1.” | `POS` |
| “Đỡ tệ hơn phần trước nhưng vẫn dở.” | `NEG` |

Mã REVIEW: `REV_MIXED`, `REV_SARCASM`, `REV_TARGET`, `REV_CONTEXT`, `REV_OTHER`. Có thể giữ `evidence`/`reason` khi khó; không bắt buộc nhập thủ công dài dòng cho mọi mẫu đơn giản. Lưu `guideline_version` cho mỗi quyết định kiểm chứng.

## 3. Chiến lược gán nhãn: mô hình làm phần lớn, người kiểm chứng có chọn lọc

**Không được hiểu “29k comment” là yêu cầu hai người gán tay 29k dòng.** Nhưng các baseline SVM/LR **không tự có nhãn**: phải có một tập hạt giống do người gán chuẩn hoặc nguồn nhãn phù hợp đã được xác thực.

1. **Dry-run:** Chọn 30–50 comment thật khó (mỉa mai, phủ định, nhiều ý trái chiều, trích dẫn, cảm xúc do phim tạo ra). Hai người áp dụng guideline, sửa các rule mơ hồ.
2. **Pilot:** 200 mẫu gồm khoảng 150 ngẫu nhiên + 50 cố ý khó. Gán độc lập để tính agreement, Cohen's Kappa, ma trận bất đồng và phân tích REVIEW. Báo kết quả hai nhóm riêng, không coi mẫu khó là ngẫu nhiên đại diện.
3. **Tập gold ban đầu:** Mục tiêu gán/xác nhận bằng người một lượng **vừa sức** (đề xuất khởi đầu ~500–1.000 comment tổng cộng, điều chỉnh theo phân phối và chất lượng). Phải có nhãn POS/NEG/NEU đủ đại diện, ưu tiên bổ sung lớp ít và mẫu khó. Không bắt buộc hai người gán mọi dòng; double annotation một phần và phân xử bất đồng.
4. **Giữ riêng gold validation/test** (gợi ý khoảng 400–600 mẫu nếu nguồn đáp ứng), nhãn do người xác nhận độc lập, không xem dự đoán; **khóa trước khi thử mô hình**. Có thể lấy một phần từ lượng gán tay nói trên; không cộng số lượng máy móc.
5. **Huấn luyện baseline trên gold train**, chạy dự đoán phần dữ liệu chưa có nhãn. Chọn mẫu để người kiểm tra bằng **active learning** (độ bất định, bất đồng giữa các mô hình, đa dạng từ vựng/nguồn, NEG/NEU nghi hiếm) và thêm mẫu kiểm tra ngẫu nhiên từ nhóm confidence cao.
6. **Pseudo-labeling** chỉ áp dụng với mẫu có độ tin cậy được **kiểm định thực nghiệm**; lưu nhãn máy riêng, không coi là gold. Có thể dùng pseudo-label train bổ sung với trọng số nhỏ hơn. So sánh gold-only với gold+pseudo trên **cùng gold test khóa sẵn**.
7. Lặp train → chọn mẫu → người sửa nhãn → train lại cho đến khi hiệu năng/khoảng bất đồng ổn định hoặc hết ngân sách gán nhãn. Ghi số mẫu người đã xem/sửa để báo **hiệu quả gán nhãn**.

**Cảnh báo:** Model đồng thuận hay confidence cao vẫn có thể sai, nhất là mỉa mai. `LinearSVC.decision_function` không phải xác suất; nếu cần ngưỡng xác suất phải calibrate trên train/validation phù hợp. Không lấy nhãn do mô hình tạo làm đáp án validation/test cuối.

## 4. Pipeline dữ liệu bắt buộc

1. **Import raw không phá dữ liệu:** CSV/JSON, UTF-8; map cột bằng cấu hình. Metadata tối thiểu nếu có: `source_dataset`, `comment_id`, `post_id`, `post_url`, `parent_comment_id`, `collected_at`, `text_raw`; ghi rõ thiếu/không biết, không tự điền giả. ID nội bộ ổn định, text hash, dấu nguồn và license/privacy nếu có.
2. **Quality & dedup:** lọc rỗng, spam, UI strings, văn bản chưa mở hết, duplicate chính xác và near-duplicate có kiểm tra. Không biến một câu ngắn hay có lỗi chính tả thành rác tự động. **Không sửa raw**; xuất bản processed riêng.
3. **Annotation & provenance:** lưu nhãn người, nhãn máy, model/version/scores, người xác nhận, timestamp, guideline version, `review_reason`, provenance. Không ghi đè nhãn người bằng nhãn máy.
4. **Split chống leakage:** chia theo `post_id`/nhóm bài, nối các nhóm chứa comment trùng; ưu tiên phân phối lớp cân đối nhưng không phá ràng buộc nhóm. Khi metadata thiếu, ghi hạn chế và dùng phương án tránh trùng text giữa split. Nếu có nhiều phim/nguồn, thêm đánh giá trên phim/bài chưa từng thấy; không trộn cùng một bài vào train và test.
5. **Vectorize đúng:** `fit` tokenizer/vectorizer/TF-IDF **chỉ train**, `transform` dev/test. Lưu artifacts, seed, config và phiên bản dữ liệu; không tái sử dụng `X_*.npz` từng fit trên toàn bộ corpus.
6. **Tuyệt đối không** cho dữ liệu test ảnh hưởng tới prompt/rule điều chỉnh, ngưỡng, chọn mô hình, active-learning hoặc pseudo-label training.

## 5. Các mô hình cần triển khai (theo thứ tự)

| Mức | Mô hình | Yêu cầu |
|---|---|---|
| P0 | Majority baseline | Dự đoán lớp phổ biến nhất để làm mốc |
| P0 | BoW + MultinomialNB | Baseline rẻ, tái lập |
| P0 | TF-IDF + Logistic Regression | Báo Macro-F1, per-class |
| P0 | TF-IDF + LinearSVC | Tối ưu C/class_weight trên validation hoặc CV train |
| P1 | ViSoBERT (`uitnlp/visobert`) | Fine-tune **3 lớp**, giữ emoji/dấu/teencode, chọn checkpoint bằng val |
| P1 | PhoBERT-v2 (`vinai/phobert-base-v2`) | Fine-tune 3 lớp, word segmentation nhất quán |
| P2, tùy tài nguyên | BamiBERT / model khác | Chỉ sau khi P0/P1 chạy ổn; không mở rộng vô hạn |

Với dữ liệu comment mạng xã hội, thử thêm **word n-gram (1,2)** và **char n-gram** cho TF-IDF, vì teencode/sai chính tả. Giữ cùng split và cùng gold test cho mọi model. Không áp dụng thẳng threshold/code nhị phân từ repo Toxic PTIT vào 3 lớp.

## 6. Đánh giá, so sánh và báo cáo

- Bắt buộc: `Macro-F1`, `Accuracy`, `Precision/Recall/F1` từng lớp, `Confusion Matrix`, số mẫu từng lớp, thời gian train/inference và cấu hình.
- Báo riêng **tỷ lệ sai nhãn tự động** ước lượng qua một mẫu kiểm tra ngẫu nhiên có phân tầng (kể cả các mẫu confidence cao), tỷ lệ REVIEW, tỷ lệ sửa nhãn, agreement giữa người gán.
- So sánh **gold-only vs gold + pseudo-label**, baseline truyền thống vs Transformer, và phân tích lỗi ở nhóm mỉa mai, phủ định, nhiều ý trái chiều, cảm xúc do phim.
- Chỉ đánh giá gold test **một lần cho đợt kết luận cuối** sau khi chốt mô hình. Nếu test đã từng dùng để chỉnh, công bố và chuẩn bị một test độc lập mới khi có thể.
- Không đặt ra accuracy/F1 giả. Bất kỳ báo cáo số nào phải dẫn tới artifact, split manifest và commit/config tương ứng.

## 7. Gợi ý cấu trúc thực thi (điều chỉnh theo repo hiện có)

```text
configs/                 # YAML/JSON: data schema, seeds, models, thresholds
src/data/                # import, validate, clean, dedup, split
src/annotation/          # guideline, review queue, audit, pseudo-label
src/features/            # BoW/TF-IDF train-only
src/models/              # NB, LR, LinearSVM, ViSoBERT, PhoBERT
src/evaluation/          # metrics, confusion, error analysis
scripts/                 # CLI cho từng phase; crawler tùy chọn
tests/                   # fixtures nhỏ + unit/integration tests
data/raw/                # bất biến, gitignore nếu nhạy cảm
data/processed/          # có phiên bản
data/annotations/        # gold, machine, adjudication tách biệt
data/splits/             # manifest đã khóa
outputs/runs/            # metrics, predictions, models, configs
README.md
```

Các lệnh mong muốn (tên có thể thay đổi nếu repo đã có CLI): `prepare-data`, `sample-annotation`, `train-baselines`, `train-transformer`, `score-unlabeled`, `build-review-queue`, `evaluate`, `report`. Tạo hướng dẫn chạy cụ thể, không chỉ code mà không có README.

## 8. Thu thập dữ liệu bổ sung — chỉ làm sau pipeline dữ liệu

Nếu repo đang có crawler, trước tiên **kiểm tra và vá** để xuất đầy đủ metadata thay vì viết lại. Có thể tham khảo `app.py`, `scripts/crawler/dom.js`, `scripts/crawler/helpers.js` từ repo Toxic PTIT: Selenium + Chrome, tự tìm bài trong feed, mở từng bài, tải comment/reply, lưu metadata. **Không mặc định dùng crawler này ngay.** Chỉ thu thập nội dung được phép truy cập/sử dụng, tôn trọng quy định nền tảng và quyền riêng tư; không vượt CAPTCHA/rate limits/cơ chế hạn chế. Không cam kết thu đủ 100% comment Facebook. Lọc PII khi tạo bản chia sẻ.

## 9. Tests / tiêu chí nghiệm thu

- Import hai dạng file giả lập; không thay đổi raw, không tạo metadata giả; số dòng trước/sau làm sạch và lý do loại có thể đối chiếu.
- `POS/NEG/NEU` khác `REVIEW/EXCLUDE`; `REVIEW` không được train như lớp thứ 4; không ép mỉa mai/khó xác định vào NEU.
- Dedup không cho text giống nhau xuất hiện qua train/dev/test, không trùng `post_id` giữa split khi có metadata; toàn bộ pipeline deterministic theo seed.
- Kiểm thử xác nhận TF-IDF chỉ fit trên train (từ chỉ xuất hiện trong test không nằm trong vocabulary).
- Tập gold test không có `label_source=machine`, không chứa dữ liệu đã dùng để tune/train.
- P0 chạy end-to-end trên fixture, xuất metrics/confusion matrix/predictions; P1 chạy khi có GPU và dữ liệu đủ.
- Pseudo-label giữ `model_id`, `model_version`, `score`, `is_pseudo`, `needs_review`; không ghi đè human labels.
- Có báo cáo đo chất lượng nhãn tự động trên người kiểm chứng, chứ không lấy độ khớp với nhãn máy làm “độ chính xác thật”.
- README hướng dẫn chạy từng lệnh, setup, đầu vào và vị trí outputs. `git status` cuối cùng rõ những file đã thay đổi; không commit dữ liệu nhạy cảm.

## 10. Trình tự Codex cần thực hiện ngay

**Phase A — Repo audit:** Kiểm tra cấu trúc, dữ liệu, scripts cũ, môi trường/GPU, các vấn đề rò rỉ. Gửi bảng giữ/sửa/tạo; không xóa hiện trạng.

**Phase B — Data foundation:** Implement import + schema + raw/processed + dedup + metadata/provenance + group split + tests. Tạo report mô tả nguồn/phân phối nếu có file thật.

**Phase C — Annotation foundation:** Viết guideline thành file versioned; tạo dry-run/pilot sampler, bảng để người xác nhận nhãn, `REVIEW` queue, thống kê agreement/kappa, không cần UI lớn.

**Phase D — Baseline:** Majority, NB, LR, LinearSVM; cùng split; Macro-F1/per-class/confusion; kiểm tra leakage; lưu model và manifest.

**Phase E — Active learning:** Score unlabeled, chọn đa dạng mẫu bất đồng/bất định để review, pseudo-label có điều kiện và audit ngẫu nhiên.

**Phase F — Transformer:** Fine-tune ViSoBERT rồi PhoBERT khi có GPU, so sánh trên cùng gold validation/test. Không chặn các phase đầu vì chưa có GPU.

**Phase G — Optional crawler:** Chỉ sau khi dữ liệu và đánh giá đã chạy đúng; giữ metadata và tính hợp pháp.

**Yêu cầu phản hồi của Codex sau mỗi phase:** (i) đã làm gì, (ii) file thay đổi, (iii) command đã chạy và kết quả test, (iv) hạn chế/bất định, (v) bước tiếp theo. **Bắt đầu thực hiện Phase A → B ngay, đừng chỉ trả lời bằng một kế hoạch.**
