"""Fixed development-only preprocessing comparisons; no gold evaluation path."""
import json
import platform
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import mean, stdev

import numpy as np
import sklearn
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from src.dataset.common import ROOT, load, read_jsonl, sha, verify, write_csv, write_jsonl
from src.preprocessing.model import model_view, text_model, ModelOptions, TEENCODE, MN_NEXT
from .core import metrics

SEEDS = (20261113, 42, 123, 2026, 17)
TOKEN_PATTERN = r'(?u)[^\s]+'
RECIPES = {'A': None, 'B': None, 'C_no_pyvi': ModelOptions(segment=False),
           'D_no_pyvi': ModelOptions(segment=False), 'C': ModelOptions(), 'D': ModelOptions(),
           'C_no_teencode': ModelOptions(teencode=False), 'C_no_elongation': ModelOptions(elongation=False)}
DOM_RECIPES = {'B', 'D', 'D_no_pyvi'}
MODELS = ('bow_complement_nb', 'tfidf_word_svm', 'tfidf_char_svm')


def fit_fold(pipeline, texts, labels, train, validation):
    if set(train) & set(validation): raise ValueError('Train/validation indices overlap')
    pipeline.fit([texts[i] for i in train], [labels[i] for i in train])
    return pipeline.predict([texts[i] for i in validation])


def write_report(output):
    """Regenerate a local narrative from recorded results, without fitting."""
    from src.dataset.common import csv_rows
    output = Path(output); config = load(output/'config.json')
    comparison = csv_rows((output/'comparison.csv').read_bytes())[0]
    paired = csv_rows((output/'paired_deltas.csv').read_bytes())[0]
    lines = ['# Development preprocessing CV', '',
        '**Kết luận: READY_WITH_LIMITATIONS; không thay pipeline/config đã evaluate gold.**', '',
        'Chỉ 425 human sentiment labels: 346 Facebook (35 post), 79 legacy không post_id. '
        'Mỗi legacy record là group riêng: **không bảo đảm chống leakage theo bài cho legacy**. '
        'Bảng phụ Facebook-only dùng 346 nhãn và group theo 35 post. '
        'Không dùng overall/AI label, nội dung hoặc nhãn gold.', '',
        '5 fold × 5 seed: '+str(config['seeds'])+'. Cùng fold cho mọi recipe/model trong mỗi cohort. '
        'Train có vectorizer fit riêng; validation chỉ transform/predict. '
        'Không phá post group; đã chặn transformed exact-text collision qua fold. '
        'Không bảo đảm chặn mọi near-duplicate: đây là grouped development CV, không phải independent test.', '',
        'A = minimal.lower(); B = DOM-rule view.lower(); C = minimal + full text_model; D = DOM-rule + full text_model. '
        'C_no_pyvi/D_no_pyvi chỉ tắt segmentation; C_no_teencode/C_no_elongation chỉ tắt đúng bước tương ứng. '
        'A/B không tách dấu câu; C/D và các ablation tách nhưng giữ dấu câu. Vì vậy A→C là nhiều tác động, '
        'không riêng PyVi; chỉ so C_no_pyvi→C hoặc D_no_pyvi→D để đo PyVi.', '',
        'Word vectorizer: `token_pattern='+repr(TOKEN_PATTERN)+'`, `lowercase=False`, không strip accents/stopwords; '
        'BoW unigram + ComplementNB alpha=1; word TF-IDF (1,2) + LinearSVC C=1 balanced. '
        'Char: TF-IDF analyzer=char_wb (3,5), token_pattern=None (không áp dụng), lowercase=False + LinearSVC C=1 balanced. '
        'Seed của classifier khớp seed CV. Pattern được lưu theo từng fold; thông số đầy đủ trong config/comparison.', '',
        '## Macro-F1 OOF theo seed', '',
        'Mean ± sample std trên **5 OOF seed**, không coi 25 fold là 25 quan sát độc lập. '
        'Fold results/support/confusion matrix ở fold_results.csv; OOF từng seed ở seed_results.csv.', '',
        '| Cohort | Recipe | Model | Macro-F1 mean ± std |', '|---|---|---|---:|']
    for r in comparison:
        lines.append(f"| {r['cohort']} | {r['recipe']} | {r['model']} | {float(r['macro_f1_oof_mean']):.4f} ± {float(r['macro_f1_oof_std']):.4f} |")
    lines += ['', '## Paired OOF deltas', '', '| Cohort | Contrast | Model | Delta mean ± std | Seed tăng / 5 |', '|---|---|---|---:|---:|']
    for r in paired:
        lines.append(f"| {r['cohort']} | {r['contrast']} | {r['model']} | {float(r['delta_mean']):+.4f} ± {float(r['delta_std']):.4f} | {r['positive_seeds']} |")
    lines += ['', '## DOM view và truy vết', '',
        'Chỉ đọc các nguồn Facebook có đường dẫn/row/SHA trong filtered, kể cả CSV, JSONL và member ZIP. '
        'Kiểm raw/comment_id/post_id khớp nguồn trước khi gọi lại display_text() hiện có; không sửa gold.py. '
        'display_text() chỉ xác minh phép xóa giới hạn đoạn tên; nó KHÔNG chứng minh mention bằng DOM. '
        'dom.js hiện loại account-link khỏi message nhưng không lưu href/node riêng: thành công chỉ gọi **DOM_RULE_MATCH**, '
        'không gọi VERIFIED_DOM_VIEW. Không xóa tên bằng regex mới. Metadata thiếu/sai hoặc deletion không hợp lệ thì RAW '
        '(RAW ở đây là minimal(raw), không sửa raw). Legacy không áp DOM. '
        'Model view là hàm dùng chung cho future train/annotation, không tự thay workbook/pool/gold hiện có.', '',
        'Chi tiết số lượng/reason/raw≠view/reply thay đổi ở view_audit.csv; model_views.local.jsonl giữ record_id, source, '
        'text_view, view_method, reason cho toàn bộ 25.810 câu. no_dom_metadata tính thiếu version/view/count, '
        'khác với no_source_observation (không có nguồn quan sát).', '',
        '## Diễn giải và quyết định', '',
        '- DOM không cải thiện ổn định ở A→B và C→D; không bật mặc định hoặc coi việc mất tiền tố là dữ liệu tốt hơn. '
        'Không từ đó kết luận tất cả mention bị xóa sai; tác động có thể liên quan tới đặc trưng tên/nguồn và nhãn.',
        '- PyVi có lợi cho BoW trên cohort hỗn hợp, nhưng hiệu quả phụ thuộc cohort/model; không có cải thiện đồng đều. '
        'Char full pipeline chỉ nhích nhẹ trên Facebook-only so A; teencode và rút chữ lặp có tác động nhỏ, không ổn định mọi model.',
        '- Giữ implementation **opt-in cho development**; baseline đơn giản A + char TF-IDF vẫn là đối chứng phù hợp. '
        'Không tự chọn pipeline mới làm active. Mức tăng nhỏ không chứng minh ý nghĩa thống kê hoặc hiệu quả ngoài miền.',
        '- text_model bắt đầu từ minimal view, lowercase phần thường, teencode token nguyên hẹp; mn chỉ trong context whitelist. '
        'Giữ k/dc/cg/mk/mik/mng/j/z/v/ng; không mở rộng bảng để khớp điểm cũ. '
        'Rút chữ lặp từ 3 xuống 1 chỉ trong ablation; có thể giảm cường độ cảm xúc hoặc ảnh hưởng từ ngoại ngữ/tên, '
        'nên chưa xác nhận là sửa chính tả đúng. Không xóa stopwords/phủ định. '
        'Emoji/emoticon/URL/email được bảo vệ trước lowercase và PyVi; giữ :D đúng dạng gốc. '
        'PyVi tạo underscore trong model view, không thêm underscore vào filtered.',
        '- ModelText chặn xử lý lặp trong API khi còn kiểu đánh dấu; sau serialize thành str không còn marker. '
        'Luôn dựng từng recipe từ text_minimal/text_view và config, không đưa lại text_model vào preprocessing.', '',
        '## Khác ablation cũ', '',
        'Bảng cũ rộng hơn theo người dùng: dc,cg,mk,mik,mng,j,z,v,ng. Bảng hẹp mới không ánh xạ các token này. '
        'Không có artifact PyVi với bảng rộng được xác định là cùng input/fold/config trong lần chạy này, '
        'nên **chưa có delta trực tiếp có thể quy cho thay đổi bảng**; không dựng số liệu để khớp. '
        'Artifact Phase E còn local ghi underthesea 8.3.0, 346 câu, 3 fold và regex word khác; '
        'không phải đối chứng PyVi hẹp/rộng này. Kết quả hiện tại 425/346 câu, 5×5, whitespace token pattern, '
        'vectorizer lowercase=False, PyVi 0.1.1 và DOM-rule policy mới nên không so điểm tuyệt đối như cùng protocol.', '',
        '## Reproduce và bất biến', '',
        '`python -m src.models preprocessing-cv --output outputs/preprocessing_experiments/NEW_RUN`', '',
        'Cài requirements/classical-base.txt trong môi trường hiện có, không đổi environment lock lịch sử. '
        'PyVi API upstream: https://github.com/trungtv/pyvi ; tokenizer dùng mô hình đóng gói sẵn, không fit tokenizer trên corpus này. '
        'Snapshot SHA trước/sau gồm filtered, raw/provenance được pin, human labels/splits/results lịch sử, '
        'toàn bộ gold/receipt/reservations (chỉ hash bytes, không parse nội dung/nhãn gold). '
        'immutability.json xác nhận tất cả giữ nguyên. Không tạo evaluation receipt mới; không train/predict gold. '
        'Không thay approval/active pointer. CV là phát triển, chưa xác nhận trên test độc lập.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def estimator(name, seed):
    if name == 'bow_complement_nb':
        vectorizer = CountVectorizer(token_pattern=TOKEN_PATTERN, lowercase=False, ngram_range=(1, 1))
        model = ComplementNB(alpha=1.)
    elif name == 'tfidf_word_svm':
        vectorizer = TfidfVectorizer(token_pattern=TOKEN_PATTERN, lowercase=False, ngram_range=(1, 2))
        model = LinearSVC(C=1., class_weight='balanced', random_state=seed, max_iter=20000)
    elif name == 'tfidf_char_svm':
        vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), lowercase=False,
                                     token_pattern=None)
        model = LinearSVC(C=1., class_weight='balanced', random_state=seed, max_iter=20000)
    else: raise ValueError('Unknown development model')
    return Pipeline([('vectorizer', vectorizer), ('model', model)])


def fold_plan(rows, seeds=SEEDS, n_splits=5):
    ids = [r['record_id'] for r in rows]
    if len(set(ids)) != len(ids): raise ValueError('Repeated development record ID')
    labels = [r['human_label'] for r in rows]; groups = []
    from src.crawler.parser import post_id
    for row in rows:
        if row['source_dataset'] == 'facebook':
            if not row.get('post_id') or post_id(row.get('post_url') or '') != row['post_id']:
                raise ValueError('Facebook requires verified post identity for grouped CV')
            groups.append('facebook:post:' + row['post_id'])
        else:
            # Explicitly NOT a fabricated post identity or a post-independence claim.
            groups.append('legacy:record:' + row['record_id'])
    plans = []
    for seed in seeds:
        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        seen = set()
        for fold, (tr, va) in enumerate(splitter.split(ids, labels, groups)):
            assert not {groups[i] for i in tr} & {groups[i] for i in va}
            if len({labels[i] for i in tr}) < 2: raise ValueError('Insufficient train classes')
            seen.update(va.tolist())
            plans.append(dict(seed=seed, fold=fold, train=tr.tolist(), validation=va.tolist(),
                              train_support=dict(Counter(labels[i] for i in tr)),
                              validation_support=dict(Counter(labels[i] for i in va))))
        assert seen == set(range(len(rows)))
    return plans, groups


def source_observations(rows, root):
    """Only checksum-pinned Facebook source exports, never search crawl runs/gold."""
    refs = defaultdict(list); result = {}; checksums = {}
    for row in rows:
        if row['source_dataset'] == 'facebook': refs[row['source_file']].append(row)
    from src.dataset.master import read_payload
    import zipfile
    import hashlib
    for relative, members in sorted(refs.items()):
        archive, separator, member = relative.partition('!')
        path = (root / archive).resolve()
        if not path.is_relative_to(root.resolve()) or path.is_relative_to(root/'outputs/gold'):
            raise ValueError('Source outside approved workspace / gold source forbidden')
        if not path.is_file(): continue  # Missing DOM metadata safely falls back.
        container_hash = sha(path)
        if separator:
            with zipfile.ZipFile(path) as stream: payload = stream.read(member)
            suffix = Path(member).suffix
        else:
            payload = path.read_bytes(); suffix = path.suffix
        checksum = hashlib.sha256(payload).hexdigest()
        if any(r['source_sha256'] != checksum for r in members):
            raise ValueError('Pinned Facebook source checksum mismatch')
        checksums[str(path)] = container_hash
        observations, _ = read_payload(payload, suffix)
        for row in members:
            index = row['source_row'] - 1
            if not 0 <= index < len(observations): raise ValueError('Source row out of range')
            result[row['record_id']] = observations[index]
    return result, checksums


def snapshot(root, filtered):
    """Hash bytes only: never parse gold text or gold human labels."""
    paths = {p.resolve() for p in filtered.iterdir() if p.is_file()}
    protected = load(filtered/'protected_inputs.local.json')
    paths.update(Path(p) for p in protected)
    for relative in ('outputs/gold', 'data/test_reservations', 'data/evaluation_usage'):
        directory = root/relative
        if directory.exists(): paths.update(p.resolve() for p in directory.rglob('*') if p.is_file())
    return {str(p): sha(p) for p in sorted(paths)}


def run(output, root=ROOT):
    root = Path(root).resolve(); output = Path(output).resolve()
    if not output.is_relative_to(root/'outputs/preprocessing_experiments'):
        raise ValueError('Use a new local outputs/preprocessing_experiments directory')
    if output.exists(): raise FileExistsError('Experiments are immutable; choose a new output')
    filtered = root/'outputs/canonical/versions/filtered_20261112_final'
    verify(filtered); before = snapshot(root, filtered)
    rows = read_jsonl(filtered/'candidate.local.jsonl')
    observations, source_hashes = source_observations(rows, root)
    views = [model_view(r, observations.get(r['record_id'])) for r in rows]
    by_id = {v['record_id']: v for v in views}
    labeled = sorted([r for r in rows if r['human_label'] in ('POS', 'NEG', 'NEU') and
                      any(d['status'] == 'LABELED' and d.get('label') == r['human_label']
                          for d in r['human_decisions'])], key=lambda r: r['record_id'])
    # Reuse production reservation guards, reading only quarantine IDs/hashes.
    from src.dataset.blind import assert_allowed
    assert_allowed([dict(r, id=r['record_id'], text_view=by_id[r['record_id']]['text_view']) for r in labeled], 'model_selection')
    output.mkdir(parents=True)
    write_jsonl(output/'model_views.local.jsonl', views)
    audit = []
    for source in sorted({r['source_dataset'] for r in rows}):
        for method in ('RAW', 'DOM_RULE_MATCH', 'VERIFIED_DOM_VIEW'):
            subset = [r for r in rows if r['source_dataset'] == source and by_id[r['record_id']]['view_method'] == method]
            audit.append(dict(source=source, view_method=method, records=len(subset),
                changed=sum(r['text_raw'] != by_id[r['record_id']]['text_view'] for r in subset),
                changed_from_minimal=sum(r['text_minimal'] != by_id[r['record_id']]['text_view'] for r in subset),
                replies_changed=sum(bool(r['parent_comment_id']) and r['text_minimal'] != by_id[r['record_id']]['text_view'] for r in subset),
                no_source_observation=sum(r['record_id'] not in observations for r in subset),
                no_dom_metadata=sum(not all(k in observations.get(r['record_id'], {}) for k in
                    ('text_extraction_version','text_without_mentions','mention_count')) for r in subset),
                reasons=dict(Counter(by_id[r['record_id']]['reason'] for r in subset))))
    write_csv(output/'view_audit.csv', audit, list(audit[0]))
    texts = {}
    for recipe, options in RECIPES.items():
        texts[recipe] = {}
        for r in labeled:
            text = by_id[r['record_id']]['text_view'] if recipe in DOM_RECIPES else r['text_minimal']
            texts[recipe][r['record_id']] = str(text_model(text, options)) if options else text.lower()
    write_jsonl(output/'development_model_texts.local.jsonl', [dict(record_id=r['record_id'],
        texts={k:texts[k][r['record_id']] for k in RECIPES}) for r in labeled])
    plans = {}; scores = []; seed_scores = []; distribution = {}; vec_configs = {}
    for cohort, subset in [('all_human', labeled), ('facebook_only', [r for r in labeled if r['source_dataset']=='facebook'])]:
        plan, groups = fold_plan(subset); plans[cohort] = dict(ids=[r['record_id'] for r in subset], groups=groups, folds=plan)
        distribution[cohort] = dict(n=len(subset), labels=dict(Counter(r['human_label'] for r in subset)),
            groups=len(set(groups)), missing_post_id=sum(not r['post_id'] for r in subset),
            legacy_record_groups=sum(r['source_dataset']!='facebook' for r in subset))
        y = [r['human_label'] for r in subset]
        for recipe in RECIPES:
            x = [texts[recipe][r['record_id']] for r in subset]
            for name in MODELS:
                for seed in SEEDS:
                    pred = [None]*len(subset)
                    for split in [p for p in plan if p['seed']==seed]:
                        tr, va = split['train'], split['validation']
                        # Detect transformed exact duplicates across folds; never hide leakage.
                        overlap = {x[i] for i in tr} & {x[i] for i in va}
                        estimator_ = estimator(name, seed); started = time.perf_counter()
                        if overlap: raise ValueError('Transformed exact duplicate crosses folds; do not fit')
                        predicted = fit_fold(estimator_, x, y, tr, va)
                        for i, value in zip(va, predicted): pred[i] = str(value)
                        m = metrics([y[i] for i in va], predicted)
                        scores.append(dict(cohort=cohort, recipe=recipe, model=name, seed=seed, fold=split['fold'],
                            macro_f1=m['macro_f1'], accuracy=m['accuracy'], per_class=m['per_class'],
                            confusion_matrix=m['confusion_matrix'], seconds=time.perf_counter()-started,
                            train_support=split['train_support'], validation_support=split['validation_support'],
                            transformed_cross_fold_exact_texts=len(overlap),
                            token_pattern=estimator_.named_steps['vectorizer'].token_pattern,
                            lowercase=estimator_.named_steps['vectorizer'].lowercase))
                    m = metrics(y, pred)
                    seed_scores.append(dict(cohort=cohort, recipe=recipe, model=name, seed=seed,
                        macro_f1=m['macro_f1'], accuracy=m['accuracy'], recall={k:m['per_class'][k]['recall'] for k in ('POS','NEG','NEU')}))
                vec = estimator(name, SEEDS[0]).named_steps['vectorizer']
                vec_configs[name] = {k:vec.get_params()[k] for k in ('analyzer','token_pattern','lowercase','ngram_range','strip_accents','stop_words')}
        print(cohort + ': finished shared 5x5 development folds', flush=True)
    comparison = []
    for cohort in distribution:
        for recipe in RECIPES:
            for name in MODELS:
                group = [s for s in seed_scores if (s['cohort'],s['recipe'],s['model'])==(cohort,recipe,name)]
                fs = [s for s in scores if (s['cohort'],s['recipe'],s['model'])==(cohort,recipe,name)]
                comparison.append(dict(cohort=cohort, recipe=recipe, model=name,
                    macro_f1_oof_mean=mean(s['macro_f1'] for s in group), macro_f1_oof_std=stdev(s['macro_f1'] for s in group),
                    fold_macro_f1_mean=mean(s['macro_f1'] for s in fs), accuracy_oof_mean=mean(s['accuracy'] for s in group),
                    recall_mean={k:mean(s['recall'][k] for s in group) for k in ('POS','NEG','NEU')},
                    changed_records=sum(texts[recipe][r['record_id']] != texts['A'][r['record_id']] for r in (labeled if cohort=='all_human' else [r for r in labeled if r['source_dataset']=='facebook'])),
                    vectorizer=vec_configs[name]))
    paired = []; paired_folds = []
    for left, right in [('A','B'),('C','D'),('C_no_pyvi','C'),('D_no_pyvi','D'),('C_no_teencode','C'),('C_no_elongation','C')]:
        for cohort in distribution:
            for name in MODELS:
                a = [s for s in seed_scores if (s['cohort'],s['recipe'],s['model'])==(cohort,left,name)]
                b = [s for s in seed_scores if (s['cohort'],s['recipe'],s['model'])==(cohort,right,name)]
                delta = [next(t['macro_f1'] for t in b if t['seed']==s['seed'])-s['macro_f1'] for s in a]
                paired.append(dict(cohort=cohort, model=name, contrast=left+' -> '+right,
                    delta_mean=mean(delta), delta_std=stdev(delta), positive_seeds=sum(d>0 for d in delta), by_seed=dict(zip(SEEDS,delta))))
                left_folds = [s for s in scores if (s['cohort'],s['recipe'],s['model'])==(cohort,left,name)]
                right_folds = {(s['seed'],s['fold']):s for s in scores if (s['cohort'],s['recipe'],s['model'])==(cohort,right,name)}
                for s in left_folds:
                    paired_folds.append(dict(cohort=cohort,model=name,contrast=left+' -> '+right,
                        seed=s['seed'],fold=s['fold'],macro_f1_delta=right_folds[(s['seed'],s['fold'])]['macro_f1']-s['macro_f1']))
    for name, data in [('comparison.csv',comparison),('fold_results.csv',scores),('seed_results.csv',seed_scores),('paired_deltas.csv',paired)]:
        write_csv(output/name, data, list(data[0]))
    write_csv(output/'paired_fold_deltas.csv',paired_folds,list(paired_folds[0]))
    config = dict(seeds=SEEDS, n_splits=5, distribution=distribution, vectorizers=vec_configs,
                  recipes={k:asdict(v) if v else 'minimal.lower()' for k,v in RECIPES.items()},
                  teencode=TEENCODE, mn_next=sorted(MN_NEXT), legacy_limit='không bảo đảm chống leakage theo bài cho legacy',
                  runtime=dict(python=platform.python_version(), sklearn=sklearn.__version__, numpy=np.__version__))
    from importlib.metadata import version
    config['runtime']['pyvi'] = version('pyvi')
    config['input_sha256'] = dict(candidate=sha(filtered/'candidate.local.jsonl'),manifest=sha(filtered/'manifest.json'))
    config['implementation_sha256'] = {str(p.relative_to(root)):sha(p) for p in
        [Path(__file__),root/'src/preprocessing/model.py',root/'src/preprocessing/__init__.py',root/'src/annotation/gold.py']}
    (output/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'folds.json').write_text(json.dumps(plans,ensure_ascii=False),encoding='utf-8')
    # Byte-level before/after hashes include gold and historical pins; no gold content parsed.
    if snapshot(root, filtered) != before or any(sha(p)!=h for p,h in source_hashes.items()):
        raise ValueError('Immutable inputs changed during development CV')
    (output/'immutability.json').write_text(json.dumps(dict(verified=True,files=before,source_exports=source_hashes),indent=2),encoding='utf-8')
    write_report(output)
    return dict(output=str(output),cohorts=distribution,fold_runs=len(scores),immutable_inputs_verified=True)
