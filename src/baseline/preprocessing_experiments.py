"""Phase E: frozen-fold Vietnamese feature/preprocessing ablations, development only."""
import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import hashlib
from importlib.metadata import distribution, distributions
import json
from pathlib import Path
import platform
import shutil
import socket
import tempfile
import time
import warnings

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import Normalizer

from scripts.development_baseline import mask_text
from scripts.import_development_review import verify_files, verify_reviewed_dataset
from scripts.prepare_development import ROOT, grouped_records, load, read_csv, save, sha, write_csv
from src.baseline.core import LABELS, metrics, model
from src.preprocessing.vietnamese import VietnamesePreprocessor


@contextmanager
def offline_network():
    """Pretrained segmenter and classifiers may read local models, never open sockets."""
    old=(socket.create_connection,socket.socket.connect,socket.socket.connect_ex)
    def blocked(*args,**kwargs):raise RuntimeError('Phase E runs offline; network connections are disabled')
    socket.create_connection=socket.socket.connect=socket.socket.connect_ex=blocked
    try:yield
    finally:socket.create_connection,socket.socket.connect,socket.socket.connect_ex=old


def read_locked(config):
    for key in ('locked_plan','reference_metrics','mask_lexicon'):
        if sha(ROOT/config[key])!=config[key+'_sha256']:
            raise ValueError('Frozen input checksum mismatch: '+key)
    source=ROOT/config['dataset'];manifest=load(source/'manifest.json')
    if sha(source/'manifest.json')!=config['dataset_manifest_sha256']:
        raise ValueError('Dataset manifest differs from frozen experiment contract')
    verify_files(source,manifest)
    rows=read_csv(source/'annotations.csv')
    from src.dataset.blind import assert_allowed
    assert_allowed(rows, 'model_selection')
    if (manifest['purpose']!='exploratory_development_only' or manifest['independent_test']
            or manifest['pending_review_ids'] or not manifest['all_human_review_resolved']):
        raise ValueError('Only completed, exposed development annotations are allowed')
    verify_reviewed_dataset(source,rows,manifest)
    locked=load(ROOT/config['locked_plan'])
    if locked['dataset_manifest_sha256']!=config['dataset_manifest_sha256'] or locked['seed']!=config['seed']:
        raise ValueError('Frozen plan dataset/seed mismatch')
    if locked['provisional'] or locked['independent_test'] or not locked['ready_to_run']:
        raise ValueError('Expected the completed development plan')
    if len(locked['folds'])!=3 or {f['fold'] for f in locked['folds']}!={0,1,2}:
        raise ValueError('Expected the same three frozen folds')
    by_id={r['id']:r for r in rows}
    if len(by_id)!=len(rows):raise ValueError('Duplicate dataset IDs')
    eligible={r['id'] for r in rows if r['status']=='LABELED' and r['label'] in LABELS
              and not r['validation_issues'] and not r['audit_pending'] and r.get('review_disposition')!='DEFER'}
    eligible-=set(locked['omitted_duplicate_ids'])
    if len(eligible)!=config['expected_candidates'] or len(eligible)!=locked['candidates']:
        raise ValueError('Candidate set changed')
    _,_,groups=grouped_records(rows)
    if groups!=locked['group_by_id']:raise ValueError('Original post/duplicate components changed')
    observed=[]
    for fold in locked['folds']:
        train,valid=fold['train_ids'],fold['validation_ids']
        if (len(set(train))!=len(train) or len(set(valid))!=len(valid)
                or set(train)&set(valid) or set(train)|set(valid)!=eligible):
            raise ValueError('Frozen fold must partition exactly the eligible IDs')
        if {groups[r] for r in train}&{groups[r] for r in valid}:
            raise ValueError('Frozen fold leaks post/duplicate groups')
        for key,ids in [('train_counts',train),('validation_counts',valid)]:
            if dict(Counter(by_id[r]['label'] for r in ids))!=fold[key]:
                raise ValueError('Frozen fold label counts changed')
        if set(fold['train_counts'])!=set(LABELS):raise ValueError('Every training fold needs three classes')
        observed.extend(valid)
    if len(observed)!=len(set(observed)) or set(observed)!=eligible:
        raise ValueError('Each eligible ID must be validated exactly once')
    return rows,locked,load(ROOT/config['reference_metrics']),load(ROOT/config['mask_lexicon'])['aliases']


def validate_config(config):
    if config['models']!=['lr','svm'] or config['class_weights']!=[None,'balanced']:
        raise ValueError('Phase E compares fixed LR/SVM with None/balanced weights')
    expected={
        'B0':dict(feature='word',light=False,segment=False,teencode=False),
        'B1':dict(feature='word',light=True,segment=False,teencode=False),
        'B2':dict(feature='word',light=True,segment=True,teencode=False),
        'B3':dict(feature='char',light=False,segment=False,teencode=False),
        'B4':dict(feature='union',light=True,segment=False,teencode=False),
        'B5':dict(feature='union',light=True,segment=False,teencode=True)}
    if config['variants']!=expected or list(config['variants'])!=list(expected):
        raise ValueError('B0-B5 ablation definitions/order must remain explicit and separate')
    if config['word_ngrams']!=[1,2] or config['char_ngrams']!=[3,5] or config['char_analyzer']!='char_wb':
        raise ValueError('Expected fixed word(1,2), char_wb(3,5), no feature tuning')
    if config.get('mask_preserve_unmatched_raw') is not True:
        raise ValueError('B6 must preserve unmatched raw Unicode; do not conflate masking with NFC')


def estimator(recipe,kind,weight,config):
    base=model('tfidf',kind,2,weight,config['seed'])
    word=base['vectorizer']
    char=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),strip_accents=None,lowercase=True)
    if recipe['feature']=='word':return base
    features=char if recipe['feature']=='char' else FeatureUnion([('word',word),('char',char)])
    # Keep a common L2 scale when concatenating two individually normalized branches.
    return Pipeline([('features',features),('normalize',Normalizer()),('model',base['model'])])


def prepare_views(rows,recipe,processor,aliases=None):
    views={};audits=[];changes=Counter();occurrences=Counter()
    for row in rows:
        raw=row['text_raw'];text=raw;steps=[]
        if aliases is not None:
            text=mask_text(text,aliases,row['movie_id'],normalize_unicode=False)
            steps.append(dict(step='entity_mask',changed=text!=raw))
        view=processor.transform(text,light=recipe['light'],segment=recipe['segment'],teencode=recipe['teencode'])
        views[row['id']]=view.text;steps.extend(view.steps)
        for step in steps:
            changes[step['step']]+=int(step['changed'])
        changes['total_changed']+=int(view.text!=raw)
        occurrences.update(view.counts)
        audits.append(dict(id=row['id'],raw_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                           text_processed=view.text,steps=steps,counts=view.counts))
    return views,dict(candidate_count=len(rows),changed_comments=dict(changes),occurrences=dict(occurrences)),audits


def collisions(views,locked):
    folds={rid:fold['fold'] for fold in locked['folds'] for rid in fold['validation_ids']}
    buckets=defaultdict(list)
    for rid,text in views.items():buckets[' '.join(text.lower().split())].append(rid)
    output=[]
    for text,ids in buckets.items():
        for index,left in enumerate(sorted(ids)):
            for right in sorted(ids)[index+1:]:
                if folds[left]!=folds[right]:
                    output.append(dict(left=left,right=right,processed_sha256=hashlib.sha256(text.encode()).hexdigest()))
    return output


def score(views,by_id,locked,recipe,kind,weight,config):
    truth=[];guess=[];predictions=[];fold_metrics=[]
    for fold in locked['folds']:
        train,valid=fold['train_ids'],fold['validation_ids']
        pipeline=estimator(recipe,kind,weight,config)
        started=time.perf_counter()
        pipeline.fit([views[r] for r in train],[by_id[r]['label'] for r in train])
        predicted=pipeline.predict([views[r] for r in valid]).tolist()
        expected=[by_id[r]['label'] for r in valid]
        truth.extend(expected);guess.extend(predicted)
        train_features=pipeline[:-1].transform([views[r] for r in train])
        valid_features=pipeline[:-1].transform([views[r] for r in valid])
        train_zero=(train_features.getnnz(axis=1)==0).tolist()
        valid_zero=(valid_features.getnnz(axis=1)==0).tolist()
        fold_metrics.append(dict(fold=fold['fold'],seconds=time.perf_counter()-started,metrics=metrics(expected,predicted),
                                 n_features=train_features.shape[1],zero_vector_train=sum(train_zero),zero_vector_validation=sum(valid_zero)))
        for rid,actual,pred,zero in zip(valid,expected,predicted,valid_zero):
            row=by_id[rid]
            predictions.append(dict(id=rid,fold=fold['fold'],human_label=actual,predicted_label=pred,
                                    movie_id=row['movie_id'],post_id=row['post_id'],selection_cohort=row['selection_cohort'],zero_features=zero))
    return dict(model=kind,class_weight=weight,oof=metrics(truth,guess),folds=fold_metrics),predictions


def verify_reference(result,reference):
    expected=next(r for r in reference['results'] if r['variant']=='original' and r['model']==result['model'])
    if result['oof']!=expected['oof']:
        raise ValueError('B0 failed to reproduce the previous baseline; stop before interpreting ablations')


def environment():
    package=distribution('underthesea')
    models={str(p):sha(package.locate_file(p)) for p in package.files
            if '/pipeline/word_tokenize/models/' in '/'+str(p).replace('\\','/') and package.locate_file(p).is_file()}
    if not models:raise ValueError('Bundled segmentation model missing; do not download it using real comments')
    return dict(python=platform.python_version(),packages={d.metadata['Name']:d.version for d in distributions()},
                segmenter_model_sha256=models,network_disabled=True)


def error_analysis(predictions,rows):
    groups=defaultdict(list);by_id={r['id']:r for r in rows};errors=[]
    for row in predictions:
        for key,value in [('class',row['human_label']),('movie',row['movie_id'])]:
            groups[row['run_id'],key,value].append(row)
        if row['human_label']!=row['predicted_label']:
            errors.append(dict(**row,text_raw=by_id[row['id']]['text_raw']))
    summaries=[]
    for (run_id,kind,value),items in sorted(groups.items()):
        summary=dict(run_id=run_id,group_by=kind,value=value,n=len(items),
                              errors=sum(r['human_label']!=r['predicted_label'] for r in items),
                              correct_rate=1-sum(r['human_label']!=r['predicted_label'] for r in items)/len(items),
                              prediction_counts=dict(Counter(r['predicted_label'] for r in items)))
        if kind=='class':summary['recall']=summary['correct_rate']
        else:summary['metrics']=metrics([r['human_label'] for r in items],[r['predicted_label'] for r in items])
        summaries.append(summary)
    return summaries,errors


def _run(config_path,output,segmenter=None,fixture=False):
    config_checksum=sha(config_path)
    config=load(config_path);validate_config(config)
    rows,locked,reference,aliases=read_locked(config)
    ids={rid for f in locked['folds'] for rid in f['validation_ids']}
    selected=[r for r in rows if r['id'] in ids];by_id={r['id']:r for r in selected}
    processor=VietnamesePreprocessor(config['preprocessing'],segmenter=segmenter)
    started=time.perf_counter();output.mkdir()
    shutil.copyfile(config_path,output/'experiment_config.json')
    if sha(output/'experiment_config.json')!=config_checksum:
        raise ValueError('Experiment config changed while reading')
    shutil.copyfile(ROOT/config['locked_plan'],output/'locked_plan.json')
    shutil.copyfile(ROOT/config['mask_lexicon'],output/'entity_mask.json')
    results=[];predictions=[];audits=[];transform_stats={};duplicate_views={}
    with offline_network(),warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        for name,recipe in config['variants'].items():
            views,stats,view_audit=prepare_views(selected,recipe,processor)
            transform_stats[name]=stats;duplicate_views[name]=collisions(views,locked)
            audits.extend(dict(variant=name,**item) for item in view_audit)
            kinds=[(kind,weight) for kind in config['models'] for weight in config['class_weights']]
            if name=='B0' and config['nb_reference']:kinds.append(('nb',None))
            for kind,weight in kinds:
                result,pred=score(views,by_id,locked,recipe,kind,weight,config)
                run_id=name+'_'+kind+'_'+('none' if weight is None else weight)
                result.update(variant=name,run_id=run_id,recipe=recipe)
                if name=='B0' and (weight=='balanced' or kind=='nb'):verify_reference(result,reference)
                results.append(result);predictions.extend(dict(run_id=run_id,**row) for row in pred)
                print(json.dumps(dict(run_id=run_id,macro_f1=result['oof']['macro_f1'])),flush=True)
        # This selection is development tuning on the same exposed CV, not an unbiased test.
        winner=max((r for r in results if r['model'] in config['models']),key=lambda r:r['oof']['macro_f1'])
        views,stats,view_audit=prepare_views(selected,winner['recipe'],processor,aliases)
        transform_stats['B6']=stats;duplicate_views['B6']=collisions(views,locked)
        audits.extend(dict(variant='B6',**item) for item in view_audit)
        result,pred=score(views,by_id,locked,winner['recipe'],winner['model'],winner['class_weight'],config)
        result.update(variant='B6',run_id='B6_masked_parent_'+winner['run_id'],recipe=winner['recipe'],parent_run_id=winner['run_id'])
        results.append(result);predictions.extend(dict(run_id=result['run_id'],**row) for row in pred)
        env=dict(fixture_only=True,network_disabled=True) if fixture else environment()
        warning_messages=sorted({str(w.message) for w in caught})
    save(output/'environment.json',env)
    save(output/'metrics.json',dict(independent_test=False,results=results,selected_parent_run_id=winner['run_id'],
                                   b6_selection_optimism=True,selection=config['selection']))
    save(output/'normalization_counts.json',transform_stats)
    save(output/'processed_cross_fold_collisions.json',duplicate_views)
    with (output/'preprocessed.jsonl').open('x',encoding='utf-8') as f:
        for row in audits:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    write_csv(output/'predictions.csv',predictions,list(predictions[0]))
    comparison=[dict(run_id=r['run_id'],variant=r['variant'],model=r['model'],class_weight=str(r['class_weight']),
                     macro_f1=r['oof']['macro_f1'],**{'recall_'+label:r['oof']['per_class'][label]['recall'] for label in LABELS}) for r in results]
    write_csv(output/'comparison.csv',comparison,list(comparison[0]))
    group_errors,errors=error_analysis(predictions,selected)
    save(output/'errors_by_class_and_movie.json',group_errors)
    write_csv(output/'errors.csv',errors,list(predictions[0])+['text_raw'])
    save(output/'warnings.json',warning_messages)
    report=render_report(results,transform_stats,duplicate_views,group_errors,locked,winner,warning_messages)
    (output/'REPORT.md').write_text(report,encoding='utf-8',newline='\n')
    # Detect any concurrent change instead of silently recording metrics against different data.
    read_locked(config)
    if sha(config_path)!=config_checksum:
        raise ValueError('Experiment config changed during execution')
    manifest=dict(purpose='development_preprocessing_ablation_only',independent_test=False,fixture_only=fixture,
                  models_trained=True,network_disabled=True,config_sha256=config_checksum,
                  dataset_manifest_sha256=config['dataset_manifest_sha256'],locked_plan_sha256=config['locked_plan_sha256'],
                  reference_metrics_sha256=config['reference_metrics_sha256'],mask_lexicon_sha256=config['mask_lexicon_sha256'],
                  candidates=len(selected),fits=sum(len(r['folds']) for r in results),seconds=time.perf_counter()-started,
                  selected_parent_run_id=winner['run_id'],b6_run_id=result['run_id'],
                  output_sha256={p.name:sha(p) for p in output.iterdir() if p.is_file()})
    save(output/'manifest.json',manifest)
    return manifest


def render_report(results,stats,duplicates,groups,locked,winner,warning_messages):
    table='\n'.join(f"| {r['run_id']} | {r['oof']['macro_f1']:.4f} | "+' | '.join(f"{r['oof']['per_class'][k]['recall']:.4f}" for k in LABELS)+' |' for r in results)
    changes='\n'.join(f"| {key} | {value['changed_comments']['total_changed']} | "+json.dumps(value['changed_comments'],ensure_ascii=False)+' |' for key,value in stats.items())
    matrices=[]
    for r in results:
        body='\n'.join('| '+label+' | '+' | '.join(map(str,row))+' |' for label,row in zip(LABELS,r['oof']['confusion_matrix']))
        matrices.append('\n### '+r['run_id']+'\n\n| Người gán / Dự đoán | POS | NEG | NEU |\n|---|---:|---:|---:|\n'+body)
    b0=max((r for r in results if r['variant']=='B0' and r['model']!='nb'),key=lambda r:r['oof']['macro_f1'])
    b6=results[-1]
    movie_rows=[r for r in groups if r['run_id']==winner['run_id'] and r['group_by']=='movie']
    movie_table='\n'.join(f"| {r['value']} | {r['n']} | {r['errors']} | {r['correct_rate']:.4f} |" for r in sorted(movie_rows,key=lambda r:(-r['n'],r['value'])))
    return f'''# Phase E — Vietnamese Text Preprocessing Experiments

Thăm dò trên {locked['candidates']} nhãn người, đúng ID/fold của plan đã khóa.
Không đổi text_raw, nhãn, guideline hoặc split. TF-IDF chỉ fit trong train từng
fold; không dùng test độc lập. B0 balanced/NB tái tạo đúng metrics baseline cũ.

## Thiết kế

B0 raw word(1,2); B1 NFC/khoảng trắng/lowercase + emoji/emoticon trung tính;
B2 B1 + underthesea 8.3.0, use_token_normalize=False; B3 raw char_wb(3,5);
B4 B1 word+char với trọng số 1:1, L2 sau nối; B5 B4 + ko/khum/đc/k có kiểm soát.
Mask B6 khớp alias NFC/NFD nhưng giữ nguyên Unicode ở phần không thay tên,
không lẫn thêm bước chuẩn hóa NFC vào parent raw/char. Chế độ mask Phase D cũ
giữ hành vi mặc định; chỉ Phase E dùng chế độ bảo toàn raw này.
Không thay vl/vch, bỏ phủ định/dấu tiếng Việt hoặc lọc stopwords.
k sau số được giữ (100 k), k độc lập ở ngữ cảnh khác là giả định của B5 và có
thể sai. Emoji/emoticon mã hóa theo ký tự, không gán POS/NEG theo biểu tượng.
Các bước chuẩn hóa là quy tắc cố định không học từ nhãn. Segmenter dùng model
đóng gói sẵn; kết nối mạng bị chặn suốt quá trình biến đổi và huấn luyện.

LR và LinearSVC C=1, None/balanced; NB alpha=1 chỉ ở B0 để tham chiếu.
Chọn B0–B5 theo pooled OOF Macro-F1, hòa điểm giữ thứ tự config. B6 chỉ thêm
mask vào đúng recipe/model/weight thắng; không đổi mask sau khi xem điểm.
Đây là lựa chọn trên cùng CV phát triển nên có selection optimism; điểm của
biến thể thắng không phải ước lượng độc lập về hiệu năng ngoài thực tế.

## So sánh

| Run | Macro-F1 OOF | Recall POS | Recall NEG | Recall NEU |
|---|---:|---:|---:|---:|
{table}

B0 tốt nhất: {b0['run_id']} ({b0['oof']['macro_f1']:.4f}). Parent chọn cho B6:
{winner['run_id']} ({winner['oof']['macro_f1']:.4f}); sau mask
{b6['oof']['macro_f1']:.4f}. Không khẳng định khác biệt có ý nghĩa thống kê.

## Số câu thực sự thay đổi

Đếm trên đúng {locked['candidates']} câu. Thay đổi text do lowercase/khoảng
trắng chưa chắc đổi vector vì vectorizer B0 vốn lowercase và tách bằng regex.

| Biến thể | Tổng câu đổi text | Số câu theo bước |
|---|---:|---|
{changes}

Chi tiết số lần thay token có trong normalization_counts.json. Text view và
hash raw ở preprocessed.jsonl, không ghi đè annotation. Cặp text sau biến đổi
giống nhau nhưng nằm khác fold: {json.dumps({k:len(v) for k,v in duplicates.items()})}.
Giữ nguyên fold theo yêu cầu; các cặp này được ghi để diễn giải kết quả.

## Lỗi theo chủ đề phim nguồn

Run parent tốt nhất B0–B5; correct_rate là tỷ lệ đúng trong từng nhóm nhỏ,
không phải hiệu năng tổng quát trên phim chưa xuất hiện khi train. movie_id là
chủ đề bài nguồn, comment có thể nói phim khác. Chi tiết từng lớp và mọi run
trong errors_by_class_and_movie.json; các câu sai ở errors.csv để người đọc rà,
không tự đổi nhãn theo model.

| Chủ đề phim | Số câu | Số lỗi | Tỷ lệ đúng mô tả |
|---|---:|---:|---:|
{movie_table}

## Confusion matrices

Hàng là nhãn người, cột là dự đoán, cùng thứ tự POS/NEG/NEU.
{''.join(matrices)}

## Giới hạn và kiểm tra

346 nhãn, một người gán, chọn mẫu có chủ đích và phụ thuộc phim/nguồn; chưa có
gold test độc lập. Không kết luận thiếu dữ liệu hay feature là nguyên nhân duy
nhất từ các ablation này. Không thêm dữ liệu hoặc sửa guideline để làm đẹp điểm.
Độ phủ mask/teencode/emoji và số lượng theo lớp cần đọc cùng điểm số. Underthesea
là model tách từ pretrained, không được fit trên toàn bộ nhãn hiện tại.

Config, plan nguyên byte, môi trường và checksum model tách từ được lưu cùng
artifact. Cảnh báo runtime: {json.dumps(warning_messages,ensure_ascii=False)}.
'''


def run(config_path,output,segmenter=None,fixture=False):
    output=Path(output).resolve()
    if output.exists():raise FileExistsError('Experiment output exists; do not overwrite a recorded run')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.phase-e-',dir=output.parent) as temporary:
        staged=Path(temporary)/'run'
        result=_run(config_path,staged,segmenter,fixture)
        staged.rename(output)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'configs/preprocessing_experiments.json')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/phase_e')
    args=parser.parse_args()
    try:result=run(args.config,args.output)
    except (ValueError,OSError,KeyError,ImportError,RuntimeError) as exc:parser.exit(2,f'{type(exc).__name__}: {exc}\n')
    print(json.dumps({k:result[k] for k in ('candidates','fits','selected_parent_run_id','b6_run_id','independent_test')}))


if __name__=='__main__':main()
