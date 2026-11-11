"""Raw-derived recovery with explicit source/model/shape evidence categories."""
import re
import unicodedata
from .plain_text import preprocess as basic,PROTECTED,TOKEN,VIETNAMESE
from .emoji_aliases import ALIASES

VERSION='plain_text_v3'
ALIASES3={**ALIASES,'smiling_face_with_smiling_eyes':'😊','thinking_face':'🤔',
    'slightly_smiling_face':'🙂','face_blowing_a_kiss':'😘','grinning_face':'😀',
    'smiling_face_with_sunglasses':'😎','folded_hands':'🙏','thumbs_up':'👍'}
NAME_PARTS=set('nguyễn trần lê phạm hoàng huỳnh phan vũ võ đặng bùi đỗ hồ ngô dương lý trấn thành anh minh thanh tuấn phúc huy linh nam lan hùng'.split())


def shape(token):
    parts=token.split('_')
    if any(c.isdigit() for c in token) or not all(p.isalpha() for p in parts):return 'PROTECTED_IDENTIFIER'
    if any(c.isupper() for c in token) or all(p in NAME_PARTS for p in parts):return 'AMBIGUOUS_NEEDS_REVIEW'
    if not 2<=len(parts)<=4 or any(not 1<=len(p)<=7 for p in parts):return 'UNKNOWN_PRESERVED'
    if not any(ord(c)>127 for c in token):return 'UNKNOWN_PRESERVED'
    if not all(unicodedata.name(c,'').startswith('LATIN ') for p in parts for c in p):return 'UNKNOWN_PRESERVED'
    return 'ROUNDTRIP_CANDIDATE'


def preprocess(raw,accepted_tokens=(),source_key='',source_sha='',verified_sources=()):
    masks={};mask_events=[]
    def mask_segment(value,offset):
        def mask(m):
            if shape(m[0])!='AMBIGUOUS_NEEDS_REVIEW':return m[0]
            key='ZXQFORMATPROTECTED'+str(len(masks))+'QXZ'
            if key in raw:raise ValueError('Reserved recovery placeholder collision')
            masks[key]=m[0];mask_events.append(dict(source_token=m[0],result=m[0],rule='PRESERVE_POSSIBLE_NAME',
                evidence='Uppercase components or common name-shaped components',confidence_category='AMBIGUOUS_NEEDS_REVIEW',raw_offset=offset+m.start()))
            return key
        return TOKEN.sub(mask,value)
    masked=[];cursor=0
    for p in PROTECTED.finditer(raw):masked.extend([mask_segment(raw[cursor:p.start()],cursor),p[0]]);cursor=p.end()
    masked.append(mask_segment(raw[cursor:],cursor))
    result=basic(''.join(masked));text=result['text_clean'];events=result['transform_events'];evidence=[];unresolved=[]
    for e in events:
        if 'raw_offset' in e:e['masked_input_offset']=e.pop('raw_offset')
        if 'raw_segment_offset' in e:e['masked_segment_offset']=e.pop('raw_segment_offset')
        e['confidence_category']='RESTORED_HIGH_CONFIDENCE'
        e['evidence']='I.2 reviewed lexical/technical rule, retained in raw-to-plain v3'
    verified=any(s.get('source_key')==source_key and s.get('sha256')==source_sha and source_sha and
                 s.get('format')=='word_segmentation' and s.get('evidence') for s in verified_sources)
    def segment(value,offset):
        def sub(m):
            token=m[0];bare=token.strip(':');category=shape(bare);replacement=None;rule='PRESERVE_UNKNOWN'
            why='Insufficient format evidence'
            if bare in ALIASES3:
                if token.startswith(':') or VIETNAMESE.search(raw):
                    replacement=ALIASES3[bare];category='RESTORED_HIGH_CONFIDENCE';rule='CLDR_ALIAS_V3';why='Exact known alias and Vietnamese context or colon syntax'
                else:category='AMBIGUOUS_NEEDS_REVIEW';why='Bare alias without serialization context'
            elif category not in ('PROTECTED_IDENTIFIER','AMBIGUOUS_NEEDS_REVIEW'):
                if verified:
                    replacement=token.replace('_',' ');category='RESTORED_VERIFIED_SOURCE';rule='ATTESTED_SOURCE_SEGMENTATION';why='Checksum-bound source format attestation'
                elif category=='ROUNDTRIP_CANDIDATE' and token in accepted_tokens:
                    replacement=token.replace('_',' ');category='RESTORED_HIGH_CONFIDENCE';rule='LOCAL_SEGMENTER_ROUNDTRIP';why='Lowercase accented Vietnamese-shaped parts and underthesea 8.3.0 exact roundtrip'
                else:category='UNKNOWN_PRESERVED'
            record=dict(source_token=token,result=replacement or token,rule=rule,evidence=why,
                        confidence_category=category,stage_offset=offset+m.start())
            evidence.append(record)
            if replacement is not None:events.append(dict(record,before=token,after=replacement));return replacement
            if category!='PROTECTED_IDENTIFIER':unresolved.append(token)
            return token
        return TOKEN.sub(sub,value)
    pieces=[];start=0
    for m in PROTECTED.finditer(text):
        pieces.extend([segment(text[start:m.start()],start),m[0]])
        if '_' in m[0]:evidence.append(dict(source_token=m[0],result=m[0],rule='PROTECTED_REGION',evidence='URL/email/hashtag/mention/code',confidence_category='PROTECTED_IDENTIFIER',stage_offset=m.start()))
        start=m.end()
    pieces.append(segment(text[start:],start));clean=''.join(pieces)
    for key,value in masks.items():
        clean=clean.replace(key,value)
        for event in events:
            for field in ('before','after'):
                if field in event:event[field]=event[field].replace(key,value)
    evidence.extend(mask_events);unresolved.extend(e['source_token'] for e in mask_events)
    result.update(text_clean=clean,text_annotation=clean,preprocessing_version=VERSION,
        format_evidence=evidence,unresolved_tokens=unresolved,format_status='NEEDS_REVIEW' if unresolved else 'PLAIN_OR_PROTECTED')
    return result
