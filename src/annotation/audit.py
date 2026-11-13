"""Human audit diagnostics and a disjoint friend handoff, never label approval."""
from collections import Counter,defaultdict
from pathlib import Path
import re

from src.dataset.common import ROOT,load,read_jsonl,save,seal,sha,digest,write_jsonl,write_csv,staged,verify
from .gold import _labels
from .guidelines import GUIDELINE
from .pilot import task,CATEGORIES,SENTIMENT
from .web_labels import successes
from .core import now

CUES={
    'EMOTION_POSSIBLE':r'khóc|xúc động|đồng cảm|ám ảnh|cảm động|nghẹn|tự hào',
    'NEGATION_PRESENT':r'(?<!\w)(?:không|chưa|chẳng|chả|ko|k|đéo|đếch)(?!\w)',
    'CONTRAST_POSSIBLE':r'(?<!\w)(?:nhưng|tuy|mặc dù|vừa)(?!\w)',
    'SARCASM_REVIEW_CUE':r':\)\)|=\)\)|:v|[“”"]|\.{3}',
    'PERSON_TARGET_REVIEW_CUE':r'(?<!\w)(?:bạn|ông|bà|thằng|fan|người xem|cmt|bình luận|đẹp trai|xinh gái)(?!\w)',
}


def label_error(human,ai):
    if human==ai:return 'MATCH'
    if human=='EXCLUDE' and ai in SENTIMENT:return 'AI_SENTIMENT_ON_HUMAN_EXCLUDE'
    if human in SENTIMENT and ai in ('REVIEW','EXCLUDE'):return 'AI_ABSTAIN_ON_HUMAN_SENTIMENT'
    if human=='NEU' and ai in ('POS','NEG'):return 'AI_POLARITY_ON_HUMAN_NEU'
    if human=='POS' and ai=='NEU':return 'HUMAN_POS_AS_NEU'
    if human=='NEG' and ai=='NEU':return 'HUMAN_NEG_AS_NEU'
    if {human,ai}=={'POS','NEG'}:return 'POS_NEG_REVERSAL'
    return 'OTHER_LABEL_DISAGREEMENT'


def analyze_errors(directory,output):
    directory,output=Path(directory).resolve(),Path(output).resolve()
    if not output.is_relative_to(directory):raise ValueError('Keep audit examples local under the pilot directory')
    _,_,coord=task(directory);records=read_jsonl(directory/'human_audit.local.jsonl')
    human={r['id']:r for r in records};audit=load(directory/'audit_coordinator.local.json')
    if set(human)!={r['id'] for r in audit['rows']}:raise ValueError('Human audit coverage changed')
    refs={r['id']:r for r in audit['rows']}
    if any(r['text']!=refs[r['id']]['text'] for r in records):raise ValueError('Human audit text changed')
    receipt=directory/'human_audit_receipt.local.json'
    if receipt.exists() and load(receipt)['human_decisions_sha256']!=sha(directory/'human_audit.local.jsonl'):
        raise ValueError('Human decision checksum changed')
    predictions=successes(directory);meta={r['record_id']:r for r in coord['rows']}
    rows=[];groups=defaultdict(Counter);cohort_counts=defaultdict(Counter);cues=defaultdict(Counter);triples=[]
    for rid,h in human.items():
        labels={model:predictions[(rid,model)]['predicted_label'] for model in ('GPT','Claude','Gemini')}
        unanimous=len(set(labels.values()))==1;ai=next(iter(labels.values()))
        tags=[k for k,pattern in CUES.items() if re.search(pattern,h['text'],re.I)]
        cohort='ORIGINAL_3_OF_3' if unanimous else 'ORIGINAL_DISAGREEMENT'
        if unanimous:triples.append(dict(record_id=rid,ai_label=ai,human_label=h['label'],match=ai==h['label'],
                                        ai_sentiment=ai in SENTIMENT,review_cues=tags))
        for model,pred in labels.items():
            category=label_error(h['label'],pred);groups[model][category]+=1
            cohort_counts[model+' / '+cohort][category]+=1
            if category!='MATCH':
                cues[model].update(tags)
                rows.append(dict(record_id=rid,model=model,human_label=h['label'],ai_label=pred,
                    cohort=cohort,error_type=category,review_cues=tags,
                    source=meta[rid]['source'],movie_id=meta[rid]['movie_id'],
                    text=h['text'],ai_reason=predictions[(rid,model)]['reason'],human_note=h['note'],
                    semantic_error_cause_confirmed=False))
    report=dict(n=len(human),human_labels=dict(Counter(r['label'] for r in records)),
        errors_by_model={k:dict(v) for k,v in groups.items()},errors_by_original_agreement={k:dict(v) for k,v in cohort_counts.items()},
        lexical_review_cues={k:dict(v) for k,v in cues.items()},
        unanimous=dict(audited=len(triples),matched=sum(r['match'] for r in triples),
            sentiment_audited=sum(r['ai_sentiment'] for r in triples),sentiment_matched=sum(r['ai_sentiment'] and r['match'] for r in triples),
            workflow_audited=sum(not r['ai_sentiment'] for r in triples),workflow_matched=sum(not r['ai_sentiment'] and r['match'] for r in triples)),
        sampling='50 stratified unanimous + 50 prioritized disagreements; not a population error estimate',
        limitation='Error types are label comparisons. Emotion/sarcasm/person-target tags are review cues, not validated semantic causes. AI recheck existed before human completion; prior reviewer exposure unknown.',
        human_labels_changed=False,silver_approved=False,gold_used=False)
    with staged(output) as out:
        save(out/'summary.json',report)
        write_jsonl(out/'errors.local.jsonl',rows)
        write_csv(out/'error_review.local.csv',rows,['record_id','model','human_label','ai_label','cohort','error_type','review_cues','source','movie_id','text','ai_reason','human_note','semantic_error_cause_confirmed'])
        write_csv(out/'unanimous_audit.csv',triples,['record_id','ai_label','human_label','match','ai_sentiment','review_cues'])
        confusion=[]
        for model in ('GPT','Claude','Gemini'):
            for truth in CATEGORIES:
                for pred in CATEGORIES:
                    confusion.append(dict(model=model,human_label=truth,ai_label=pred,n=sum(h['label']==truth and predictions[(rid,model)]['predicted_label']==pred for rid,h in human.items())))
        write_csv(out/'confusion_all_5_states.csv',confusion,['model','human_label','ai_label','n'])
        save(out/'inputs.json',{name:sha(directory/name) for name in ['selection_manifest.json','human_audit.local.jsonl','audit_coordinator.local.json','model_predictions.local.jsonl']})
        lines=['# Phân tích lỗi AI trên 100 câu người dùng chốt','',
            'Không sửa nhãn, không approve silver, không train hoặc dùng gold. File 350 câu đang gán không được đọc.', '',
            '| Model | Khớp / 100 | Lệch / 100 |','|---|---:|---:|']
        for model in ('GPT','Claude','Gemini'):
            n=groups[model]['MATCH'];lines.append(f'| {model} | {n} | {len(human)-n} |')
        u=report['unanimous'];lines += ['',
            f"Nhóm 3/3: {u['matched']}/{u['audited']} trùng người. Riêng sentiment: {u['sentiment_matched']}/{u['sentiment_audited']}; "
            f"REVIEW/EXCLUDE: {u['workflow_matched']}/{u['workflow_audited']}. Không gộp các nhóm này để kết luận chất lượng 184 silver candidate.", '',
            '## Dạng lệch xác nhận được từ cặp nhãn','', '```json',__import__('json').dumps(report['errors_by_model'],ensure_ascii=False,indent=2),'```','',
            'Các lệch POS/NEU, phân cực trên human NEU, hoặc AI REVIEW/EXCLUDE trên human sentiment được đếm trực tiếp. '
            'Các cue cảm xúc, phủ định, tương phản, mỉa mai, đích người bình luận chỉ dùng để mở câu kiểm tra; '
            'không coi regex/emoji là nguyên nhân được xác minh. Ví dụ và lý do đầy đủ chỉ ở errors.local.jsonl/error_review.local.csv để đọc local.', '',
            'Mẫu được chọn có chủ đích; các AI đã gán lại trước khi người hoàn thành nên không chứng minh audit mù độc lập. '
            'NEU/POS cảm xúc và ranh giới REVIEW/EXCLUDE cần ưu tiên rà theo guideline đang có, chưa sửa guideline hoặc prompt từ kết quả này.', '',
            'Đề nghị giữ riêng human labels mới, chờ 350 câu và kiểm tra nguồn gán. Đồng thuận AI vẫn là candidate; '
            'chưa đặt ngưỡng hoặc tạo silver release. Không suy rộng tỷ lệ ở đây thành hiệu năng toàn pool.']
        (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        seal(out,dict(kind='DEVELOPMENT_HUMAN_AUDIT_DIAGNOSTICS',approved=False))
    return report


def import_friend(directory,annotator,origin,workbook_path=None,output=None):
    directory=Path(directory);_,_,c=task(directory)
    bound=directory/'friend_task.local.json';coordinator=load(bound)
    if coordinator['selection_manifest_sha256']!=sha(directory/'selection_manifest.json') or coordinator['guideline_sha256']!=sha(GUIDELINE):
        raise ValueError('Friend task input/guideline changed')
    if coordinator['owner_audit_coordinator_sha256']!=sha(directory/'audit_coordinator.local.json'):raise ValueError('Owner task changed')
    refs=coordinator['rows'];ids={r['id'] for r in refs};owner={r['id'] for r in load(directory/'audit_coordinator.local.json')['rows']}
    if len(ids)!=len(refs) or ids!=set(c['unlabeled_ids'])-owner or ids&set(c['calibration_labels']):
        raise ValueError('Friend task overlaps owner/calibration or has invalid coverage')
    if origin not in ('human','human_reviewed_ai','ai') or not annotator.strip():raise ValueError('Explicit annotator and label origin required')
    source=Path(workbook_path) if workbook_path else Path(coordinator['workbook'])
    decisions=_labels(source,refs)  # Only read the workbook when explicitly importing it.
    output=(Path(output) if output else directory/'friend_import').resolve()
    if not output.is_relative_to(directory.resolve()):raise ValueError('Keep friend labels local under the pilot directory')
    context=dict(workbook_sha256=sha(source),task_sha256=sha(bound),annotator=annotator,origin=origin,
        selection_manifest_sha256=sha(directory/'selection_manifest.json'),guideline_sha256=sha(GUIDELINE))
    if output.exists():
        verify(output)
        if load(output/'receipt.json')['context']!=context:raise FileExistsError('Different friend revision/origin; choose a new output')
        return dict(already_imported=True,records=len(decisions),origin=origin)
    human=origin in ('human','human_reviewed_ai')
    records=[dict(r,annotator=annotator,annotation_origin=origin,human_confirmed=human,
        label_scope='DEVELOPMENT_HUMAN' if human else 'AI_SUGGESTION',created_at=now()) for r in decisions.values()]
    with staged(output) as out:
        write_jsonl(out/'decisions.local.jsonl',records)
        save(out/'receipt.json',dict(context=context,records=len(records),human_confirmed=human,
            labels=dict(Counter(r['label'] for r in records)),data_sha256=sha(out/'decisions.local.jsonl'),
            disjoint_owner=True,calibration_excluded=True,approved_release=False,
            note='Separate items, not inter-annotator agreement; human_reviewed_ai is not blind annotation'))
        seal(out,dict(kind='FRIEND_LABEL_IMPORT',origin=origin,approved=False))
    return dict(records=len(records),origin=origin,human_confirmed=human,approved=False,output=str(output))
