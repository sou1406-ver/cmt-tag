"""Fixed A/B/C/D on frozen Facebook folds; strict master leakage gate is mandatory."""
from collections import Counter,defaultdict,deque
from importlib.metadata import version
from pathlib import Path
import time

from src.dataset.common import ROOT,load,read_jsonl,csv_rows,save,seal,sha,staged,verify,write_csv
from src.dataset.unified import check_protection,guard
from src.dataset.master import normal
from src.dataset.common import digest
from src.baseline.core import metrics
from .preprocessing_experiments import estimator,offline_network

TRIALS=[dict(id='A',augment=False,view='original'),dict(id='B',augment=True,view='original'),
        dict(id='C',augment=False,view='basic'),dict(id='D',augment=True,view='basic')]
FIXED=dict(feature='char_wb',ngram_range=[3,5],C=1,class_weight='balanced',seed=42,extra_l2=True)


def pipeline():
    return estimator(dict(feature='char'),'svm','balanced',dict(seed=42))


def evaluate_trial(rows,plans,trial,factory=pipeline):
    by_id={r['id']:r for r in rows};folds=[p for p in plans if p['view']==trial['view']]
    if len(folds)!=3 or {p['fold'] for p in folds}!={0,1,2}:raise ValueError('Exactly the original three folds required')
    if any(p['blockers'] for p in folds):raise ValueError('Strict component preflight blocks this experiment')
    group_key='group_id' if trial['view']=='original' else 'group_id_normalized'
    field='text_view' if trial['view']=='original' else 'text_normalized'
    outputs=[];per_fold=[]
    for fold in folds:
        train=fold['fb_train_ids']+(fold['legacy_added_ids'] if trial['augment'] else [])
        valid=fold['validation_ids']
        if (set(train)&set(valid) or {by_id[i][group_key] for i in train}&{by_id[i][group_key] for i in valid}
            or any(by_id[i]['source_dataset']!='facebook_development' for i in valid)):
            raise ValueError('Train/validation leakage or legacy validation detected')
        guard([by_id[i] for i in train],'train');guard([by_id[i] for i in valid],'validation')
        model=factory();started=time.perf_counter()
        model.fit([by_id[i][field] for i in train],[by_id[i]['label'] for i in train])
        pred=model.predict([by_id[i][field] for i in valid]);elapsed=time.perf_counter()-started
        truth=[by_id[i]['label'] for i in valid]
        per_fold.append(dict(fold=fold['fold'],train_rows=len(train),validation_rows=len(valid),
            legacy_added=len(fold['legacy_added_ids']) if trial['augment'] else 0,
            legacy_excluded=fold['legacy_exclusions'] if trial['augment'] else [],
            train_counts=dict(Counter(by_id[i]['label'] for i in train)),validation_counts=fold['validation_counts'],
            seconds=elapsed,metrics=metrics(truth,pred)))
        for rid,yhat in zip(valid,pred):outputs.append(dict(experiment=trial['id'],fold=fold['fold'],id=rid,
            original_id=by_id[rid]['original_id'],human_label=by_id[rid]['label'],predicted_label=str(yhat)))
    expected={r['id'] for r in rows if r['source_dataset']=='facebook_development'}
    if len(outputs)!=len(expected) or len({p['id'] for p in outputs})!=len(expected) or {p['id'] for p in outputs}!=expected:
        raise ValueError('OOF predictions must cover every Facebook ID exactly once')
    return dict(experiment=trial['id'],metrics=metrics([p['human_label'] for p in outputs],[p['predicted_label'] for p in outputs]),folds=per_fold),outputs


def reference_reproduction(rows,locked,phase_e,reference_predictions):
    """Historical A only: reproduce E's own protocol, without certifying master leakage."""
    by_original={r['original_id']:r for r in rows if r['source_dataset']=='facebook_development'}
    outputs=[];folds=[]
    for fold in locked['folds']:
        train=[by_original[i] for i in fold['train_ids']];valid=[by_original[i] for i in fold['validation_ids']]
        guard(train,'train');guard(valid,'validation')
        model=pipeline();started=time.perf_counter()
        model.fit([r['text_view'] for r in train],[r['label'] for r in train]);pred=model.predict([r['text_view'] for r in valid])
        folds.append(dict(fold=fold['fold'],seconds=time.perf_counter()-started,metrics=metrics([r['label'] for r in valid],pred)))
        outputs.extend(dict(id=r['original_id'],fold=fold['fold'],human_label=r['label'],predicted_label=str(p)) for r,p in zip(valid,pred))
    result=dict(metrics=metrics([r['human_label'] for r in outputs],[r['predicted_label'] for r in outputs]),folds=folds)
    from .bow_robustness import validate_reference
    validate_reference(result,outputs,phase_e,reference_predictions,'B3_svm_balanced')
    return dict(status='EXACT_REFERENCE_REPRODUCED',leakage_qualified_for_master_protocol=False,
                purpose='historical_reference_only_not_new_comparison',**result),outputs


def bridge_witnesses(rows,locked,master_root):
    """Metadata/exact/near graph witnesses, with text hashes instead of private text."""
    master=read_jsonl(Path(master_root)/'master.jsonl');by_master={r['id']:r for r in master}
    by_fb={r['original_id']:r for r in rows if r['source_dataset']=='facebook_development'}
    adjacency=defaultdict(list);seen={}
    for r in master:
        keys=[(k,r['source_platform'],r[k]) for k in ('post_id','post_url','comment_id') if r[k]]
        keys.extend(('frozen_development_group','all',g) for g in r['development_groups'])
        aliases={*r['text_variants'],r['text_view'],*(d['text_raw'] for d in r['human_decisions'])}
        keys.extend(('exact_text','all',digest(normal(text))) for text in aliases if normal(text))
        for key in keys:
            if key in seen and seen[key]!=r['id']:
                left=seen[key];edge=dict(kind=key[0],identity_or_text_sha256=digest(str(key[2])))
                adjacency[left].append((r['id'],edge));adjacency[r['id']].append((left,edge))
            else:seen[key]=r['id']
    for pair in load(Path(master_root)/'near_duplicates.json'):
        left,right=pair['left_master_id'],pair['right_master_id'];edge=dict(kind='near_duplicate',score=pair['score'])
        adjacency[left].append((right,edge));adjacency[right].append((left,edge))
    output=[]
    for fold in locked['folds']:
        start={by_fb[i]['master_id']:i for i in fold['train_ids']};target={by_fb[i]['master_id']:i for i in fold['validation_ids']}
        queue=deque(sorted(start));parent={i:None for i in queue};incoming={};hit=None
        while queue:
            node=queue.popleft()
            if node in target:hit=node;break
            for other,edge in adjacency[node]:
                if other not in parent:parent[other]=node;incoming[other]=edge;queue.append(other)
        if hit is not None:
            path=[];cursor=hit
            while parent[cursor] is not None:
                path.append(dict(left=parent[cursor],right=cursor,**incoming[cursor]));cursor=parent[cursor]
            path.reverse();component=by_master[hit]['group_id']
            output.append(dict(fold=fold['fold'],train_original_id=start[cursor],validation_original_id=target[hit],
                master_component=component,master_members=sum(r['group_id']==component for r in master),path=path,
                note='Structural component bridge; not proof these two annotated texts are direct duplicates or vocabulary leakage'))
    return output


def run(config_path,output):
    cfg=load(config_path)
    if cfg['trials']!=TRIALS or cfg['model']!=FIXED or cfg['require_master_component_isolation'] is not True:
        raise ValueError('Fixed A/B/C/D, estimator and strict master-component gate must not change')
    unified=ROOT/cfg['unified'];um=verify(unified)
    if sha(unified/'manifest.json')!=cfg['unified_manifest_sha256']:raise ValueError('Unified manifest changed')
    rows=read_jsonl(unified/'unified.jsonl');plans=load(unified/'fold_plans.json');locked=load(unified/'frozen_plan.json')
    protected=load(unified/'protected_inputs.json');check_protection(protected)
    # Verify all old contracts and numerical versions, not just the displayed 0.5802.
    from .bow_robustness import inputs
    uc=load(unified/'config.json');_,old_locked,phase_e,old_cfg=inputs(load(ROOT/uc['facebook_contract']))
    if old_locked!=locked:raise ValueError('Frozen folds were modified')
    ref_rows,_=csv_rows((ROOT/'outputs/phase_e/predictions.csv').read_bytes())
    blocked=um['status']!='READY_FOR_FIXED_FOLD_ABLATION';results=[];predictions=[]
    with offline_network():
        reference,reference_oof=reference_reproduction(rows,locked,phase_e,ref_rows)
        if not blocked:
            for trial in TRIALS:
                result,pred=evaluate_trial(rows,plans,trial);results.append(result);predictions.extend(pred)
    comparisons=[]
    if results:
        scores={r['experiment']:r['metrics']['macro_f1'] for r in results}
        for name,left,right in [('augmentation_original','B','A'),('normalization_fb_only','C','A'),
                                ('normalization_augmented','D','B'),('augmentation_normalized','D','C')]:
            diff=scores[left]-scores[right];comparisons.append(dict(comparison=name,left=left,right=right,
                absolute=diff,relative=diff/scores[right] if scores[right] else None))
    with staged(output) as work:
        save(work/'reference_A.json',reference)
        write_csv(work/'reference_A_oof.csv',reference_oof,['id','fold','human_label','predicted_label'])
        save(work/'results.json',dict(status='PARTIAL' if blocked else 'COMPLETE_DEVELOPMENT_ONLY',results=results,
            comparisons=comparisons,experiment_status={t['id']:'BLOCKED_STRICT_COMPONENT_ISOLATION' if blocked else 'COMPLETED' for t in TRIALS},
            independent_test=False,reference_reproduced=True,strict_group_gate_passed=not blocked))
        save(work/'bridge_witnesses.json',bridge_witnesses(rows,locked,ROOT/uc['master']))
        save(work/'fold_audit.json',plans)
        if predictions:write_csv(work/'oof_predictions.csv',predictions,list(predictions[0]))
        save(work/'config.json',cfg);save(work/'environment.json',dict(packages={p:version(p) for p in ('scikit-learn','numpy','scipy')},
            offline=True,model=FIXED))
        check_protection(protected)
        return seal(work,dict(status='PARTIAL' if blocked else 'COMPLETE_DEVELOPMENT_ONLY',
            strict_experiment_fits=12 if not blocked else 0,historical_reference_fits=3,
            unified_manifest_sha256=sha(unified/'manifest.json'),reference_A_macro_f1=reference['metrics']['macro_f1'],
            original_artifacts_unchanged=True,independent_test=False,extended_normalization_run=False))
