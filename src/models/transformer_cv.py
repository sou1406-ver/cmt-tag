"""Resumable five-fold Transformer development comparisons; no gold evaluation."""
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import gc
import time

from src.dataset.common import ROOT,load,save,sha,digest,normal,verify,seal,staged,read_jsonl,write_jsonl,write_csv
from src.dataset.blind import assert_allowed
from src.annotation.pilot import fingerprints,reference_index,near_any
from .core import LABELS,metrics,confusion_png
from .transformer_demo import text_view,fit_prepared,REPOS


def verified_pretrained(name,revision,root=ROOT):
    """Download public weights only; pin upstream LFS/Git checksums, then readonly."""
    root=Path(root);cache=root/'data/local_models/cv_verified_cache'
    target=cache/('models--'+REPOS[name].replace('/','--'))/'snapshots'/revision
    proof=cache/(name+'_verified.json')
    if proof.exists():
        info=load(proof)
        if info['revision']!=revision:raise ValueError('Verified revision differs; use a separate cache')
        for relative,h in info['files'].items():
            path=(target/relative).resolve()
            if not path.is_relative_to(target.resolve()) or not path.is_file() or sha(path)!=h:
                raise ValueError('Verified pretrained cache changed; do not repair an active run silently')
        return target
    import hashlib,stat
    from huggingface_hub import HfApi,hf_hub_download
    info=HfApi(token=False).model_info(REPOS[name],revision=revision,files_metadata=True)
    metadata={f.rfilename:f for f in info.siblings}
    weights='model.safetensors' if 'model.safetensors' in metadata else 'pytorch_model.bin'
    required={weights,'config.json','tokenizer_config.json','tokenizer.json','special_tokens_map.json',
              'vocab.txt','bpe.codes','sentencepiece.bpe.model'}&set(metadata)
    checks={};upstream={}
    for relative in sorted(required):
        path=Path(hf_hub_download(REPOS[name],relative,revision=revision,cache_dir=cache,token=False))
        meta=metadata[relative]
        if meta.lfs:
            expected=meta.lfs.sha256;actual=sha(path)
        else:
            data=path.read_bytes();expected=meta.blob_id
            actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if actual!=expected:raise ValueError('Upstream checksum mismatch: '+relative)
        checks[relative]=sha(path);upstream[relative]=expected;path.chmod(stat.S_IREAD)
    save(proof,dict(repo=REPOS[name],revision=revision,files=checks,upstream_checksums=upstream))
    return target


def view_roster(rows,views,fold,condition):
    key='baseline_train_ids' if condition=='human_only' else 'augmented_train_ids'
    validation=fold['validation_ids'];by_id={r['record_id']:r for r in rows}
    exact={normal(views[i]) for i in validation};near=reference_index([fingerprints(views[i]) for i in validation])
    groups={by_id[i]['group_id'] for i in validation};train=[];dropped=[]
    for rid in fold[key]:
        if by_id[rid]['group_id'] in groups:raise ValueError('Post group crosses validation')
        duplicate=normal(views[rid]) in exact or near_any(views[rid],near)
        if duplicate:
            if by_id[rid]['role']=='human':raise ValueError('Transformed human text crosses frozen fold; no silent split repair')
            dropped.append(rid)
        else:train.append(rid)
    return train,validation,dropped


def prepare(reference,output,config,root=ROOT):
    root,reference,output=map(lambda p:Path(p).resolve(),(root,reference,output));cfg=load(config)
    if not output.is_relative_to(root/'outputs'):raise ValueError('Keep experiment local under outputs/')
    if cfg['gold_allowed'] or cfg['approved_release'] or cfg['n_splits']!=5:raise ValueError('Development 5-fold only')
    if output.exists():
        verify(output/'frozen')
        context=load(output/'frozen/context.json')
        if context['reference_sha256']!=sha(reference/'manifest.json') or load(output/'frozen/config.json')!=cfg:
            raise ValueError('Resume context differs; choose a new output')
        return cfg
    verify(reference);summary=load(reference/'summary.json');refcfg=load(reference/'config.json')
    source=root/refcfg['baseline_dataset'];annotation=root/refcfg['annotation_dataset'];verify(source);verify(annotation)
    by_id={r['record_id']:r for r in read_jsonl(annotation/'candidate.local.jsonl')}
    base=[r for r in read_jsonl(source/'candidate.local.jsonl') if r['human_label'] in LABELS]
    selected=load(reference/'selection.local.json')['silver'];rows=[]
    from .human_expansion import group
    for r in base:
        rows.append(dict(record_id=r['record_id'],text=r['text_minimal'],label=r['human_label'],role='human',group_id=group(r),
                         post_id=r.get('post_id'),comment_id=r.get('comment_id'),source_dataset=r['source_dataset']))
    for s in selected:
        r=by_id[s['record_id']]
        rows.append(dict(record_id=r['record_id'],text=r['text_annotation_view'],label=s['label'],role='silver',group_id=group(r),
                         post_id=r.get('post_id'),comment_id=r.get('comment_id'),source_dataset=r['source_dataset']))
    if len(base)!=425 or len(selected)!=summary['silver'] or len({r['record_id'] for r in rows})!=len(rows):raise ValueError('Frozen population changed')
    folds=[f for f in load(reference/'folds.local.json') if f['seed']==cfg['seed']]
    if len(folds)!=5 or {f['fold'] for f in folds}!=set(range(5)):raise ValueError('Need all five fixed folds of declared seed')
    assert_allowed([dict(r,id=r['record_id'],text_view=r['text']) for r in rows],'model_selection',
        reservation_root=root/'outputs/phase_g/blind_test',registry=root/'data/test_reservations')
    from .preprocessing_cv import snapshot
    before=snapshot(root,source);pretrained={}
    for name in cfg['models']:
        # Read revision metadata only. Never initialize from full-425 demo weights.
        info=load(root/'outputs/demo_transformers_425'/name/'model_info.json');revision=info['revision']
        path=verified_pretrained(name,revision,root)
        files={str(p):sha(p) for p in sorted(path.iterdir()) if p.is_file()}
        if not files:raise FileNotFoundError('Missing pinned pretrained cache: '+name)
        proof=load(root/'data/local_models/cv_verified_cache'/f'{name}_verified.json')
        if proof['revision']!=revision or any(sha(path/p)!=h for p,h in proof['files'].items()):
            raise ValueError('Pretrained cache does not match verified source')
        pretrained[name]=dict(path=str(path),revision=revision,files=files)
    with staged(output) as out:
        frozen=out/'frozen';frozen.mkdir()
        write_jsonl(frozen/'rows.local.jsonl',rows);save(frozen/'folds.json',folds);save(frozen/'config.json',cfg)
        save(frozen/'context.json',dict(reference=str(reference),reference_sha256=sha(reference/'manifest.json'),
            protected=before,pretrained=pretrained,human=425,silver=len(selected),
            source_sha256=sha(Path(__file__)),transformer_helper_sha256=sha(ROOT/'src/models/transformer_demo.py')))
        seal(frozen,dict(kind='FROZEN_TRANSFORMER_CV_INPUT',gold_used=False))
    return cfg


def worker(output,name,condition,only_fold=None):
    output=Path(output);verify(output/'frozen');cfg=load(output/'frozen/config.json')
    context=load(output/'frozen/context.json');pretrained=context['pretrained'][name]
    if sha(ROOT/'src/models/transformer_demo.py')!=context['transformer_helper_sha256']:
        raise ValueError('Training implementation changed; do not mix resumed folds')
    if any(sha(p)!=h for p,h in pretrained['files'].items()):raise ValueError('Pretrained weights changed')
    rows=read_jsonl(output/'frozen/rows.local.jsonl');by_id={r['record_id']:r for r in rows}
    views={r['record_id']:text_view(r['text'],name) for r in rows}
    for fold in load(output/'frozen/folds.json'):
        if only_fold is not None and fold['fold']!=only_fold:continue
        if any(sha(p)!=h for p,h in pretrained['files'].items()):raise ValueError('Pretrained changed before fold')
        target=output/'fits'/name/condition/('fold_'+str(fold['fold']))
        expected=dict(frozen_sha256=sha(output/'frozen/manifest.json'),name=name,condition=condition,fold=fold['fold'])
        if target.exists():
            verify(target)
            if load(target/'context.json')!=expected:raise ValueError('Completed fold belongs to different input')
            print(f'{name} {condition} fold={fold["fold"]}: already complete',flush=True);continue
        tr,va,dropped=view_roster(rows,views,fold,condition)
        prefix=f'{name} {condition} fold={fold["fold"]}'
        print(prefix+f': START train={len(tr)}, validation={len(va)}, dropped_silver={len(dropped)}',flush=True)
        def emit(message,**kwargs):print(prefix+': '+message,**kwargs)
        model,tokenizer,losses,elapsed=fit_prepared(name,pretrained['path'],[views[i] for i in tr],
            [by_id[i]['label'] for i in tr],cfg,emit)
        import torch
        model.eval();predicted=[]
        with torch.inference_mode():
            for start in range(0,len(va),cfg['batch_size']):
                ids=va[start:start+cfg['batch_size']]
                batch=tokenizer([views[i] for i in ids],padding=True,truncation=True,max_length=cfg['max_length'],return_tensors='pt')
                result=model(**batch).logits.argmax(dim=-1).tolist()
                predicted.extend(model.config.id2label[i] for i in result)
        score=metrics([by_id[i]['label'] for i in va],predicted)
        if any(sha(p)!=h for p,h in pretrained['files'].items()):raise ValueError('Pretrained changed during fold; no metrics published')
        with staged(target) as out:
            save(out/'context.json',expected)
            save(out/'metrics.json',dict(score,train=len(tr),validation=len(va),elapsed_seconds=elapsed,train_loss=losses,
                human_train=sum(by_id[i]['role']=='human' for i in tr),silver_train=sum(by_id[i]['role']=='silver' for i in tr),
                train_ids=tr,validation_ids=va,transformed_duplicate_exclusions=dropped,
                pretrained_revision=pretrained['revision'],initialization='fresh_pretrained',selected_epoch=cfg['epochs']))
            write_jsonl(out/'oof.local.jsonl',[dict(record_id=i,true_label=by_id[i]['label'],predicted_label=p) for i,p in zip(va,predicted)])
            seal(out,dict(kind='TRANSFORMER_DEVELOPMENT_FOLD',gold_used=False))
        print(prefix+f': DONE macro-F1={score["macro_f1"]:.4f}',flush=True)
        del model,tokenizer;gc.collect()
    return name,condition


def summarize(output):
    output=Path(output);cfg=load(output/'frozen/config.json');context=load(output/'frozen/context.json')
    comparison=[];fold_scores=[]
    for name in cfg['models']:
        for condition in cfg['conditions']:
            oof=[]
            for fold in range(5):
                path=output/'fits'/name/condition/f'fold_{fold}';verify(path)
                oof+=read_jsonl(path/'oof.local.jsonl');fold_scores.append(dict(model=name,condition=condition,fold=fold,**load(path/'metrics.json')))
            if len(oof)!=425 or len({r['record_id'] for r in oof})!=425:raise ValueError('Incomplete five-fold OOF')
            score=metrics([r['true_label'] for r in oof],[r['predicted_label'] for r in oof])
            comparison.append(dict(model=name,condition=condition,seed=cfg['seed'],**score))
    if any(sha(p)!=h for p,h in context['protected'].items()):raise ValueError('Protected data changed during experiment')
    if (output/'manifest.json').exists():verify(output);return load(output/'summary.json')
    write_csv(output/'comparison.csv',comparison,list(comparison[0]));write_csv(output/'fold_results.csv',fold_scores,list(fold_scores[0]))
    save(output/'metrics.json',comparison)
    (output/'figures').mkdir(exist_ok=True)
    lines=['# PhoBERT / ViSoBERT — grouped CV phát triển','',
        f"425 nhãn người + {context['silver']} silver chưa duyệt toàn bộ. Đủ 5 fold của seed {cfg['seed']}; không phải mean 5 seed hoặc Gold Test.",
        'Mỗi fold khởi tạo lại pretrained, 3 epoch cố định; validation không dùng chọn epoch. '
        'Case được giữ; PhoBERT dùng PyVi (khác RDRSegmenter); ViSoBERT minimal. '
        f"{context['silver']} silver là snapshot khi bắt đầu; không tự đưa nhãn mới vào giữa lượt chạy.", '',
        '| Model | Điều kiện | Macro-F1 OOF | Accuracy |','|---|---|---:|---:|']
    tex=[r'\subsection{PhoBERT và ViSoBERT trên dữ liệu mở rộng}',
        f"Thực nghiệm tạm thời với 425 nhãn người và {context['silver']} silver; 5 fold của seed {cfg['seed']}. "
        'Điểm là OOF gộp trên 425 câu, không phải trung bình 5 seed. Mỗi fold khởi tạo pretrained mới và học 3 epoch cố định; không dùng Gold Test.',
        r'\begin{table}[H]\centering\begin{tabular}{llcc}\toprule Model & Điều kiện & Macro-F1 & Accuracy \\ \midrule']
    for row in comparison:
        name=row['model'];condition=row['condition'];confusion_png(output/'figures'/f'{name}_{condition}.png',row['confusion_matrix'])
        lines.append(f"| {name} | {condition} | {row['macro_f1']:.4f} | {row['accuracy']:.4f} |")
        label='Human' if condition=='human_only' else 'Human + silver'
        tex.append(f"{name} & {label} & {row['macro_f1']:.4f} & {row['accuracy']:.4f} \\\\")
    tex += [r'\bottomrule\end{tabular}\caption{Transformer: grouped OOF trên cùng 425 validation IDs, một seed cố định.}\end{table}',
            'Nhãn AI chưa được duyệt toàn bộ; chưa có independent test cho các model này. Không suy diễn rằng điểm cao hơn trên CV bảo đảm tổng quát tốt.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    (output/'section_8_bert.tex').write_text('\n'.join(tex)+'\n',encoding='utf8')
    summary=dict(status='COMPLETE_PROVISIONAL_5FOLD',human=425,silver=context['silver'],folds_per_condition=5,
                 seed=cfg['seed'],completed_fits=len(fold_scores),gold_used=False,approved_release=False,reference=context['reference'])
    save(output/'summary.json',summary);seal(output,dict(kind='TRANSFORMER_5FOLD_DEVELOPMENT',approved=False))
    return summary


def run(reference,output,config,root=ROOT):
    cfg=prepare(reference,output,config,root)
    if (Path(output)/'manifest.json').exists():return summarize(output)
    folds=load(Path(output)/'frozen/folds.json')
    tasks=[(name,condition,fold['fold'],len(fold['baseline_train_ids'] if condition=='human_only' else fold['augmented_train_ids']))
           for fold in folds for name in cfg['models'] for condition in cfg['conditions']]
    # Longer fits first; jobs are independent and every fit resets its own seed.
    tasks.sort(key=lambda t:(-t[3],t[0],t[1],t[2]))
    with ProcessPoolExecutor(max_workers=cfg['workers']) as pool:
        jobs=[pool.submit(worker,str(Path(output).resolve()),name,condition,fold) for name,condition,fold,_ in tasks]
        for job in jobs:job.result()
    return summarize(output)
