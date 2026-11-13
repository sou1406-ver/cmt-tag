"""Prepare paired training rosters on fixed development validation; never fit."""
from collections import Counter
from pathlib import Path

from src.dataset.common import ROOT,load,read_jsonl,save,sha,digest,normal,staged,seal,verify
from src.annotation.pilot import task,fingerprints,reference_index,near_any,SENTIMENT
from src.dataset.blind import assert_allowed


def group(row):
    if row['source_dataset']=='facebook':
        from src.data.quality import verified_post
        if not verified_post(row):raise ValueError('Unverified Facebook post identity')
        return 'facebook:post:'+row['post_id']
    return 'legacy:record:'+row['record_id']


def additional_fold_rows(base,extra,plan):
    """Same held-out base population; extra rows can only augment train."""
    by_id={r['record_id']:r for r in base};new={r['record_id']:r for r in extra}
    if set(by_id)&set(new):raise ValueError('Additional labels repeat original development IDs')
    if set(plan['ids'])!=set(by_id):raise ValueError('Frozen baseline ID set changed')
    folds=[]
    for split in plan['folds']:
        seed,fold=split['seed'],split['fold']
        train=[plan['ids'][i] for i in split['train']];validation=[plan['ids'][i] for i in split['validation']]
        train_groups={group(by_id[i]) for i in train};val_groups={group(by_id[i]) for i in validation}
        if train_groups&val_groups:raise ValueError('Frozen baseline post crosses train/validation')
        references=reference_index([fingerprints(by_id[i]['text']) for i in validation])
        exact={normal(by_id[i]['text']) for i in validation}
        if any(normal(by_id[i]['text']) in exact or near_any(by_id[i]['text'],references) for i in train):
            raise ValueError('Frozen baseline has cross-fold duplicate leakage; do not repair splits silently')
        # Locate existing group assignment from this seed's original validation folds.
        known={}
        for other in plan['folds']:
            if other['seed']==seed:
                for i in other['validation']:known[group(by_id[plan['ids'][i]])]=other['fold']
        added=[];held=[];excluded=[]
        for rid,r in new.items():
            key=group(r);assigned=known.get(key,int(digest(str(seed)+'\n'+key)[:16],16)%5)
            if key in val_groups or assigned==fold:held.append(rid);continue
            if normal(r['text']) in exact or near_any(r['text'],references):excluded.append(rid);continue
            added.append(rid)
        folds.append(dict(seed=seed,fold=fold,baseline_train_ids=train,validation_ids=validation,
            augmented_train_ids=train+added,additional_train_ids=added,additional_held_ids=held,
            additional_duplicate_validation_exclusions=excluded,
            validation_support=dict(Counter(by_id[i]['label'] for i in validation)),
            baseline_train_support=dict(Counter(by_id[i]['label'] for i in train)),
            augmented_train_support=dict(Counter([by_id[i]['label'] for i in train]+[new[i]['label'] for i in added]))))
    return folds


def prepare(config,output,root=ROOT):
    root,output=Path(root).resolve(),Path(output).resolve();cfg=load(config)
    if cfg['execution_allowed'] or cfg['gold_allowed'] or cfg['silver_allowed']:raise ValueError('Planning only; no execution/gold/silver allowed')
    if not output.is_relative_to(root/'outputs'):raise ValueError('Keep label plans local under outputs/')
    baseline=root/cfg['baseline_dataset'];annotation=root/cfg['annotation_dataset'];pilot=root/cfg['pilot_directory']
    verify(baseline);verify(annotation);_,_,coordinator=task(pilot)
    by_id={r['record_id']:r for r in read_jsonl(annotation/'candidate.local.jsonl')}
    base=[dict(r,text=r['text_minimal'].lower(),label=r['human_label']) for r in read_jsonl(baseline/'candidate.local.jsonl') if r['human_label'] in SENTIMENT]
    if len(base)!=425:raise ValueError('Original 425 human sentiment records required')
    if any(by_id[r['record_id']]['text_annotation_view']!=r['text_minimal'] for r in base):
        raise ValueError('Baseline human text differs from the frozen minimal view')
    owner=read_jsonl(pilot/'human_audit.local.jsonl');receipt=load(pilot/'human_audit_receipt.local.json')
    if receipt['human_decisions_sha256']!=sha(pilot/'human_audit.local.jsonl'):raise ValueError('Owner human audit checksum mismatch')
    additions=list(owner);friend=root/cfg['friend_import'];friend_status='PENDING_UNREAD_WORKBOOK';friend_count=0
    assignment=pilot/'friend_assignment_status.json'
    returned=assignment.exists() and load(assignment)['status']=='RETURNED_TO_UNLABELED'
    if returned:friend_status='RETURNED_TO_UNLABELED'
    if friend.exists() and not returned:
        verify(friend);r=load(friend/'receipt.json')
        if r['data_sha256']!=sha(friend/'decisions.local.jsonl'):raise ValueError('Friend data checksum mismatch')
        if r['human_confirmed']:
            rows=read_jsonl(friend/'decisions.local.jsonl')
            if any(not d['human_confirmed'] or d['annotation_origin'] not in ('human','human_reviewed_ai') for d in rows):raise ValueError('Friend origin mismatch')
            additions+=rows;friend_count=len(rows);friend_status='IMPORTED_HUMAN'
        else:friend_status='AI_SUGGESTIONS_NOT_TRAINING_LABELS'
    allowed=set(coordinator['unlabeled_ids']);seen=set();extra=[]
    for d in additions:
        rid=d['id']
        if rid in seen or rid not in allowed or rid in coordinator['calibration_labels']:raise ValueError('New human/calibration IDs overlap')
        seen.add(rid)
        if d['text']!=by_id[rid]['text_annotation_view']:raise ValueError('Human text differs from labelled annotation view')
        if d['label'] in SENTIMENT:extra.append(dict(by_id[rid],text=d['text'].lower(),label=d['label']))
    assert_allowed([dict(r,id=r['record_id'],text_view=r['text']) for r in base+extra],'model_selection',
        reservation_root=root/'outputs/phase_g/blind_test',registry=root/'data/test_reservations')
    frozen=root/cfg['baseline_fold_file'];plan=load(frozen)['all_human'];folds=additional_fold_rows(base,extra,plan)
    if {f['seed'] for f in folds}!=set(cfg['seeds']) or len(folds)!=cfg['n_splits']*len(cfg['seeds']):
        raise ValueError('Frozen fold schedule differs from the configured 5x5 design')
    summary=dict(status='PLAN_ONLY_NOT_TRAINED',baseline=425,additional_human_sentiment=len(extra),augmented_known=425+len(extra),
        additional_statuses=dict(Counter(r['label'] for r in additions)),friend_status=friend_status,friend_imported=friend_count,
        pending_friend_assignment=len(load(pilot/'friend_task.local.json')['rows']) if friend_status=='PENDING_UNREAD_WORKBOOK' else 0,
        folds=len(folds),seeds=sorted({f['seed'] for f in folds}),shared_validation_ids=True,
        legacy_note='79 baseline legacy record groups do not guarantee post independence',
        fit_called=False,predict_called=False,approved_release=False,gold_used=False,silver_used=False)
    inputs={str(p):sha(p) for p in [Path(config),baseline/'manifest.json',annotation/'manifest.json',frozen,
        pilot/'human_audit.local.jsonl',pilot/'human_audit_receipt.local.json',pilot/'selection_manifest.json']}
    if friend.exists():inputs.update({str(p):sha(p) for p in [friend/'receipt.json',friend/'decisions.local.jsonl']})
    if assignment.exists():inputs[str(assignment)]=sha(assignment)
    with staged(output) as out:
        save(out/'summary.json',summary);save(out/'config.json',cfg);save(out/'folds.local.json',folds)
        save(out/'inputs.json',inputs)
        from .preprocessing_cv import estimator
        for name in cfg['models']:
            actual=estimator(name,20261113).named_steps['model'].get_params()
            if any(actual.get(k)!=v for k,v in cfg['model_parameters'][name].items()):raise ValueError('Declared model parameters differ from fixed implementation')
        vectorizers={name:{k:estimator(name,20261113).named_steps['vectorizer'].get_params()[k] for k in ['analyzer','token_pattern','lowercase','ngram_range']} for name in cfg['models']}
        save(out/'vectorizers.json',vectorizers)
        lines=['# Kế hoạch CV nhãn người — chưa chạy','',
            f"Baseline 425; thêm {len(extra)} nhãn sentiment người đã có, tổng biết {425+len(extra)}. Trạng thái phân công bạn: {friend_status}; không đọc workbook cũ trong bước chuẩn bị.", '',
            'Giữ đúng 25 fold (5 fold × 5 seed) của baseline hiện có. Mỗi cặp baseline/augmented đánh giá trên cùng validation IDs thuộc 425 nhãn cũ. '
            'Augmented chỉ thêm nhãn mới vào train khi post không thuộc validation; record của post mới có fold theo hash seed/group, không dựa nhãn. '
            'Không so điểm tuyệt đối trên hai validation population khác nhau.', '',
            'Dữ liệu thêm có post ở validation hoặc trùng exact/near validation không vào train fold đó. '
            'Nếu baseline đã có leakage thì dừng kế hoạch, không thay split cũ. '
            'Legacy vẫn là record group riêng, không bảo đảm chống leakage theo bài.', '',
            'Text baseline: immutable text_minimal.lower(); text mới: đúng text_annotation_view mà người gán đã đọc, lowercase. '
            'Không PyVi hay rule mới trong primary comparison; sai khác view giữa nguồn là giới hạn cần báo. '
            'BoW + ComplementNB / word TF-IDF + balanced LinearSVC / char_wb (3,5) + balanced LinearSVC theo cấu hình đã định. '
            'Word token_pattern r"(?u)[^\\s]+", lowercase=False trong vectorizer. Fit vectorizer chỉ train khi được phép chạy sau này.', '',
            'Nếu có nhãn người mới từ một task hợp lệ thì tạo kế hoạch output mới. '
            'Không nhập nhãn AI-only hoặc 150 calibration lần hai. REVIEW/EXCLUDE giữ lịch sử và ngoài sentiment training. '
            'Chưa approve release, không fit/predict, không metrics giả, không gold evaluation.']
        (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Plan inputs changed')
        seal(out,dict(kind='HUMAN_EXPANSION_PLAN_ONLY',execution_allowed=False))
    return summary
