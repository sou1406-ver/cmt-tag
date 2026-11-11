"""Focused raw-derived v3.1 proposals; annotation approval is never inferred."""
import html
import html.entities
import re
import unicodedata
from src.dataset.common import ROOT,load
from .plain_text import PROTECTED,TOKEN,VIETNAMESE,LEXICON
from .plain_text_v3 import preprocess as plain_v3,shape

VERSION='plain_text_v3_1'
ABBREVIATIONS=load(ROOT/'configs/abbreviations_v3_1.json')
FUNCTION_WORDS=set('không chưa chẳng đừng đã đang sẽ rất quá cũng vẫn thì là mà và của với cho về ở này ấy đó những các một gì nào có được'.split())
SPLIT_ENTITY=re.compile(r'&\s*(?:amp\s*;\s*)*(?:quot|amp|lt|gt|apos|#\s*(?:39|34))\s*;')
MISSING_SEMICOLON=re.compile(r'&(?:quot|apos|amp|lt|gt)(?=$|\s|[.,!?])')
ENTITY=re.compile(r'&(?:amp;)*(?:[A-Za-z][A-Za-z0-9]*|#[xX][0-9a-fA-F]+|#[0-9]+);')
EXTRA_PROTECTED=re.compile(r'```[\s\S]*?```|`[^`]*`|https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?<!\w)[@#][\w.]+|"[^"\n]*"|(?<!\w)\x27[^\x27\n]*\x27(?!\w)|“[^”\n]*”|‘[^’\n]*’|«[^»\n]*»|(?<!\w)\d+(?:\s*[./:-]\s*\d+)+(?!\w)|(?::[-]?\)+|=[-]?\)+|:\(+|:v)|[.!?]{2,}|\b[A-Za-z_]\w*(?:\.\w+)+\b')
WORD=re.compile(r'(?<!\w)[^\W_]+(?!\w)',re.UNICODE)
TECHNICAL=re.compile(PROTECTED.pattern+r'|(?<!\w)\d+(?:\s*[./:-]\s*\d+)+(?!\w)|\b[A-Za-z_]\w*(?:\.\w+)+\b')


def _once(value):
    if value.startswith('&amp;'):return '&'+value[5:]
    if not value.startswith('&') or not value.endswith(';'):return value
    name=value[1:-1]
    if name+';' in html.entities.html5:return html.unescape(value)
    if name.startswith('#'):
        try:code=int(name[2:],16) if name[1:2].lower()=='x' else int(name[1:])
        except ValueError:return value
        if code in (34,38,39,60,62,160,8216,8217,8220,8221):return chr(code)
    return value


def _pass(raw,accepted_tokens=(),source='unknown',abbreviations=None,max_decode_passes=4):
    cfg=ABBREVIATIONS if abbreviations is None else abbreviations
    if type(max_decode_passes) is not int or max_decode_passes<1:raise ValueError('Positive decode limit required')
    events=[];flags=[];masks={};accepted_tokens=set(accepted_tokens)
    def event(rule,before,after,offset,stage):
        if before!=after:events.append(dict(rule=rule,before=before,after=after,stage=stage,stage_offset=offset,confidence_category='HIGH_CONFIDENCE_PROPOSAL'))
    def mask(value):
        key='QZXFINALPROTECT'+str(len(masks))+'ZXQ'
        if key in raw:raise ValueError('Reserved placeholder collision')
        masks[key]=value;return key
    def decode_segment(segment,offset):
        def repair(m):
            result=re.sub(r'\s+','',m[0]);event('HTML_SPLIT_REPAIR',m[0],result,offset+m.start(),'raw entity repair');return result
        value=SPLIT_ENTITY.sub(repair,segment)
        def close(m):
            result=m[0]+';';event('HTML_MISSING_SEMICOLON',m[0],result,offset+m.start(),'entity repair');return result
        value=MISSING_SEMICOLON.sub(close,value)
        def decode(m):
            original=current=m[0]
            for _ in range(max_decode_passes):
                decoded=_once(current)
                if decoded==current:break
                current=decoded
            if _once(current)!=current:
                flags.append('ENTITY_DEPTH_LIMIT_PRESERVED');return mask(original)
            event('HTML_DECODE',original,current,offset+m.start(),'bounded entity decode')
            if ENTITY.fullmatch(current):flags.append('UNKNOWN_ENTITY_PRESERVED');return mask(current)
            return current
        return ENTITY.sub(decode,value)
    chunks=[];cursor=0
    for m in TECHNICAL.finditer(raw):chunks.extend([decode_segment(raw[cursor:m.start()],cursor),mask(m[0])]);cursor=m.end()
    chunks.append(decode_segment(raw[cursor:],cursor));entity_view=''.join(chunks)
    base=plain_v3(entity_view,accepted_tokens);text=base['text_clean']
    inherited=[dict(e,stage='raw-derived v3 component after entity repair') for e in base['transform_events']]
    events=inherited+events
    known_segments=accepted_tokens|LEXICON
    segmented_context=len({m[0] for m in TOKEN.finditer(entity_view) if m[0] in known_segments})>=2
    vi_context=bool(VIETNAMESE.search(unicodedata.normalize('NFC',entity_view)))
    unbalanced_quote=(text.count('"')%2!=0 or text.count('“')!=text.count('”') or text.count('‘')!=text.count('’') or text.count('«')!=text.count('»'))
    if unbalanced_quote:flags.append('UNBALANCED_QUOTE_CONTEXT_PRESERVED')
    def patch_segment(value,offset):
        if unbalanced_quote:return value
        def recover(m):
            token=m[0];replacement=None;rule=None
            if vi_context and token=='con_gái':replacement='con gái';rule='USER_CONFIRMED_COMPOUND'
            elif source=='legacy_29k_unverified' and segmented_context and shape(token)=='ROUNDTRIP_CANDIDATE' and any(p in FUNCTION_WORDS for p in token.split('_')):
                replacement=token.replace('_',' ');rule='FUNCTION_WORD_SEGMENT_RECOVERY'
            if replacement is None:return token
            event(rule,token,replacement,offset+m.start(),'additional whole-token format recovery');return replacement
        value=TOKEN.sub(recover,value)
        def abbreviate(m):
            token=m[0]
            if token in cfg['auto'] and cfg['enabled']['auto'] and source in cfg['auto_sources'] and vi_context:
                replacement=cfg['auto'][token];event('ABBREVIATION_'+token,token,replacement,offset+m.start(),'contextual abbreviation');return replacement
            if cfg['enabled']['review_flags'] and (token in cfg['review_only'] or token in cfg['auto']):flags.append('AMBIGUOUS_ABBREVIATION_'+token)
            return token
        value=WORD.sub(abbreviate,value)
        def punct(m):event('PUNCTUATION_SPACE',m[0],m[1],offset+m.start(),'single-punctuation spacing');return m[1]
        return re.sub(r'\s+([,.!?;:])',punct,value)
    pieces=[];cursor=0
    for m in EXTRA_PROTECTED.finditer(text):pieces.extend([patch_segment(text[cursor:m.start()],cursor),m[0]]);cursor=m.end()
    pieces.append(patch_segment(text[cursor:],cursor));normalized=''.join(pieces)
    for key,value in masks.items():
        normalized=normalized.replace(key,value)
        for e in events:
            for field in ('before','after'):
                if field in e:e[field]=e[field].replace(key,value)
    remaining=[];cursor=0
    for m in EXTRA_PROTECTED.finditer(normalized):
        remaining.extend(t[0] for t in TOKEN.finditer(normalized[cursor:m.start()]) if shape(t[0])!='PROTECTED_IDENTIFIER');cursor=m.end()
    remaining.extend(t[0] for t in TOKEN.finditer(normalized[cursor:]) if shape(t[0])!='PROTECTED_IDENTIFIER')
    return dict(text_normalized=normalized,normalization_version=VERSION,normalization_events=events,
                normalization_flags=sorted(set(flags)),remaining_format_tokens=remaining,
                normalization_approval='PENDING_HUMAN_NORMALIZATION_APPROVAL')


def normalize(raw,accepted_tokens=(),source='unknown',abbreviations=None,max_decode_passes=4):
    current=raw;events=[];flags=set()
    for pass_number in range(1,5):
        result=_pass(current,accepted_tokens,source,abbreviations,max_decode_passes)
        events.extend(dict(e,pipeline_pass=pass_number) for e in result['normalization_events'])
        flags.update(result['normalization_flags'])
        if result['text_normalized']==current:
            result.update(normalization_events=events,normalization_flags=sorted(flags));return result
        current=result['text_normalized']
    raise ValueError('Normalization did not reach a fixed point; refuse unstable output')
