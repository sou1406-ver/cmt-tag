> Canonical rebuild 12/11/2026 chưa chạy thí nghiệm mới. Các metrics bên dưới
> vẫn dùng dataset/split lịch sử (532 nhãn, legacy augmentation186). Candidate
> mới còn524 nhãn/178 legacy sentiment, chưa approved; không chuyển input,
> tái sử dụng manifest cũ hoặc gắn điểm lịch sử cho candidate mới.


# Kết quả thực nghiệm và giới hạn so sánh

Không có model mới được fit trong lần consolidation này. Các số dưới lấy từ
báo cáo/artifact đã khóa, không là kết quả test độc lập. Dataset hiện có 532
human sentiment labels không đồng nghĩa mọi experiment dùng 532 validation
rows. **Char-SVM là reference phát triển, không phải model đã nghiệm thu.**

## Protocol và kết quả chính

| Experiment / data | Model / representation | Evaluation protocol | Macro-F1 và nhận xét |
| --- | --- | --- | --- |
| D: synthetic 210 | BoW/TF-IDF × NB/LR/LinearSVC | 126 train /42 dev /42 test fixture | 1,000 cho6cells; majority0,1176. Software smoke, không đo sentiment thực. [D](archive/PHASE_D_REPORT.md) |
| Development: FB346, labels110/144/92 | TF-IDF word(1,2), NB/LR/SVM | Frozen3 grouped folds; OOF trên346 | NB0,2946; LR0,4575; SVM0,4561. LR+mask0,4828, SVM+mask0,4727. [Baseline](archive/DEVELOPMENT_BASELINE.md) |
| E: cùng FB346/folds | LR/SVM None/balanced, B0–B6 | Same3 folds, vectorizer train-only; chọn recipe trên development CV | Best B3 char_wb(3–5)+SVM balanced **0,580159**, accuracy0,6185. Selection optimism; không là independent estimate. [E](archive/PHASE_E_REPORT.md) |
| E.1: cùng FB346 | CountVectorizer MNB/CNB + TF-IDF references | 5 seeds42/7/21/73/2026, mỗi seed3 grouped folds | Char-SVM **0,5593±0,0146**, CNB unigram0,4887±0,0157. Std trên5OOF scores, không15fold độc lập. [E.1](archive/PHASE_E1_REPORT.md) |
| G.3: FB346 + legacy186 | Char-SVM cố định | Strict full-master component gate giữ fold cũ | A/B/C/D bị chặn, chỉ tái lập mốc E; không gọi đây là4 thí nghiệm hoàn tất. [G.3](archive/PHASE_G3_REPORT.md) |
| G.3.1: FB validation346, legacy chỉ thêm train | Same char-SVM, raw/basic_v1 | direct_fold_isolation_v1, same frozen FB folds; legacy post provenance unknown | A0,580159; B0,542666; C0,587578; D0,552875. Direct checks pass, augmentation vẫn exploratory. [G.3.1](archive/PHASE_G3_1_REPORT.md) |
| G.3.2: saved OOF, không refit | Phân tích lỗi A–D và reply provenance | Verify346 source rows/113 replies; zero known thread crossings | Legacy tăng POS prediction nhưng mất NEG/NEU recognition; không tự kết luận legacy labels sai. [G.3.2](archive/PHASE_G3_2_REPORT.md) |
| H: fold0 validation152 | ViSoBERT3epochs FB /FB+legacy | Fixed-config pilot một fold, không full CV | **0,3895 /0,5191**, accuracy0,4408/0,5461. SVM cùng fold0≈0,5739/0,5391; H chưa đủ kết luận model tốt nhất. [H](archive/PHASE_H_REPORT.md) |

## E: cách biểu diễn thực sự thay đổi điều gì?

Cùng classifier SVM balanced và cùng fold để đọc ablation:

| Variant | Feature/preprocessing | Macro-F1 | Khác biệt so mốc phù hợp |
| --- | --- | ---: | --- |
| B0 | Raw word unigram+bigram | 0,4561 | Mốc syllable/regex word features |
| B1 | Chuẩn hóa nhẹ + word | 0,4530 | -0,0031 với B0; nhiều preprocessing không bảo đảm tốt hơn |
| B2 | B1 + underthesea segmentation | 0,4844 | +0,0314 với B1 |
| B3 | Raw char_wb(3–5) | 0,5802 | +0,1241 với cùng SVM B0 |
| B4 | Word+char cố định1:1 | 0,5192 | Chưa vượt char-only |
| B5 | B4 + controlled teencode | 0,5158 | -0,0034 với B4; LR có phản ứng khác |
| B6 | B3 + entity mask bảo toàn raw | 0,5729 | -0,0073 với B3; chưa có lợi ích mask |

B3 recall POS/NEG/NEU = **0,4364/0,8819/0,4239**. Đây là cân bằng tốt hơn B0
trên dataset này, nhưng POS/NEU vẫn yếu. Mask tốt nhất của baseline cũ0,4828
là **LR**, nên không so với B3 như chỉ thay một preprocessing component.
Các phép mới I.2/I.3/v3.1 là annotation recovery, **chưa được train/đánh giá
sentiment ở protocol E**; không gán điểm0,5876 của basic_v1 cho v3.1.

## E.1: BoW, độ nhạy fold và source-label association

| Model | Fold gốc OOF | Mean ± sample std (5 seed) |
| --- | ---: | ---: |
| BoW MNB unigram | 0,4345 | 0,4399±0,0073 |
| BoW MNB unigram+bigram | 0,3871 | 0,3915±0,0109 |
| BoW ComplementNB unigram | 0,4781 | 0,4887±0,0157 |
| BoW ComplementNB unigram+bigram | 0,4367 | 0,4310±0,0120 |
| Word TF-IDF LR balanced | 0,4575 | 0,4657±0,0076 |
| Word TF-IDF SVM balanced | 0,4561 | 0,4645±0,0138 |
| Char TF-IDF SVM balanced | 0,5802 | 0,5593±0,0146 |

Char-SVM cao nhất5/5seed, nhưng các bài Mưa Đỏ không đổi fold sau align giữa
seed; chỉ30–68 câu phim khác đổi. Std nhỏ không đo chuyển miền mạnh. Mưa Đỏ
có90/110POS trong171/346rows, chỉ3bài. Fold0 nhiều lỗi tuyệt đối nhất63/132,
fold1 mới có error rate cao nhất44/104 và Macro-F1 thấp nhất0,5098; không
suy nguyên nhân chỉ từ số POS hay tổng lỗi. CNB unigram recallPOS cao hơn
char-SVM trung bình nhưng recallNEU≈0,148, thấp hơn0,400 của char-SVM.

## E.2: cross-domain ranking khác với argmax classification

Other→Mưa Đỏ: train175 =20POS/134NEG/21NEU, eval171=90/10/71.
Chiều ngược dùng đúng hai miền đảo lại. Char-SVM F1 **0,0707** và **0,1397**;
không dùng target labels sửa threshold hoặc chọn hyperparameter.

| Chiều / lớp | Eval support | Prevalence | ROC-AUC OvR | AP |
| --- | ---: | ---: | ---: | ---: |
| Other→Mưa Đỏ POS | 90 | 0,5263 | 0,5801 | 0,5875 |
| Other→Mưa Đỏ NEG | 10 | 0,0585 | 0,7068 | 0,1919 |
| Other→Mưa Đỏ NEU | 71 | 0,4152 | 0,6096 | 0,4994 |
| Mưa Đỏ→Other POS | 20 | 0,1143 | 0,5155 | 0,1663 |
| Mưa Đỏ→Other NEG | 134 | 0,7657 | 0,6698 | 0,8640 |
| Mưa Đỏ→Other NEU | 21 | 0,1200 | 0,6422 | 0,1827 |

Native LinearSVC order NEG/NEU/POS được ánh xạ rõ sang POS/NEG/NEU.
Score không là probability. NEG ranking có tín hiệu dù chiều ngược argmax
không nhận đúng NEG nào, nhưng POS ranking gần chance và scores chồng lấn:
không thể quy lỗi hoàn toàn cho intercept/threshold hoặc chứng minh prior
shift. AP phải so prevalence; 10NEG Mưa Đỏ quá ít, một dự đoán đổi recall0,1.
[ROC/PR/score plots và đầy đủ giới hạn](archive/PHASE_E2_REPORT.md).

## G: basic normalization và legacy augmentation

| Trial | Training composition | FB OOF F1 | POS recall | NEG recall | NEU recall |
| --- | --- | ---: | ---: | ---: | ---: |
| A | FB original | 0,580159 | 0,4364 | 0,8819 | 0,4239 |
| B | FB+186legacy original | 0,542666 | 0,5091 | 0,7569 | 0,3587 |
| C | FB basic_v1 | 0,587578 | 0,4364 | 0,8819 | 0,4457 |
| D | FB+186legacy basic_v1 | 0,552875 | 0,5364 | 0,7500 | 0,3696 |

Same folds/classifier: normalization C−A +0,0074; D−B +0,0102. Legacy B−A
−0,0375; D−C −0,0347. Validation luôn FB346; 186legacy chỉ train augmentation,
không gọi532validation examples. A→B có44correct→wrong,28wrong→correct;
NEG/NEU giảm, POS tăng. Khác style/label proportions/provenance có thể cùng
góp phần, không phải chứng minh nguyên nhân. Component khổng lồ do transitive
exact bridges khác direct contamination; graph và strict-gate artifact cũ
vẫn nguyên, protocol mới chỉ thu hẹp điều được kết luận.

## H và lựa chọn hiện tại

H smoke xác nhận execution, không sentiment quality. PhoBERT-v2 cần Java/local
RDR assets, chưa có smoke hoàn chỉnh; full4config×3fold chưa chạy. Hai ViSoBERT
pilot numbers chỉ cùng fold0, class support58/47/47, không là OOF toàn346.
Không dùng chúng kết luận Transformer hơn/kém toàn bộ classical CV.

Giữ char_wb TF-IDF(3–5)+LinearSVC C=1, balanced làm **reference có thể tái lập**
và BoW CNB unigram làm bài tập/reference phụ. Không triển khai production,
không train thêm hay chọn threshold trong structural cleanup. Ưu tiên hiện
tại là human quality và independent-test evidence, không tăng score bằng
đổi split/nhãn hoặc silver chưa xác minh.

## Runner/config index

| Purpose | Runner | Config |
| --- | --- | --- |
| Frozen reviewed baseline | scripts/development_baseline.py | baseline_development.json + reviewed artifact |
| E preprocessing | scripts/run_preprocessing_experiments.py | preprocessing_experiments.json |
| E.1 BoW / repeated grouped CV | scripts/run_bow_robustness.py | bow_robustness.json |
| E.2 ranking | scripts/run_ranking_diagnostics.py | ranking_diagnostics.json |
| G.3 strict ablation | scripts/run_normalization_ablation.py | normalization_ablation.json |
| G.3.1 direct isolation | scripts/run_phase_g31_ablation.py | normalization_ablation_direct.json |
| G.3.2 saved-OOF diagnostics | scripts/analyze_legacy_effect_g32.py | sealed G.3.1 artifacts |
| H model-specific inputs | scripts/run_phase_h.py | phase_h/data.json + training.json |

Mọi config ở configs/, output/model/IDs ở local outputs/. Giữ đúng source
hashes, fresh output directory và môi trường trong [setup](guides/ENVIRONMENT.md).
Không so điểm từ protocol khác nhau như một ablation; không dùng fixture,
development CV, transfer hay pilot fold thay independent test.
