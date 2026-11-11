"""Future checksum-bound freeze/release gates. Not run during pending Phase J."""
from collections import Counter
from .common import ROOT,load,read_jsonl,sha,digest,verify,staged,save,seal,write_jsonl,write_csv,csv_rows
from .phase_i3 import held
from .blind import assert_allowed


def write_blind_files(output,rows):
    """Writer used only after release guards; tests may exercise with fixtures."""
    blind=[dict(id=r['record_id'],text_annotation=r['text_annotation']) for r in rows]
    for provider in ('codex','claude','gemini'):write_csv(output/f'{provider}_input.csv',blind,['id','text_annotation'])
    checks={provider:sha(output/f'{provider}_input.csv') for provider in ('codex','claude','gemini')}
    if len(set(checks.values()))!=1:raise AssertionError('Blind input bytes differ')
    return checks


def freeze(source,imports,approval_path,output):
    """Require actual complete human imports and explicit scoped pool approval."""
    verify(source);approval=load(approval_path);contract=load(source/'contract.json')
    flags=('approved','normalization_issues_resolved','format_delta_resolved','domain_spam_quality_accepted','quality_holdout_accepted','sample_to_pool_limitations_accepted')
    if any(approval.get(k) is not True for k in flags) or not approval.get('reviewer') or not approval.get('approved_at'):
        raise ValueError('Explicit human freeze approval with issue resolution required')
    if approval.get('source_manifest_sha256')!=sha(source/'manifest.json') or approval.get('contract_sha256')!=sha(source/'contract.json'):
        raise ValueError('Freeze approval/source checksum mismatch')
    if not contract['isolation_ok']:raise ValueError('Quality holdout isolation unresolved')
    if sha(ROOT/'src/preprocessing/final_normalization.py')!=contract['normalizer_sha256'] or sha(ROOT/'configs/abbreviations_v3_1.json')!=contract['rule_table_sha256']:
        raise ValueError('Normalization contract changed')
    if set(imports)!={'format','normalization','domain','holdout'}:raise ValueError('Four real human imports required')
    for name,path in imports.items():
        m=verify(path)
        if approval.get(name+'_import_manifest_sha256')!=sha(path/'manifest.json'):raise ValueError('Import approval checksum mismatch')
        expected_status={'format':'HUMAN_FORMAT_REVIEW_IMPORTED','normalization':'HUMAN_NORMALIZATION_REVIEW_IMPORTED_NOT_CORPUS_APPROVAL','domain':'HUMAN_QUALITY_REVIEW_IMPORTED','holdout':'HUMAN_QUALITY_REVIEW_IMPORTED'}[name]
        if m['status']!=expected_status or m['rows']!={'format':200,'normalization':150,'domain':200,'holdout':40}[name]:raise ValueError('Incomplete/wrong review import')
        if name in ('domain','holdout'):
            if m['kind']!=('development' if name=='domain' else 'holdout') or m['source_manifest_sha256']!=contract['source_manifest_sha256']:raise ValueError('Quality import source/kind mismatch')
            coordinator=source/('semantic_review_input.local.json' if name=='domain' else 'holdout_input.local.json')
            if m['coordinator_sha256']!=sha(coordinator):raise ValueError('Quality import coordinator mismatch')
        elif name=='normalization':
            cfg=load(source/'config.json')
            if m['coordinator_sha256']!=sha(ROOT/cfg['normalization_coordinator']):raise ValueError('Normalization review version mismatch')
        elif name=='format':
            cfg=load(source/'config.json')
            if m['coordinator_sha256']!=sha(ROOT/cfg['format_coordinator']):raise ValueError('Format review version mismatch')
    # Delta resolution and sampled-to-pool acceptance are explicit decisions, never inferred from ACCEPT counts.
    if approval.get('review_delta_sha256')!=sha(source/'review_delta.local.csv'):raise ValueError('Unresolved/unbound version delta')
    evidence=approval.get('quality_holdout_evaluation')
    if not evidence:raise ValueError('Quality holdout evaluation required')
    evaluation=ROOT/evidence;em=verify(evaluation)
    if em.get('kind')!='holdout' or em.get('import_manifest_sha256')!=sha(imports['holdout']/'manifest.json') or em.get('contract_sha256')!=sha(source/'contract.json'):
        raise ValueError('Holdout evaluation not tied to this frozen rule contract')
    ids=approval.get('approved_record_ids',[])
    if not ids or len(set(ids))!=len(ids):raise ValueError('Explicit unique approved pool IDs required')
    corpus={r['record_id']:r for r in read_jsonl(source/'quality_proposals.local.jsonl')};selected=[]
    sources=approval.get('approved_sources',[])
    for rid in ids:
        r=corpus[rid]
        if r['annotation_eligibility']!='ELIGIBLE_PROPOSED' or r['human_decisions'] or held(r) or r['source_dataset'] not in sources:raise ValueError('Approved ID outside guarded proposal pool')
        if r['source_dataset']=='legacy_29k_unverified' and approval.get('legacy_provenance_limitations_accepted') is not True:raise ValueError('Legacy provenance unresolved')
        item=dict(r,annotation_eligibility='ELIGIBLE_APPROVED',text_annotation=r['text_normalized'],annotation_text_version='plain_text_v3_1',
                  quality_approval_basis='EXPLICIT_CHECKSUM_BOUND_POOL_APPROVAL_NOT_PER_ROW_HUMAN_DOMAIN_LABEL')
        selected.append(item)
    assert_allowed([dict(r,id=r['record_id'],group_id=r['master_group_id']) for r in selected],'pseudo_labeling')
    with staged(output) as out:
        write_jsonl(out/'approved_annotation_pool.local.jsonl',selected);save(out/'approval.local.json',approval);save(out/'contract.json',contract)
        return seal(out,dict(status='DATASET_FROZEN_FOR_ANNOTATION',rows=len(selected),source_manifest_sha256=sha(source/'manifest.json'),approval_sha256=sha(approval_path),
            guideline_sha256=contract['guideline_sha256'],sampled_quality_does_not_supply_per_record_human_labels=True))


def export(frozen,source,candidate_path,approval_path,output):
    m=verify(frozen);verify(source);approval=load(approval_path)
    if m.get('status')!='DATASET_FROZEN_FOR_ANNOTATION' or m['source_manifest_sha256']!=sha(source/'manifest.json'):raise ValueError('Real matching frozen corpus required')
    if approval.get('approved') is not True or not approval.get('reviewer') or not approval.get('approved_at'):raise ValueError('Explicit pilot approval required')
    if approval.get('candidate_sha256')!=sha(candidate_path) or approval.get('frozen_manifest_sha256')!=sha(frozen/'manifest.json'):raise ValueError('Pilot approval checksum mismatch')
    candidates,fields=csv_rows(candidate_path.read_bytes())
    if fields!=['id','text_annotation'] or len(candidates)!=500 or len({r['id'] for r in candidates})!=500:raise ValueError('Exact 500-row blind schema required')
    corpus={r['record_id']:r for r in read_jsonl(frozen/'approved_annotation_pool.local.jsonl')};selected=[]
    for c in candidates:
        r=corpus[c['id']]
        if r['annotation_eligibility']!='ELIGIBLE_APPROVED' or r['text_annotation']!=c['text_annotation'] or r['human_decisions'] or held(r):raise ValueError('Ineligible/changed candidate')
        selected.append(r)
    # Recheck normalized exact/direct-near rather than relying on old I.3 groups.
    if len({digest(r['text_annotation'].casefold()) for r in selected})!=500:raise ValueError('Exact duplicates in pilot')
    ids={r['record_id'] for r in selected};cfg=load(source/'config.json')
    edges,_=csv_rows((ROOT/cfg['source']/'direct_near_normalized.local.csv').read_bytes())
    old_edges,_=csv_rows((ROOT/'outputs/phase_i3/v3/direct_near_duplicates.local.csv').read_bytes());edges+=old_edges
    if any(e['left'] in ids and e['right'] in ids for e in edges):raise ValueError('Direct near duplicates in pilot')
    assert_allowed([dict(r,id=r['record_id'],group_id=r['master_group_id']) for r in selected],'pseudo_labeling')
    with staged(output) as out:
        hashes=write_blind_files(out,selected)
        return seal(out,dict(status='HUMAN_APPROVED_PILOT_EXPORTED',rows=500,sha256=hashes,guideline_sha256=m['guideline_sha256'],approval_sha256=sha(approval_path),
            source_distribution=dict(Counter(r['source_dataset'] for r in selected)),agreement_interpretation='silver, never gold'))
