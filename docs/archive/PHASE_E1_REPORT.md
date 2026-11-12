# Phase E.1 — Kết quả BoW và kiểm tra độ ổn định

Chạy 11/11/2026, đúng 346 nhãn người (110 POS / 144 NEG / 92 NEU), không thêm
hoặc sửa dữ liệu. Bốn CountVectorizer baselines và ba TF-IDF references, 5 seed
cố định, tổng 119 lần fit. Không thêm char-BoW phụ hoặc tìm C/alpha; cả hai
ngram ranges đã khai báo đều được báo cáo, không chọn theo transfer.
Phase E, ba fold gốc và toàn bộ artifact cũ giữ nguyên checksum.

## Kết quả tóm tắt

Mốc 0,5802 của char-SVM ở seed 42 được tái tạo đúng từng dự đoán/fold, không
bị thay thế. Qua 5 seed, char-SVM là **0,5593 ± 0,0146**, khoảng 0,5417–0,5802;
seed tham chiếu cũ tình cờ là cao nhất trong năm seed đã khai báo. Char-SVM
cao nhất trong 5/5 seed, nhưng không dùng điều đó để tuyên bố kiểm định
thống kê hoặc hiệu năng trên miền phim mới.

| Model | Macro-F1 fold gốc | Macro-F1 mean ± sample std của 5 seed | Recall POS mean | Recall NEG mean | Recall NEU mean |
|---|---:|---:|---:|---:|---:|
| bow_mnb_w1 | 0.4345 | 0.4399 ± 0.0073 | 0.4945 | 0.8514 | 0.0891 |
| bow_mnb_w12 | 0.3871 | 0.3915 ± 0.0109 | 0.3873 | 0.9014 | 0.0478 |
| bow_cnb_w1 | 0.4781 | 0.4887 ± 0.0157 | 0.5473 | 0.8486 | 0.1478 |
| bow_cnb_w12 | 0.4367 | 0.4310 ± 0.0120 | 0.4255 | 0.8917 | 0.0935 |
| tfidf_word_lr | 0.4575 | 0.4657 ± 0.0076 | 0.2982 | 0.9236 | 0.2326 |
| tfidf_word_svm | 0.4561 | 0.4645 ± 0.0138 | 0.3200 | 0.9264 | 0.2087 |
| tfidf_char_svm | 0.5802 | 0.5593 ± 0.0146 | 0.4055 | 0.8806 | 0.4000 |

BoW tốt nhất trong bảng là ComplementNB unigram. Recall POS của nó cao hơn
char-SVM, nhưng NEU thấp: khoảng 0,148 so với 0,400 của char-SVM. Với alpha=1
đã khai báo, thêm bigram làm cả MNB và CNB kém hơn unigram ở bộ dữ liệu này;
không suy ra bigram luôn có hại ở dataset hoặc tham số khác.

Mean/std được tính trên **5 pooled OOF scores**, không lấy 15 fold làm 15 mẫu
độc lập, cũng không gộp lặp thành 1.730 quan sát mới. Các lần lặp dùng cùng dữ
liệu nên độ lệch chuẩn chỉ mô tả độ nhạy với cách chia nhóm, không phải CI.

## Bằng chứng POS tập trung theo bài/phim

Mưa Đỏ có **90/110 POS (81,8%)**, trong khi chỉ chiếm 171/346 câu (49,4%).
Nó có ba bài với phân bố lần lượt POS/NEG/NEU là 56/3/40, 25/6/23 và 9/1/8.
Các phim khác có 175 câu nhưng chỉ 20 POS, 134 NEG, 21 NEU. Đây là bằng chứng
về sự gắn chặt giữa source-topic và nhãn, không tự chứng minh model chỉ học
phim/tên nhân vật, và không tách được ảnh hưởng phim/cộng đồng/cách chọn mẫu.

Trong ba fold cũ, số POS Mưa Đỏ train → validation lần lượt **34→56, 65→25,
81→9**. POS phim khác trong validation chỉ **2, 4, 14**. Vì vậy tổng số POS
không đủ mô tả độ phủ nguồn của lớp POS; bảng theo post/movie đã được xuất.

Có 5 partition khác nhau, nhưng sau căn chỉnh tên fold, **không câu Mưa Đỏ
nào đổi fold**; chỉ 30–68 câu từ những phim khác đổi. Mỗi bài Mưa Đỏ vẫn là
một khối validation riêng. Std nhỏ trong 5 seed này chưa đo được thay đổi lớn
ở cấu trúc nguồn của đa số POS hoặc chuyển sang cộng đồng/phim mới.

Với char-SVM, fold 1 (đánh số báo cáo từ 1) có **63/132 lỗi, 47,7% tổng lỗi**,
nhưng cũng chứa 152/346 câu. Fold 2 mới có tỷ lệ lỗi cao nhất **44/104 = 42,3%**
và Macro-F1 thấp nhất **0,5098**; fold 3 có 25/90 lỗi, Macro-F1 0,6529.
Không kết luận fold nhiều lỗi tuyệt đối là fold khó nhất, hoặc thiếu số POS
là nguyên nhân duy nhất: fold 2 có 81 POS train, nhiều hơn 52 POS của fold 1.

## Transfer: kết quả yếu, chỉ có giá trị diagnostic

| Chiều | Train POS/NEG/NEU | Eval POS/NEG/NEU | Char-SVM Macro-F1 | Hạn chế chính |
|---|---|---|---:|---|
| Phim khác → Mưa Đỏ | 20 / 134 / 21 | 90 / 10 / 71 | 0,0707 | Chỉ 10 NEG eval; 3 bài Mưa Đỏ |
| Mưa Đỏ → phim khác | 90 / 10 / 71 | 20 / 134 / 21 | 0,1397 | Chỉ 10 NEG train từ 3 bài |

Không có connected component vắt qua hai miền nên không loại mẫu nào ở run
này. Cả hai chiều có đủ ba lớp để fit theo ngưỡng khai báo, nhưng đều gắn
limited_diagnostic. 10 NEG không cho phép suy luận chắc chắn về lớp NEG của
Mưa Đỏ. Chỉ cần một dự đoán thay đổi đã làm recall NEG ở miền này đổi 0,1.

Train trên phim khác → Mưa Đỏ: char-SVM đúng 10/10 NEG nhưng chỉ 2/90 POS và
2/71 NEU. Chiều ngược lại không nhận đúng NEG nào trong **134 NEG** phim khác.
Do đó recall cao của một lớp hoặc ưu thế CV không bảo đảm chuyển miền.
CNB unigram đạt 0,1624 ở chiều A, nhưng đây cũng là điểm rất thấp, không dùng
kết quả transfer để đổi hyperparameter hay lựa chọn mô hình cho test cuối.

Hai miền có prior nhãn gần đảo ngược; training-majority reference cũng được
báo. Chưa kiểm soát riêng được prior shift, cách chọn câu, nội dung/chủ đề,
nguồn cộng đồng và chất lượng nhãn. movie_id là chủ đề bài nguồn; câu có thể
so sánh hoặc nói phim khác. Vì vậy không gọi đây là clean unseen-movie test,
independent gold test hoặc bằng chứng nhân quả rằng thiếu dữ liệu là lý do duy nhất.

## Tái lập và bàn giao

```powershell
.\.venv-phase-e\Scripts\python.exe scripts/run_bow_robustness.py
```

Dùng môi trường/dependencies Phase E đã khóa, không cài thêm package. Config
configs/bow_robustness.json khóa artifact Phase E và seeds 42/7/21/73/2026.
Output ở `outputs/phase_e1/`; đã có sẽ bị từ chối, chọn --output khác để lặp.
Không cho đặt output mới bên trong thư mục Phase E bất biến. Fresh checkout
cần các artifact local đúng hash. CSV/JSON dùng fold 0–2; bảng báo cáo dùng 1–3.

- original_comparison.csv / original_results.json: đầy đủ metrics, confusion
  matrices, fit/predict/total time. TF-IDF được refit E.1 để timing so được với
  BoW nhưng kiểm cả metrics/dự đoán trùng Phase E; không thay kết quả Phase E.
- original_fold_metrics.csv: Macro-F1, recall, support train/val, số/tỷ lệ lỗi,
  tỷ trọng lỗi và thời gian mỗi fold/model.
- overall_distribution.csv / original_fold_distribution.csv: nhãn theo
  movie_id/post_id toàn bộ candidates và từng phần train/validation.
- mua_do_fold_support.csv: số lớp và POS Mưa Đỏ/khác phim theo fold.
- seed_scores.csv / seed_summary.json / repeated_results.json: từng seed và
  mean/std; repeated_plans.json / partition_diagnostics.json để kiểm nhóm.
- transfer_diagnostics.json / transfer_comparison.csv: kiểm support trước fit,
  giới hạn, skip reason, class metrics, confusion matrices và timing hai chiều.
- predictions.csv: ID/model/seed/fold/stage, cho phép tái tính toàn bộ số đo.
  Artifact từng câu giữ local; Git chỉ chia sẻ code/config/tests/report tổng hợp.

Kiểm thử: **174/174 pass** (31,005 giây), gồm CountVectorizer trả count thật,
MNB/CNB, vocabulary chỉ train, 5 seed cố định, không phá connected group,
partition hoán vị không bị đếm thành mới, sample std từ 5 OOF scores, thiếu
lớp thì skip transfer, source Phase E bị sửa thì dừng trước fit, và fixture
end-to-end 119 fit. Không gọi GPT/Claude, silver labeling hoặc PhoBERT.

Kết luận có giới hạn: ưu thế char-SVM lặp lại trong 5 seed hiện tại, nhưng
các partition giữ nguyên những khối Mưa Đỏ. Transfer thất bại cùng phân bố
nhãn theo nguồn cho thấy cần ưu tiên đánh giá độc lập và độ phủ nhãn theo
bài/phim trước khi tuyên bố mô hình tổng quát. Chưa bổ sung dữ liệu hay đổi nhãn
trong E.1; không sửa lại split hoặc mốc Phase E để làm điểm đẹp hơn.

## Báo cáo tự sinh đầy đủ

Đúng 346 nhãn người, không thêm data hoặc sửa nhãn.
Phase E được khóa và giữ nguyên. E.1 refit TF-IDF để đo thời gian cùng cách,
nhưng kiểm tất cả OOF/fold metrics và dự đoán trùng Phase E. Không thay mốc
seed 42 bằng seed tốt nhất, không chọn tham số theo transfer.

### BoW và mốc ba fold cũ

CountVectorizer word unigram / unigram+bigram, lowercase, token đơn cũng giữ,
không stopword/strip accents, binary=False, alpha=1. ComplementNB norm=False.
Không thêm char-BoW vào thí nghiệm chính. TF-IDF LR/SVM balanced, C=1; char
TF-IDF dùng đúng char_wb(3,5) và L2 của Phase E. Input là raw như B0/B3.
Vectorizer fit riêng train từng fold; estimator seed luôn 42 để đổi seed chỉ
tác động cách chia nhóm. Fit_seconds gồm vector hóa train, predict_seconds
gồm transform validation; total là tổng hai phần, không so với timing cũ có
diagnostics overhead. Các lần chạy không cache feature từ validation.

| Model | Macro-F1 OOF | Accuracy | Recall POS | Recall NEG | Recall NEU | Giây |
|---|---:|---:|---:|---:|---:|---:|
| bow_mnb_w1 | 0.4345 | 0.5289 | 0.4909 | 0.8403 | 0.0870 | 0.037 |
| bow_mnb_w12 | 0.3871 | 0.5058 | 0.3909 | 0.8889 | 0.0435 | 0.082 |
| bow_cnb_w1 | 0.4781 | 0.5549 | 0.5455 | 0.8264 | 0.1413 | 0.035 |
| bow_cnb_w12 | 0.4367 | 0.5347 | 0.4364 | 0.8889 | 0.0978 | 0.082 |
| tfidf_word_lr | 0.4575 | 0.5347 | 0.3000 | 0.9167 | 0.2174 | 0.153 |
| tfidf_word_svm | 0.4561 | 0.5376 | 0.3182 | 0.9236 | 0.1957 | 0.086 |
| tfidf_char_svm | 0.5802 | 0.6185 | 0.4364 | 0.8819 | 0.4239 | 0.192 |

Precision/Recall/F1/support từng lớp và confusion matrices đầy đủ ở
original_results.json, repeated_results.json, transfer_diagnostics.json;
bảng phẳng original_comparison.csv. Accuracy chỉ mô tả mẫu phát triển đã chọn.

### Bằng chứng theo fold cũ

Macro-F1 OOF tính trên toàn bộ dự đoán ngoài fold, không phải trung bình ba
Macro-F1. Số lỗi có thể cộng, Macro-F1 không phân rã cộng theo fold. Phân biệt
số lỗi tuyệt đối với tỷ lệ lỗi khi validation khác kích thước.

| Model | Fold | N validation | Lỗi | Tỷ lệ lỗi | Macro-F1 | Recall POS | Recall NEG | Recall NEU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| bow_mnb_w1 | 1 | 152 | 81 | 0.5329 | 0.3753 | 0.4483 | 0.9362 | 0.0213 |
| bow_mnb_w1 | 2 | 104 | 52 | 0.5000 | 0.4201 | 0.5172 | 0.7083 | 0.1111 |
| bow_mnb_w1 | 3 | 90 | 30 | 0.3333 | 0.5512 | 0.5652 | 0.8776 | 0.2222 |
| bow_mnb_w12 | 1 | 152 | 90 | 0.5921 | 0.3038 | 0.2759 | 0.9787 | 0.0000 |
| bow_mnb_w12 | 2 | 104 | 50 | 0.4808 | 0.4192 | 0.5517 | 0.7500 | 0.0741 |
| bow_mnb_w12 | 3 | 90 | 31 | 0.3444 | 0.4943 | 0.4783 | 0.9388 | 0.1111 |
| bow_cnb_w1 | 1 | 152 | 73 | 0.4803 | 0.4555 | 0.5517 | 0.8936 | 0.1064 |
| bow_cnb_w1 | 2 | 104 | 50 | 0.4808 | 0.4572 | 0.5172 | 0.7083 | 0.1852 |
| bow_cnb_w1 | 3 | 90 | 31 | 0.3444 | 0.5271 | 0.5652 | 0.8776 | 0.1667 |
| bow_cnb_w12 | 1 | 152 | 82 | 0.5395 | 0.3744 | 0.3793 | 0.9787 | 0.0426 |
| bow_cnb_w12 | 2 | 104 | 49 | 0.4712 | 0.4611 | 0.4828 | 0.7500 | 0.1852 |
| bow_cnb_w12 | 3 | 90 | 30 | 0.3333 | 0.5088 | 0.5217 | 0.9388 | 0.1111 |
| tfidf_word_lr | 1 | 152 | 83 | 0.5461 | 0.4075 | 0.2586 | 0.9574 | 0.1915 |
| tfidf_word_lr | 2 | 104 | 48 | 0.4615 | 0.4604 | 0.2414 | 0.8542 | 0.2963 |
| tfidf_word_lr | 3 | 90 | 30 | 0.3333 | 0.5208 | 0.4783 | 0.9388 | 0.1667 |
| tfidf_word_svm | 1 | 152 | 82 | 0.5395 | 0.4148 | 0.2759 | 0.9574 | 0.1915 |
| tfidf_word_svm | 2 | 104 | 49 | 0.4712 | 0.4416 | 0.2759 | 0.8542 | 0.2222 |
| tfidf_word_svm | 3 | 90 | 29 | 0.3222 | 0.5298 | 0.4783 | 0.9592 | 0.1667 |
| tfidf_char_svm | 1 | 152 | 63 | 0.4145 | 0.5739 | 0.4483 | 0.9149 | 0.4255 |
| tfidf_char_svm | 2 | 104 | 44 | 0.4231 | 0.5098 | 0.3103 | 0.8542 | 0.3704 |
| tfidf_char_svm | 3 | 90 | 25 | 0.2778 | 0.6529 | 0.5652 | 0.8776 | 0.5000 |

Char-SVM: nhiều lỗi tuyệt đối nhất ở fold [1] (63 lỗi); tỷ lệ lỗi cao nhất ở fold [2] (0.4231); Macro-F1 thấp nhất ở fold [2] (0.5098).
Đây là xác định bằng confusion matrices/OOF, không suy đoán nguyên nhân từ điểm.
original_fold_metrics.csv có số lớp train/validation, tỷ trọng lỗi và timing.
original_fold_distribution.csv có phân bố nhãn theo movie_id và post_id cho
cả train/validation từng fold; không lấy tên phim làm bằng chứng nhân quả.

Mưa Đỏ và phần POS còn lại:

| Fold | Phần | N Mưa Đỏ | POS Mưa Đỏ | NEG Mưa Đỏ | NEU Mưa Đỏ | POS phim khác |
|---|---|---:|---:|---:|---:|---:|
| 1 | train | 72 | 34 | 7 | 31 | 18 |
| 1 | validation | 99 | 56 | 3 | 40 | 2 |
| 2 | train | 117 | 65 | 4 | 48 | 16 |
| 2 | validation | 54 | 25 | 6 | 23 | 4 |
| 3 | train | 153 | 81 | 9 | 63 | 6 |
| 3 | validation | 18 | 9 | 1 | 8 | 14 |

### 5-seed grouped CV

Seeds cố định trước khi đo: [42, 7, 21, 73, 2026]. Cùng một plan cho mọi model trong
mỗi seed. Nhóm nối theo bài, source comment ID và exact/near duplicates như
Phase E, kể cả liên kết qua dòng ngoài train. Seed 42 tái tạo nguyên byte ID
của ba fold cũ và tái dùng kết quả refit E.1, không tính là thí nghiệm độc lập.

| Model | 42 | 7 | 21 | 73 | 2026 |
|---|---:|---:|---:|---:|---:|
| bow_mnb_w1 | 0.4345 | 0.4323 | 0.4487 | 0.4373 | 0.4464 |
| bow_mnb_w12 | 0.3871 | 0.3810 | 0.4079 | 0.3848 | 0.3970 |
| bow_cnb_w1 | 0.4781 | 0.4811 | 0.4829 | 0.4849 | 0.5163 |
| bow_cnb_w12 | 0.4367 | 0.4151 | 0.4265 | 0.4292 | 0.4475 |
| tfidf_word_lr | 0.4575 | 0.4598 | 0.4769 | 0.4679 | 0.4663 |
| tfidf_word_svm | 0.4561 | 0.4663 | 0.4781 | 0.4764 | 0.4454 |
| tfidf_char_svm | 0.5802 | 0.5665 | 0.5417 | 0.5534 | 0.5545 |

Một pooled OOF Macro-F1/seed; mean ± sample std (ddof=1) trên 5 seed scores,
KHÔNG trên 15 fold và KHÔNG gộp 5 lần lặp thành 1.730 mẫu độc lập.

| Model | Macro-F1 mean ± std | Recall POS mean ± std | Recall NEG mean ± std | Recall NEU mean ± std |
|---|---:|---:|---:|---:|
| bow_mnb_w1 | 0.4399 ± 0.0073 | 0.4945 ± 0.0189 | 0.8514 ± 0.0105 | 0.0891 ± 0.0049 |
| bow_mnb_w12 | 0.3915 ± 0.0109 | 0.3873 ± 0.0319 | 0.9014 ± 0.0076 | 0.0478 ± 0.0060 |
| bow_cnb_w1 | 0.4887 ± 0.0157 | 0.5473 ± 0.0226 | 0.8486 ± 0.0158 | 0.1478 ± 0.0212 |
| bow_cnb_w12 | 0.4310 ± 0.0120 | 0.4255 ± 0.0244 | 0.8917 ± 0.0038 | 0.0935 ± 0.0124 |
| tfidf_word_lr | 0.4657 ± 0.0076 | 0.2982 ± 0.0041 | 0.9236 ± 0.0110 | 0.2326 ± 0.0165 |
| tfidf_word_svm | 0.4645 ± 0.0138 | 0.3200 ± 0.0226 | 0.9264 ± 0.0062 | 0.2087 ± 0.0142 |
| tfidf_char_svm | 0.5593 ± 0.0146 | 0.4055 ± 0.0246 | 0.8806 ± 0.0076 | 0.4000 ± 0.0161 |

Chỉ có 5 partition khác nhau khi bỏ qua
hoán vị tên fold. Các seed cùng dữ liệu, các partition giống nhau hoặc chỉ
chuyển ít nhóm không phải bằng chứng độc lập. Std nhỏ chỉ mô tả độ nhạy trong
những cách chia cụ thể này, không chứng minh khái quát tốt. Không báo CI hoặc
kiểm định dựa trên giả định 15 fold độc lập.

| Seed | Số câu đổi fold so với 42 | Số component đổi | Số câu Mưa Đỏ đổi |
|---|---:|---:|---:|
| 42 | 0 | 0 | 0 |
| 7 | 37 | 6 | 0 |
| 21 | 68 | 15 | 0 |
| 73 | 39 | 8 | 0 |
| 2026 | 30 | 8 | 0 |

### Movie/source-topic transfer diagnostic

movie_id là chủ đề bài nguồn, không luôn là phim thực sự được bình luận.
Hai chiều sau là diagnostic phát triển, không independent gold test hoặc
đánh giá phim chưa thấy sạch về ngữ nghĩa. Nếu component vắt qua hai miền,
loại nguyên component khỏi diagnostic và ghi ID; không phá nhóm hay xóa data.
Ngưỡng fit cố định: train mỗi lớp ≥2, eval mỗi lớp ≥1.
Support <20 câu/lớp hoặc <3 component/lớp được gắn hạn chế,
đây là quy tắc cảnh báo đã khai báo, không bảo đảm suy luận thống kê nếu vượt ngưỡng.

#### other_to_mua_do

Status: limited_diagnostic.

Support: `{"train": {"n": 175, "counts": {"POS": 20, "NEG": 134, "NEU": 21}, "groups_per_class": {"POS": 14, "NEG": 27, "NEU": 18}, "n_posts": 32}, "evaluation": {"n": 171, "counts": {"POS": 90, "NEG": 10, "NEU": 71}, "groups_per_class": {"POS": 3, "NEG": 3, "NEU": 3}, "n_posts": 3}}`.

Giới hạn: ["evaluation NEG: only 10 comments"]. Bỏ qua nếu: [].

Train-majority NEG: Macro-F1 0.0368, accuracy 0.0585.

| Model | Macro-F1 | Accuracy | Recall POS | Recall NEG | Recall NEU |
|---|---:|---:|---:|---:|---:|
| bow_mnb_w1 | 0.0848 | 0.0936 | 0.0667 | 0.9000 | 0.0141 |
| bow_mnb_w12 | 0.0540 | 0.0702 | 0.0111 | 1.0000 | 0.0141 |
| bow_cnb_w1 | 0.1624 | 0.1579 | 0.1333 | 0.8000 | 0.0986 |
| bow_cnb_w12 | 0.0915 | 0.0994 | 0.0556 | 1.0000 | 0.0282 |
| tfidf_word_lr | 0.0446 | 0.0643 | 0.0111 | 1.0000 | 0.0000 |
| tfidf_word_svm | 0.0445 | 0.0643 | 0.0111 | 1.0000 | 0.0000 |
| tfidf_char_svm | 0.0707 | 0.0819 | 0.0222 | 1.0000 | 0.0282 |

#### mua_do_to_other

Status: limited_diagnostic.

Support: `{"train": {"n": 171, "counts": {"POS": 90, "NEG": 10, "NEU": 71}, "groups_per_class": {"POS": 3, "NEG": 3, "NEU": 3}, "n_posts": 3}, "evaluation": {"n": 175, "counts": {"POS": 20, "NEG": 134, "NEU": 21}, "groups_per_class": {"POS": 14, "NEG": 27, "NEU": 18}, "n_posts": 32}}`.

Giới hạn: ["train NEG: only 10 comments"]. Bỏ qua nếu: [].

Train-majority POS: Macro-F1 0.0684, accuracy 0.1143.

| Model | Macro-F1 | Accuracy | Recall POS | Recall NEG | Recall NEU |
|---|---:|---:|---:|---:|---:|
| bow_mnb_w1 | 0.0931 | 0.1029 | 0.7500 | 0.0075 | 0.0952 |
| bow_mnb_w12 | 0.0745 | 0.1143 | 1.0000 | 0.0000 | 0.0000 |
| bow_cnb_w1 | 0.1377 | 0.1543 | 0.7000 | 0.0821 | 0.0952 |
| bow_cnb_w12 | 0.1212 | 0.1486 | 0.9000 | 0.0522 | 0.0476 |
| tfidf_word_lr | 0.1050 | 0.1029 | 0.7000 | 0.0000 | 0.1905 |
| tfidf_word_svm | 0.1039 | 0.1086 | 0.8000 | 0.0000 | 0.1429 |
| tfidf_char_svm | 0.1397 | 0.1257 | 0.6500 | 0.0000 | 0.4286 |


### Artifact và tái lập

Chạy scripts/run_bow_robustness.py với venv Phase E và dependencies đã khóa.
Artifact E.1 mới, từ chối ghi đè output; không ghi ngược Phase E. Config,
original_locked_plan.json, phase_e_manifest.json và mọi repeated plan lưu
cùng kết quả. predictions.csv giữ đủ ID/seed/fold/model để tái tính mọi số đo.
Dataset/guideline/split cũ không đổi; không gọi GPT/Claude, silver-labeling
hoặc PhoBERT. Kết quả transfer không dùng chọn hyperparameter/test cuối.

API tham khảo: [CountVectorizer](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.CountVectorizer.html),
[ComplementNB](https://scikit-learn.org/stable/modules/generated/sklearn.naive_bayes.ComplementNB.html),
[StratifiedGroupKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html).

## Precision / Recall / F1 và confusion matrices của mốc cũ

| Model | Lớp | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| bow_mnb_w1 | POS | 0.4865 | 0.4909 | 0.4887 | 110 |
| bow_mnb_w1 | NEG | 0.5525 | 0.8403 | 0.6667 | 144 |
| bow_mnb_w1 | NEU | 0.5000 | 0.0870 | 0.1481 | 92 |
| bow_mnb_w12 | POS | 0.4778 | 0.3909 | 0.4300 | 110 |
| bow_mnb_w12 | NEG | 0.5120 | 0.8889 | 0.6497 | 144 |
| bow_mnb_w12 | NEU | 0.6667 | 0.0435 | 0.0816 | 92 |
| bow_cnb_w1 | POS | 0.5085 | 0.5455 | 0.5263 | 110 |
| bow_cnb_w1 | NEG | 0.5862 | 0.8264 | 0.6859 | 144 |
| bow_cnb_w1 | NEU | 0.5200 | 0.1413 | 0.2222 | 92 |
| bow_cnb_w12 | POS | 0.5053 | 0.4364 | 0.4683 | 110 |
| bow_cnb_w12 | NEG | 0.5401 | 0.8889 | 0.6719 | 144 |
| bow_cnb_w12 | NEU | 0.6429 | 0.0978 | 0.1698 | 92 |
| tfidf_word_lr | POS | 0.5238 | 0.3000 | 0.3815 | 110 |
| tfidf_word_lr | NEG | 0.5259 | 0.9167 | 0.6684 | 144 |
| tfidf_word_lr | NEU | 0.6250 | 0.2174 | 0.3226 | 92 |
| tfidf_word_svm | POS | 0.5147 | 0.3182 | 0.3933 | 110 |
| tfidf_word_svm | NEG | 0.5320 | 0.9236 | 0.6751 | 144 |
| tfidf_word_svm | NEU | 0.6429 | 0.1957 | 0.3000 | 92 |
| tfidf_char_svm | POS | 0.6000 | 0.4364 | 0.5053 | 110 |
| tfidf_char_svm | NEG | 0.6256 | 0.8819 | 0.7320 | 144 |
| tfidf_char_svm | NEU | 0.6190 | 0.4239 | 0.5032 | 92 |

### bow_mnb_w1

| Nhãn người / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 54 | 52 | 4 |
| NEG | 19 | 121 | 4 |
| NEU | 38 | 46 | 8 |

### bow_mnb_w12

| Nhãn người / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 43 | 66 | 1 |
| NEG | 15 | 128 | 1 |
| NEU | 32 | 56 | 4 |

### bow_cnb_w1

| Nhãn người / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 60 | 44 | 6 |
| NEG | 19 | 119 | 6 |
| NEU | 39 | 40 | 13 |

### bow_cnb_w12

| Nhãn người / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 48 | 58 | 4 |
| NEG | 15 | 128 | 1 |
| NEU | 32 | 51 | 9 |

### tfidf_word_lr

| Nhãn người / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 33 | 69 | 8 |
| NEG | 8 | 132 | 4 |
| NEU | 22 | 50 | 20 |

### tfidf_word_svm

| Nhãn người / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 35 | 68 | 7 |
| NEG | 8 | 133 | 3 |
| NEU | 25 | 49 | 18 |

### tfidf_char_svm

| Nhãn người / Dự đoán | POS | NEG | NEU |
|---|---:|---:|---:|
| POS | 48 | 45 | 17 |
| NEG | 10 | 127 | 7 |
| NEU | 22 | 31 | 39 |

Run manifest SHA-256: `49d546532eae7bea7e6fa67fafddf2c5863d1cf35fa580a22f8f02345b621859`.
Phase E manifest giữ nguyên: `52b314e753174bb458e8c2d0d8ceb7bdc8a851f04e444bdcda0e203403bceed3`.
