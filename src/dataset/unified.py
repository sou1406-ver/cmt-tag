"""Versioned human-only data; source text, frozen folds and master components remain distinct."""
from collections import Counter,defaultdict,deque
from pathlib import Path

from .common import ROOT,csv_rows,digest,load,read_jsonl,save,seal,sha,staged,verify,write_csv,write_jsonl
from .master import normal
from .blind import assert_allowed
from src.data.quality import near_duplicate_candidates
from src.data.split import UnionFind
from src.preprocessing.normalization import BASIC,normalize,inspect,signals

LABELS={'POS','NEG','NEU'}


def protection(paths):
    result={}
    for relative in paths:
        target=ROOT/relative
        if not target.exists():raise FileNotFoundError('Required protected input: '+relative)
        values=[target] if target.is_file() else sorted(p for p in target.rglob('*') if p.is_file())
        result.update({str(p.resolve()):sha(p) for p in values})
    return result


def check_protection(snapshot):
    if any(sha(p)!=value for p,value in snapshot.items()):raise ValueError('Protected source/artifact changed')


def source_rows(cfg):
    from src.baseline.bow_robustness import inputs
    if sha(ROOT/cfg['facebook_contract'])!=cfg['facebook_contract_sha256']:raise ValueError('Facebook contract changed')
    fb_all,locked,_,_=inputs(load(ROOT/cfg['facebook_contract']))
    master=ROOT/cfg['master'];verify(master)
    if sha(master/'manifest.json')!=cfg['master_manifest_sha256']:raise ValueError('Master changed')
    records=read_jsonl(master/'master.jsonl');by_master={r['id']:r for r in records}
    fb_map={r['development_id']:r['master_id'] for r in load(master/'development_mapping.json')}
    imported=ROOT/cfg['legacy_import'];im=verify(imported)
    if sha(imported/'manifest.json')!=cfg['legacy_import_manifest_sha256']:raise ValueError('Human import changed')
    task=ROOT/cfg['legacy_task'];verify(task,mutable_files=('legacy_train_candidates.xlsx',))
    if sha(task/'manifest.json')!=cfg['legacy_task_manifest_sha256']:raise ValueError('Legacy task changed')
    receipt=load(imported/'receipt.json');contract=load(task/'coordinator/task.json')
    if (receipt['label_source']!='human_single_annotator' or receipt['legacy_labels_used'] or
        receipt['task_manifest_sha256']!=cfg['legacy_task_manifest_sha256'] or
        receipt['guideline_sha256']!=contract['guideline_sha256']):raise ValueError('Not the confirmed human annotation lineage')
    if sha(imported/'input_snapshot.xlsx')!=receipt['input_sha256']:raise ValueError('Human snapshot changed')
    from scripts.normalize_annotations import read_input
    _,before,_=read_input(imported/'input_snapshot.xlsx',text_field='text_view');before={r['id']:r for r in before}
    decisions,_=csv_rows((imported/'decisions.csv').read_bytes());history=load(imported/'history.json')
    history={r['id']:r for r in history};expected={r['id']:r for r in contract['rows']}
    if len(decisions)!=250 or len(history)!=250 or set(before)!=set(expected):raise ValueError('Human decision coverage mismatch')
    for r in decisions:
        event=history[r['id']]
        if event['before']!=before[r['id']] or event['after']!=r or r['text_view']!=expected[r['id']]['text_view']:
            raise ValueError('Human labels or source view no longer match their import history')
    legacy=[r for r in decisions if r['status']=='LABELED' and r['label'] in LABELS]
    exported,_=csv_rows((imported/'sentiment.csv').read_bytes())
    if legacy!=exported or len(legacy)!=cfg['expected_legacy']:raise ValueError('Supervised legacy rows changed')
    mapping={r['id']:r for r in load(task/'coordinator/coordinator_mapping.json')}
    fb_ids={rid for fold in locked['folds'] for rid in fold['validation_ids']}
    fb=[r for r in fb_all if r['id'] in fb_ids]
    if len(fb)!=cfg['expected_facebook']:raise ValueError('Facebook candidate count changed')
    unified=[];auxiliary=[]
    for namespace,rows in [('facebook_development',fb_all),('legacy_human',legacy)]:
        for source in rows:
            oid=source['id'];is_fb=namespace=='facebook_development'
            if is_fb:
                linked=by_master[fb_map[oid]];raw=view=source['text_raw']
                provenance=dict(annotation_input='outputs/development/reviewed/annotations.csv',
                    original_guideline_version=source['original_guideline_version'],
                    review_event_id=source.get('review_event_id',''),review_guideline_version=source.get('review_guideline_version',''),
                    reviewed_manifest_sha256=locked['dataset_manifest_sha256'])
            else:
                linked=by_master[oid];raw=mapping[oid]['text_raw'];view=source['text_view']
                if raw!=view or mapping[oid]['source_sha256']!=contract['input_source_sha256']:
                    raise ValueError('Legacy raw/view lineage mismatch')
                provenance=dict(annotation_input=cfg['legacy_import']+'/sentiment.csv',
                    import_manifest_sha256=cfg['legacy_import_manifest_sha256'],input_snapshot_sha256=receipt['input_sha256'],
                    task_manifest_sha256=cfg['legacy_task_manifest_sha256'],source_file=mapping[oid]['source_file'],
                    source_row=mapping[oid]['source_row'],source_sha256=mapping[oid]['source_sha256'],
                    guideline_version=receipt['guideline_version'],guideline_sha256=receipt['guideline_sha256'])
            aliases=sorted({raw,view,linked['text_raw'],linked['text_view'],*linked['text_variants'],
                *(d['text_raw'] for d in linked['human_decisions'])})
            row=dict(id=('fbdev::' if is_fb else 'legacyhuman::')+oid,original_id=oid,
                text_raw=raw,text_view=view,text_normalized=normalize(view,cfg['normalization']),label=source.get('label',''),
                source_dataset=namespace,annotation_source='human_single_annotator',
                platform='facebook' if is_fb else 'unknown',movie_id=source['movie_id'] if is_fb else '',
                post_id=source['post_id'] if is_fb else '',post_url=source['post_url'] if is_fb else '',
                comment_id=source['comment_id'] if is_fb else '',
                frozen_group_id=locked['group_by_id'][oid] if is_fb else '',master_id=linked['id'],master_group_id=linked['group_id'],
                alias_texts=aliases,provenance=provenance,source_raw_definition='unchanged original annotation source text; not certified raw Facebook for legacy')
            if is_fb and oid not in fb_ids:auxiliary.append(row)
            else:unified.append(row)
    if len({r['id'] for r in unified})!=len(unified):raise ValueError('Unified IDs repeated')
    if Counter(r['label'] for r in unified)!=Counter(cfg['expected_labels']):raise ValueError('Human label distribution changed')
    return unified,auxiliary,locked,records


def component_graph(rows,near_cfg,normalization_cfg,processed=False):
    """Metadata/master + all aliases + exact/near transitive closure; no labels used."""
    uf=UnionFind([r['id'] for r in rows]);seen={};texts={};owners=defaultdict(set)
    for row in rows:
        keys=[('master',row['master_group_id'])]
        if row.get('frozen_group_id'):keys.append(('frozen',row['frozen_group_id']))
        for name in ('post_id','post_url','comment_id'):
            if row.get(name):keys.append((row['platform'],name,row[name]))
        for value in row['alias_texts']:
            text=normal(normalize(value,normalization_cfg) if processed else value)
            if not text:continue
            h=digest(text);keys.append(('text',h));texts[h]=text;owners[h].add(row['id'])
        for key in keys:
            if key in seen:uf.union(row['id'],seen[key])
            else:seen[key]=row['id']
    near=near_duplicate_candidates([dict(id=h,text=t,quality=dict(status='KEEP',duplicate_of=None)) for h,t in sorted(texts.items())],near_cfg)
    for pair in near:uf.union(min(owners[pair['left']]),min(owners[pair['right']]))
    members=defaultdict(list)
    for row in rows:members[uf.find(row['id'])].append(row['id'])
    names={root:('ung_basic_' if processed else 'ung_original_')+digest('\n'.join(sorted(ids))) for root,ids in members.items()}
    return {r['id']:names[uf.find(r['id'])] for r in rows},near


def collisions(rows,field):
    groups=defaultdict(list)
    for row in rows:groups[normal(row[field])].append(row)
    return [dict(text_sha256=digest(key),ids=sorted(r['id'] for r in values),
            labels=sorted({r['label'] for r in values}),conflict=len({r['label'] for r in values})>1,
            source_datasets=sorted({r['source_dataset'] for r in values}))
            for key,values in sorted(groups.items()) if key and len(values)>1]


def fold_plans(rows,locked):
    fb={r['original_id']:r for r in rows if r['source_dataset']=='facebook_development'}
    legacy=[r for r in rows if r['source_dataset']=='legacy_human'];result=[]
    for variant,group_key,text_key in [('original','group_id','text_view'),('basic','group_id_normalized','text_normalized')]:
        dup=collisions(rows,text_key);conflict_ids={rid for c in dup if c['conflict'] for rid in c['ids']}
        for old in locked['folds']:
            train=[fb[rid] for rid in old['train_ids']];valid=[fb[rid] for rid in old['validation_ids']]
            vg={r[group_key] for r in valid};overlap=vg&{r[group_key] for r in train}
            accepted=[];excluded=[];seen={normal(r[text_key]) for r in train}
            for row in sorted(legacy,key=lambda r:r['id']):
                reasons=[]
                if row[group_key] in vg:reasons.append('CONNECTED_TO_VALIDATION')
                if row['id'] in conflict_ids:reasons.append('HUMAN_LABEL_CONFLICT_AFTER_VIEW')
                if not row[text_key]:reasons.append('EMPTY_VIEW')
                if normal(row[text_key]) in seen:reasons.append('EXACT_DUPLICATE_ALREADY_IN_TRAIN')
                if reasons:excluded.append(dict(id=row['id'],reasons=reasons))
                else:accepted.append(row['id']);seen.add(normal(row[text_key]))
            blockers=[]
            if overlap:blockers.append('FACEBOOK_FROZEN_FOLDS_INTERSECT_MASTER_OR_DUPLICATE_COMPONENTS')
            if conflict_ids & {r['id'] for r in train+valid}:blockers.append('FACEBOOK_LABEL_CONFLICT_IN_VIEW')
            result.append(dict(view=variant,fold=old['fold'],fb_train_ids=[r['id'] for r in train],validation_ids=[r['id'] for r in valid],
                legacy_added_ids=accepted,legacy_exclusions=excluded,shared_fb_components=sorted(overlap),
                shared_fb_train_rows=sum(r[group_key] in overlap for r in train),shared_fb_validation_rows=sum(r[group_key] in overlap for r in valid),
                fb_train_counts=dict(Counter(r['label'] for r in train)),validation_counts=dict(Counter(r['label'] for r in valid)),blockers=blockers))
    return result


def normalization_audit(rows):
    summary={};details=[]
    for row in rows:details.append(dict(id=row['id'],source_dataset=row['source_dataset'],text_before=row['text_view'],text_after=row['text_normalized'],**inspect(row['text_view'],row['text_normalized'])))
    for source in sorted({r['source_dataset'] for r in rows}):
        subset=[d for d in details if d['source_dataset']==source]
        summary[source]=dict(rows=len(subset),changed=sum(d['changed'] for d in subset),empty_after=sum(d['empty_after'] for d in subset),
            char_delta=sum(d['after']['characters']-d['before']['characters'] for d in subset),
            token_delta=sum(d['after']['tokens']-d['before']['tokens'] for d in subset),
            before={key:sum(d['before'][key] for d in subset) for key in ('urls','mentions','underscore_tokens','emoji_codepoints','emoji_aliases','html_entities')},
            after={key:sum(d['after'][key] for d in subset) for key in ('urls','mentions','underscore_tokens','emoji_codepoints','emoji_aliases','html_entities')},
            rows_with_url=sum(d['before']['urls']>0 for d in subset),rows_with_mention=sum(d['before']['mentions']>0 for d in subset),
            underscore_kinds=dict(sum((Counter(d['before']['underscore_kinds']) for d in subset),Counter())),
            sentiment_information_risks=sum(bool(d['sentiment_information_risks']) for d in subset))
    return summary,details


def guard(rows,purpose):
    assert_allowed(rows,purpose)
    assert_allowed([dict(r,id=r['original_id'],group_id=r['master_group_id']) for r in rows],purpose)


def build(config_path,output):
    cfg=load(config_path)
    if cfg['normalization']!=BASIC:raise ValueError('Predeclare basic_v1; extended rules cannot silently replace it')
    protected=protection(cfg['protect_paths']);rows,aux,locked,master=source_rows(cfg)
    guard(rows,'model_selection')
    original,pairs=component_graph(rows+aux,cfg['near_duplicate'],cfg['normalization'])
    processed,processed_pairs=component_graph(rows+aux,cfg['near_duplicate'],cfg['normalization'],True)
    for row in rows:row.update(group_id=original[row['id']],group_id_normalized=processed[row['id']])
    plans=fold_plans(rows,locked);summary,details=normalization_audit(rows)
    before=collisions(rows,'text_view');after=collisions(rows,'text_normalized')
    blocked=any(p['blockers'] for p in plans) or any(d['empty_after'] or d['sentiment_information_risks'] for d in details)
    with staged(output) as work:
        write_jsonl(work/'unified.jsonl',rows)
        fields=['id','text_raw','text_view','text_normalized','label','source_dataset','annotation_source','platform','movie_id','post_id','post_url',
                'comment_id','group_id','group_id_normalized','master_group_id','original_id','provenance']
        write_csv(work/'unified.csv',rows,fields)
        save(work/'frozen_plan.json',locked);save(work/'fold_plans.json',plans);save(work/'normalization_audit.json',summary)
        write_csv(work/'normalization_before_after.csv',details,['id','source_dataset','text_before','text_after','changed','before','after','empty_after','sentiment_information_risks'])
        # Representative cases use only text signals, never validation labels or outcomes.
        representative=[d for d in details if d['changed']]+[d for d in details if d['before']['underscore_tokens'] or d['before']['urls'] or d['before']['mentions'] or d['before']['emoji_aliases']]
        representative=list({d['id']:d for d in representative}.values())[:60]
        write_csv(work/'normalization_representatives.csv',representative,['id','source_dataset','text_before','text_after','before','after'])
        save(work/'duplicates.json',dict(original=before,basic=after,original_near=pairs,basic_near=processed_pairs))
        save(work/'config.json',cfg);save(work/'protected_inputs.json',protected)
        check_protection(protected)
        return seal(work,dict(status='PARTIAL_CV_BLOCKED' if blocked else 'READY_FOR_FIXED_FOLD_ABLATION',dataset_version=cfg['dataset_version'],
            rows=len(rows),input_facebook=cfg['expected_facebook'],input_legacy=cfg['expected_legacy'],labels=dict(Counter(r['label'] for r in rows)),
            supervised_eligibility='All human three-class rows retained; fold/variant gates determine safe experimental eligibility',
            blocked_fold_views=sum(bool(p['blockers']) for p in plans),source_config_sha256=sha(config_path),
            auxiliary_facebook_review_exclude_rows_used_only_for_grouping=len(aux),
            original_duplicates=len(before),basic_duplicates=len(after),basic_new_duplicates=len({tuple(c['ids']) for c in after}-{tuple(c['ids']) for c in before}),
            normalized_conflicts=sum(c['conflict'] for c in after),independent_test=False,legacy_provenance_verified=False,models_trained=False))
