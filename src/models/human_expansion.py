"""Paired development plans and explicitly authorized provisional silver CV."""
from collections import Counter
from pathlib import Path

from src.dataset.common import ROOT,load,read_jsonl,save,sha,digest,normal,staged,seal,verify
from src.annotation.pilot import task,fingerprints,reference_index,near_any,SENTIMENT
from src.dataset.blind import assert_allowed


def consensus_rows(items,predictions,calibration_ids=()):
    """Never ignore an available dissenting third vote or invent missing votes."""
    from src.annotation.web_labels import SLOTS
    result=[]
    for row in items:
        rid=row['record_id']
        if rid in calibration_ids:continue
        providers=[p for p in SLOTS if (rid,p) in predictions]
        values=[predictions[(rid,p)]['predicted_label'] for p in providers]
        if len(providers)>=2 and len(set(values))==1 and values[0] in SENTIMENT:
            result.append(dict(record_id=rid,text=row['text'].lower(),label=values[0],
                               providers=providers,label_origin='PROVISIONAL_AI_CONSENSUS',human_confirmed=False))
    return result


def cv_estimator(name,seed):
    from .preprocessing_cv import estimator
    if name=='bow_multinomial_nb':
        from sklearn.naive_bayes import MultinomialNB
        model=estimator('bow_complement_nb',seed)
        return model.set_params(model=MultinomialNB(alpha=1.0))
    return estimator(name,seed)


def run_silver_cv(config,output,root=ROOT,emit=print):
    """Fixed same-425 validation, exploratory only; normal release guards untouched."""
    from collections import defaultdict
    from statistics import mean,stdev
    import time
    from .core import metrics,confusion_png,LABELS
    from .preprocessing_cv import snapshot
    from src.dataset.common import write_csv,write_jsonl
    from src.annotation.web_labels import successes,SLOTS
    root,output=Path(root).resolve(),Path(output).resolve();cfg=load(config)
    if not cfg['allow_unapproved_silver_for_exploratory_cv'] or cfg['gold_allowed'] or cfg['approved_release']:
        raise ValueError('Explicit provisional-only protocol required; no gold or approved release')
    if cfg['n_splits']!=5 or cfg['silver_weight']!=1.0:raise ValueError('Fixed 5-fold/unit-weight protocol required')
    if not output.is_relative_to(root/'outputs'):raise ValueError('Keep results local under outputs/')
    if output.exists():raise FileExistsError('Immutable experiment exists; choose a new output')
    source=root/cfg['baseline_dataset'];annotation=root/cfg['annotation_dataset'];frozen=root/cfg['baseline_fold_file']
    verify(source);verify(annotation);before=snapshot(root,source)
    inputs={str(p):sha(p) for p in [Path(config),source/'manifest.json',annotation/'manifest.json',frozen]}
    by_id={r['record_id']:r for r in read_jsonl(annotation/'candidate.local.jsonl')}
    base=[dict(r,text=r['text_minimal'].lower(),label=r['human_label']) for r in read_jsonl(source/'candidate.local.jsonl')
          if r['human_label'] in SENTIMENT]
    if len(base)!=425:raise ValueError('Exactly original 425 human sentiment labels required')
    if any(by_id[r['record_id']]['text_annotation_view']!=r['text_minimal'] for r in base):raise ValueError('Baseline view changed')
    extra=[];batch_report=[];prediction_payloads={}
    for batch in sorted((root/cfg['expansion_directory']).glob('batch_*')):
        m,items,c=task(batch);pred=successes(batch)
        for filename in ('selection_manifest.json','pilot_input.local.jsonl','coordinator.local.json','model_predictions.local.jsonl'):
            p=batch/filename
            if p.exists():inputs[str(p)]=sha(p)
        if (batch/'model_predictions.local.jsonl').exists():
            payload=(batch/'model_predictions.local.jsonl').read_bytes()
            if digest(payload)!=inputs[str(batch/'model_predictions.local.jsonl')]:raise ValueError('Journal changed while reading')
            prediction_payloads[batch.name]=payload
        inputs.update(m['source_sha256'])
        selected=consensus_rows(items,pred,set(c['calibration_labels']))
        for row in selected:
            original=by_id[row['record_id']]
            if original['text_annotation_view'].lower()!=row['text'] or original.get('human_decisions'):
                raise ValueError('Silver text/human-decision conflict')
            if original['quality_decision']!='KEEP':raise ValueError('Silver quality is not KEEP')
            extra.append(dict(original,**row))
        batch_report.append(dict(batch=batch.name,records=len(items),
            providers={p:sum(slot==p for rid,slot in pred) for p in SLOTS},selected=len(selected),
            selected_labels=dict(Counter(r['label'] for r in selected))))
    if not extra or len({r['record_id'] for r in extra})!=len(extra):raise ValueError('Empty or duplicate silver selection')
    assert_allowed([dict(r,id=r['record_id'],text_view=r['text']) for r in base+extra],'model_selection',
        reservation_root=root/'outputs/phase_g/blind_test',registry=root/'data/test_reservations')
    plan=load(frozen)['all_human'];folds=additional_fold_rows(base,extra,plan)
    if len(folds)!=5*len(cfg['seeds']) or {f['seed'] for f in folds}!=set(cfg['seeds']):raise ValueError('Frozen fold schedule changed')
    lookup={r['record_id']:r for r in base+extra};base_by_id={r['record_id']:r for r in base}
    oof=[];fold_scores=[];seed_scores=[];error_groups=[];started=time.perf_counter()
    with staged(output) as out:
        save(out/'config.json',cfg);save(out/'inputs.json',inputs);save(out/'folds.local.json',folds)
        (out/'prediction_snapshots').mkdir()
        for name,payload in prediction_payloads.items():(out/'prediction_snapshots'/(name+'.local.jsonl')).write_bytes(payload)
        save(out/'selection.local.json',dict(batches=batch_report,silver=[{k:r[k] for k in
            ('record_id','label','providers','label_origin','human_confirmed')} for r in extra]))
        (out/'figures').mkdir()
        for name in cfg['models']:
            for condition,key in [('human_only','baseline_train_ids'),('human_plus_silver','augmented_train_ids')]:
                for seed in cfg['seeds']:
                    truth=[];predicted=[];seen=set();elapsed=0.
                    for fold in [f for f in folds if f['seed']==seed]:
                        tr=fold[key];va=fold['validation_ids'];model=cv_estimator(name,seed)
                        tick=time.perf_counter();model.fit([lookup[i]['text'] for i in tr],[lookup[i]['label'] for i in tr])
                        p=model.predict([lookup[i]['text'] for i in va]).tolist();elapsed+=time.perf_counter()-tick
                        y=[lookup[i]['label'] for i in va];score=metrics(y,p)
                        fold_scores.append(dict(model=name,condition=condition,seed=seed,fold=fold['fold'],
                            train=len(tr),validation=len(va),silver_train=len(tr)-len(fold['baseline_train_ids']),**score))
                        if seen&set(va):raise ValueError('OOF ID repeated in seed')
                        seen.update(va);truth+=y;predicted+=p
                        oof.extend(dict(model=name,condition=condition,seed=seed,record_id=i,true_label=t,predicted_label=v)
                                   for i,t,v in zip(va,y,p))
                    if seen!=set(base_by_id):raise ValueError('OOF coverage differs from frozen human validation')
                    score=metrics(truth,predicted)
                    seed_scores.append(dict(model=name,condition=condition,seed=seed,elapsed_seconds=elapsed,**score))
                    if seed==cfg['seeds'][0]:confusion_png(out/'figures'/f'{name}_{condition}.png',score['confusion_matrix'])
                    emit(f'{name} {condition} seed={seed}: macro-F1={score["macro_f1"]:.4f}',flush=True)
        comparison=[];paired=[]
        for name in cfg['models']:
            for condition in ('human_only','human_plus_silver'):
                scores=[s for s in seed_scores if s['model']==name and s['condition']==condition]
                entry=dict(model=name,condition=condition)
                for metric in ('macro_f1','accuracy','macro_precision','macro_recall'):
                    values=[s[metric] for s in scores];entry[metric+'_mean']=mean(values);entry[metric+'_std']=stdev(values) if len(values)>1 else 0.
                for label in LABELS:
                    for metric in ('precision','recall','f1-score'):entry[label+'_'+metric]=mean(s['per_class'][label][metric] for s in scores)
                comparison.append(entry)
            differences=[next(s for s in seed_scores if s['model']==name and s['condition']=='human_plus_silver' and s['seed']==seed)['macro_f1']-
                         next(s for s in seed_scores if s['model']==name and s['condition']=='human_only' and s['seed']==seed)['macro_f1'] for seed in cfg['seeds']]
            paired.append(dict(model=name,delta_mean=mean(differences),delta_std=stdev(differences) if len(differences)>1 else 0.,
                               positive_seeds=sum(d>0 for d in differences),seed_deltas=differences))
        for (name,condition,seed,field,value),records in _error_groups(oof,base_by_id).items():
            error_groups.append(dict(model=name,condition=condition,seed=seed,field=field,value=value,
                support=len(records),errors=sum(r['true_label']!=r['predicted_label'] for r in records)))
        for filename,data in [('comparison.csv',comparison),('paired_deltas.csv',paired),('fold_results.csv',fold_scores),
                              ('seed_results.csv',seed_scores),('by_movie_source_class.csv',error_groups)]:
            write_csv(out/filename,data,list(data[0]))
        write_jsonl(out/'oof_predictions.local.jsonl',oof)
        summary=dict(status='PROVISIONAL_DEVELOPMENT_RESULTS',human=425,silver=len(extra),
            human_labels=dict(Counter(r['label'] for r in base)),silver_labels=dict(Counter(r['label'] for r in extra)),
            silver_consensus_sizes=dict(Counter(len(r['providers']) for r in extra)),batches=batch_report,
            folds=len(folds),seeds=cfg['seeds'],fits=len(fold_scores),elapsed_seconds=time.perf_counter()-started,
            gold_used=False,approved_release=False,legacy_record_groups=sum(r['source_dataset']!='facebook' for r in base),
            silver_train_min=min(len(f['additional_train_ids']) for f in folds),silver_train_max=max(len(f['additional_train_ids']) for f in folds))
        save(out/'summary.json',summary)
        _silver_report(out,summary,comparison,paired)
        if snapshot(root,source)!=before or any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Experiment input changed; no result published')
        save(out/'immutability.json',dict(verified=True,files=before));seal(out,dict(kind='PROVISIONAL_DEVELOPMENT_CV',approved=False))
    return summary


def _error_groups(oof,by_id):
    from collections import defaultdict
    groups=defaultdict(list)
    for r in oof:
        source=by_id[r['record_id']]
        for field,value in [('source',source['source_dataset']),('movie_id',source.get('movie_id') or 'UNKNOWN'),('true_label',r['true_label'])]:
            groups[(r['model'],r['condition'],r['seed'],field,value)].append(r)
    return groups


def _silver_report(out,summary,comparison,paired):
    title=r'\section{HUẤN LUYỆN VÀ ĐÁNH GIÁ MÔ HÌNH SAU MỞ RỘNG NHÃN}'+'\n'+r'\label{sec:expanded-training}'+'\n'
    description=(f"Đây là thực nghiệm phát triển tạm thời trên 425 nhãn người và {summary['silver']} nhãn AI đồng thuận chưa được duyệt toàn bộ. "
        'Không phải kết quả Gold Test hay bộ dữ liệu đã phê duyệt. '
        'Batch có hai AI cần cả hai đồng ý; có ba AI cần cả ba đồng ý; không dùng nhãn một AI. '
        'Các batch chưa đủ phản hồi được giữ ngoài tập silver. ')
    protocol=('Giữ nguyên 5 fold theo nhóm bài đăng với 5 seed đã khóa; human-only và human+silver dùng đúng cùng validation IDs thuộc 425 nhãn người. '
        'Silver chỉ thêm vào train khi post và exact/near duplicate không chạm validation. '
        f"{summary['legacy_record_groups']} legacy có group riêng theo record, không bảo đảm độc lập theo bài. "
        'Text là minimal/annotation view lowercase; word tokenization theo khoảng trắng, giữ token một ký tự; char-wb 3--5. '
        'Vectorizer chỉ fit train từng fold. NB alpha=1; SVM C=1, balanced; không tune. '
        'Mean và sample std tính trên 5 OOF seed, không coi 25 fold là các quan sát độc lập. ')
    lines=['# Mục 8 — thực nghiệm tạm thời','',description,'',protocol,'',
           '| Model | Điều kiện | Macro-F1 mean ± std | Accuracy mean |','|---|---|---:|---:|']
    tex=[title,r'\noindent\textit{Số liệu tạm thời; quá trình gán nhãn chưa hoàn tất.}',
         r'\subsection{Tập huấn luyện và giao thức kiểm định}',description,protocol,
         f"Tập silver có {summary['silver_consensus_sizes'].get(2,0)} câu đồng thuận hai AI và {summary['silver_consensus_sizes'].get(3,0)} câu đồng thuận ba AI. "
         f"Nhãn người POS/NEG/NEU lần lượt: {summary['human_labels'].get('POS',0)}/{summary['human_labels'].get('NEG',0)}/{summary['human_labels'].get('NEU',0)}. "
         f"Silver POS/NEG/NEU: {summary['silver_labels'].get('POS',0)}/{summary['silver_labels'].get('NEG',0)}/{summary['silver_labels'].get('NEU',0)}. "
         f"Mỗi fold chỉ thêm {summary['silver_train_min']}--{summary['silver_train_max']} câu silver sau khi giữ riêng nhóm validation.",
         r'\subsection{So sánh human-only và human + silver}',r'\begin{table}[H]\centering\small',
         r'\begin{tabular}{llcccc}\toprule Mô hình & Điều kiện & Macro-P & Macro-R & Macro-F1 $\pm$ std & Acc. \\ \midrule']
    names={'bow_multinomial_nb':'BoW + MNB','bow_complement_nb':'BoW + CNB','tfidf_word_svm':'TF-IDF word + SVM','tfidf_char_svm':'TF-IDF char + SVM'}
    for r in comparison:
        condition='Human' if r['condition']=='human_only' else 'Human + silver'
        lines.append(f"| {names[r['model']]} | {condition} | {r['macro_f1_mean']:.4f} ± {r['macro_f1_std']:.4f} | {r['accuracy_mean']:.4f} |")
        tex.append(f"{names[r['model']]} & {condition} & {r['macro_precision_mean']:.4f} & {r['macro_recall_mean']:.4f} & ${r['macro_f1_mean']:.4f} \\pm {r['macro_f1_std']:.4f}$ & {r['accuracy_mean']:.4f} \\\\")
    tex += [r'\bottomrule\end{tabular}',r'\caption{Grouped CV tạm thời trên cùng 425 nhãn validation người; không phải Gold Test.}\end{table}']
    lines+=['','## Chênh lệch theo seed','']+[f"- {names[r['model']]}: delta Macro-F1 {r['delta_mean']:+.4f} ± {r['delta_std']:.4f}; tăng ở {r['positive_seeds']}/5 seed." for r in paired]
    limitations=('Nhãn AI có thể sai đồng thời; tập silver được chọn theo đồng thuận và nguồn phản hồi sẵn có, không đại diện ngẫu nhiên. '
        'Đồng thuận không phải ground truth. Mẫu người ít và phân bố theo phim không đều; số liệu chỉ mang tính thăm dò, không chứng minh hiệu năng ngoài miền. '
        'Không chạy lại Gold Test, không thay preprocessing, guideline hay split. PhoBERT/ViSoBERT demo chưa được đánh giá trong thí nghiệm mở rộng này.')
    tex += [r'\subsection{Phân tích lỗi của mô hình mở rộng}',r'\begin{table}[H]\centering\small',
            r'\begin{tabular}{llccc}\toprule Mô hình & Điều kiện & Recall POS & Recall NEG & Recall NEU \\ \midrule']
    for r in comparison:
        condition='Human' if r['condition']=='human_only' else 'Human + silver'
        tex.append(f"{names[r['model']]} & {condition} & {r['POS_recall']:.4f} & {r['NEG_recall']:.4f} & {r['NEU_recall']:.4f} \\\\")
    word={r['condition']:r for r in comparison if r['model']=='tfidf_word_svm'}
    error_note=''
    if len(word)==2:
        a,b=word['human_only'],word['human_plus_silver']
        error_note=(f"Với TF-IDF word + SVM, recall POS thay đổi {a['POS_recall']:.4f} lên {b['POS_recall']:.4f}, "
                    f"NEU từ {a['NEU_recall']:.4f} lên {b['NEU_recall']:.4f}, "
                    f"NEG từ {a['NEG_recall']:.4f} lên {b['NEG_recall']:.4f}. "
                    'Cần xem từng lớp thay vì chỉ điểm tổng; tăng Macro-F1 không bảo đảm mọi lớp đều cải thiện.')
    tex += [r'\bottomrule\end{tabular}\caption{Recall từng lớp trung bình trên 5 OOF seed.}\end{table}',error_note,
        'Precision, recall, F1 từng lớp có trong comparison.csv; ma trận nhầm lẫn của seed cố định đầu tiên và kết quả từng seed/fold được xuất riêng. '
        r'Không chọn seed đẹp nhất. Phân tích lỗi theo nhãn, phim và nguồn được lưu trong by\_movie\_source\_class.csv.',limitations]
    lines += ['',limitations,'','comparison.csv: Macro P/R/F1, Accuracy và P/R/F1 từng lớp. '
              'seed_results.csv và fold_results.csv chứa confusion matrix mọi lần; figures/ là seed đầu tiên. '
              'oof_predictions.local.jsonl giữ ID và dự đoán, không dùng nội dung gold.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    (out/'section_8.tex').write_text('\n'.join(tex)+'\n',encoding='utf8')


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
