"""Evidence-bound v3.2 candidate. Frozen v3.1 is composed, never mutated."""
import json
import re
import unicodedata
from collections import Counter
from .final_normalization import normalize as v31
from .plain_text_v3 import NAME_PARTS
from .plain_text import VIETNAMESE
from src.dataset.common import ROOT,load,digest
from src.crawler.parser import post_id as parse_post

VERSION='plain_text_v3_2'
TOKENIZER='nfc_case_sensitive_lowercase_latin_standalone_v1'
PROTECTED=re.compile(r'```[\s\S]*?```|`[^`]*`|https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?<!\w)#[\w.]+|(?<!\w)@[\w.]+|(?<!\w)(?:-_-|\^_\^|T_T|\._\.|>_<)(?!\w)|\b[A-Za-z_]\w*(?:\.\w+)+\b')
COMPOUND=re.compile(r'(?<![\w/@#])\w+(?:_\w+)+(?!\w)',re.UNICODE)
WORD=re.compile(r'(?<!\w)[^\W_]+(?!\w)',re.UNICODE)
MENTION=re.compile(r'@[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*\Z')
ALIAS=re.compile(r'(?<![\w/@#])(?::\s*([a-z][a-z0-9_&+’-]*)\s*:|([a-z][a-z0-9]*(?:_[a-z0-9]+)+))(?!\w)')


def segments(text):
    cursor=0
    for m in PROTECTED.finditer(text):
        if m.start()>cursor:yield False,text[cursor:m.start()],cursor
        yield True,m[0],m.start();cursor=m.end()
    if cursor<len(text):yield False,text[cursor:],cursor


def latin_word(value):
    return (value.isalpha() and value.islower() and 1<=len(value)<=7 and
            all(unicodedata.name(c,'').startswith('LATIN ') for c in value))


def token_evidence(rows,blocked,minimum=5):
    """Count distinct identities AND distinct exact comments, never occurrences."""
    counts=Counter();seen_text=set();seen_ids=set();used=[]
    for r in sorted(rows,key=lambda x:x['record_id']):
        if r['record_id'] in blocked or r['source_dataset']!='facebook':continue
        if not str(r.get('comment_id','')).isdigit() or not verified_post(r):continue
        key=(r['post_id'],r['comment_id']);text=unicodedata.normalize('NFC',r['text_raw'])
        textkey=' '.join(text.split()).casefold()
        if key in seen_ids or textkey in seen_text:continue
        seen_ids.add(key);seen_text.add(textkey);used.append(r['record_id'])
        words={m[0] for protected,s,_ in segments(text) if not protected for m in WORD.finditer(s) if latin_word(m[0])}
        counts.update(words)
    vocab={k:v for k,v in sorted(counts.items()) if v>=minimum}
    return dict(tokenizer=TOKENIZER,minimum_distinct_comments=minimum,case_policy='NFC, case-sensitive; lowercase Latin alphabetic 1..7 only',
        frequencies=dict(sorted(counts.items())),vocabulary=vocab,used_ids=used,distinct_comments=len(used),
        vocabulary_sha256=digest(json.dumps(vocab,ensure_ascii=False,sort_keys=True)),
        warning='Frequency/Latin shape is evidence heuristic, not a Vietnamese language validator')


def verified_post(r):
    try:return bool(r.get('post_id')) and parse_post(r.get('post_url',''))==r['post_id']
    except (ValueError,TypeError):return False


def select_dom(record,candidates):
    """No name guessing. Changed DOM requires exact, attested mention deletion spans.

    A paired dom_text_v2 export without spans proves a proposed view, but does
    not prove which deleted characters were linked mentions. It fails closed.
    """
    if record['source_dataset']!='facebook':return record['text_raw'],[],[]
    flags=set();valid=[];audit=[]
    variants={record['text_raw'],*record.get('source_text_variants',[])}
    for c in candidates:
        reason=None
        if not c.get('checksum_verified'):reason='DOM_SOURCE_MISMATCH'
        elif not str(record.get('comment_id','')).isdigit() or not verified_post(record):reason='DOM_SOURCE_MISMATCH'
        elif c.get('comment_id')!=record['comment_id'] or c.get('post_id')!=record['post_id'] or not verified_post(c):reason='DOM_SOURCE_MISMATCH'
        elif c.get('text_extraction_version')!='dom_text_v2':reason='DOM_EVIDENCE_MISSING'
        elif c.get('text_raw') not in variants or c.get('text_raw')!=record['text_raw']:reason='DOM_CONTENT_MISMATCH'
        elif not isinstance(c.get('text_without_mentions'),str):reason='DOM_EVIDENCE_MISSING'
        else:
            raw=c['text_raw'];clean=c['text_without_mentions'];spans=c.get('removed_mention_spans',[])
            if raw!=clean:
                # The original journals currently lack these spans: never invent them.
                if not isinstance(spans,list) or not spans:reason='DOM_EVIDENCE_MISSING'
                elif any(not isinstance(s,dict) or type(s.get('start')) is not int or type(s.get('end')) is not int for s in spans):reason='DOM_CONTENT_MISMATCH'
                else:
                    ordered=sorted(spans,key=lambda s:s['start']);cursor=0;parts=[]
                    for s in ordered:
                        start,end=s.get('start'),s.get('end')
                        if (type(start) is not int or type(end) is not int or not cursor<=start<end<=len(raw)
                            or raw[start:end]!=s.get('text') or not account_href(s.get('href',''))):reason='DOM_CONTENT_MISMATCH';break
                        parts.extend([raw[cursor:start]]);cursor=end
                    if not reason:
                        parts.append(raw[cursor:]);rebuilt=''.join(parts)
                        rebuilt=re.sub(r'^[\s,:;–—-]+','',rebuilt);rebuilt=re.sub(r'[ \t]{2,}',' ',rebuilt).rstrip()
                        if rebuilt!=clean or str(c.get('mention_count',''))!=str(len(spans)):reason='DOM_CONTENT_MISMATCH'
            elif str(c.get('mention_count',0))!='0':reason='DOM_CONTENT_MISMATCH'
        audit.append(dict(source_file=c.get('source_file'),source_sha256=c.get('source_sha256'),source_row=c.get('source_row'),
            comment_id=c.get('comment_id'),post_id=c.get('post_id'),raw_sha256=digest(c.get('text_raw','')),
            dom_sha256=digest(c.get('text_without_mentions','')),status=reason or 'VALID'))
        if reason:flags.add(reason)
        else:valid.append(c)
    if not candidates:flags.add('DOM_EVIDENCE_MISSING')
    if len({c['text_without_mentions'] for c in valid})>1:flags.add('DOM_CONFLICT');valid=[]
    if not valid:return record['text_raw'],sorted(flags),audit
    chosen=valid[0]
    return chosen['text_without_mentions'],sorted(flags),audit


def account_href(href):
    from urllib.parse import urlsplit,parse_qs
    try:
        p=urlsplit(href)
        if p.scheme!='https' or p.hostname not in {'facebook.com','www.facebook.com'}:return False
        if p.username or p.password:return False
        if any(k in parse_qs(p.query) for k in ('comment_id','reply_comment_id')):return False
        if p.path.endswith('.php'):return p.path=='/profile.php' and str(parse_qs(p.query).get('id',[''])[0]).isdigit()
        return bool(
            re.fullmatch(r'/(?:people/[^/]+/\d+|groups/\d+/user/\d+)/?',p.path) or
            re.fullmatch(r'/(?!(?:photo|photos|watch|reel|reels|groups|events|pages|hashtag|share|stories|login|help|marketplace)/?$)[A-Za-z0-9.]+/?',p.path))
    except ValueError:return False


def aliases_resource():
    r=load(ROOT/'configs/emoji_aliases_v3_2.json')
    if digest(json.dumps(r['aliases'],ensure_ascii=False,sort_keys=True,separators=(',',':')))!=r['mapping_sha256']:raise ValueError('Emoji mapping checksum mismatch')
    return r


def _pass(raw,source,accepted_tokens,evidence,abbreviations,aliases):
    events=[];flags=set();remaining=[];masks={}
    def mask(s):
        key='QZXVTHREETWOPROTECT'+str(len(masks))+'ZXQ'
        if key in raw:raise ValueError('Reserved v3.2 placeholder collision')
        masks[key]=s;return key
    def event(rule,before,after,offset,stage='v3.2 input spans'):
        events.append(dict(rule=rule,before=before,after=after,stage_offset=offset,stage=stage,status='FIX_PROPOSED'))
    def process(s,offset):
        def alias(m):
            name=m[1] or m[2];value=aliases.get(name)
            if value is None:
                if name.endswith(('_face','_eyes','_heart','_hearts','_sweat')):flags.add('UNMATCHED_ALIAS_REVIEW')
                return m[0]
            delimited=m[1] is not None
            context=(source=='legacy_29k_unverified' and bool(VIETNAMESE.search(raw))
                and not re.search(r'(?:=|\b(?:var|const|def|class|return)\s)',s))
            if not delimited and not context:
                flags.add('BARE_ALIAS_AMBIGUOUS');return mask(m[0])
            event('PINNED_EMOJI_ALIAS',m[0],value,offset+m.start());return mask(value)
        value=ALIAS.sub(alias,s)
        def guard(m):
            token=m[0];parts=token.split('_');why=None
            if any(c.isdigit() for c in token):why='DIGIT_IDENTIFIER'
            elif any(c.isupper() for c in token) or all(p in NAME_PARTS|{'hà','akira','yui'} for p in parts):why='POSSIBLE_NAME'
            elif not 2<=len(parts)<=4 or not all(latin_word(p) for p in parts):why='TOKEN_SHAPE'
            elif not any(ord(c)>127 for c in token):why='ASCII_IDENTIFIER_AMBIGUOUS'
            if why:
                remaining.append(dict(token=token,reason=why));flags.add('UNDERSCORE_'+why)
                return mask(token)
            return token
        # Preserve technical/name spans, but do not undo frozen lexical recovery.
        return COMPOUND.sub(guard,value)
    parts=[]
    for protected,s,offset in segments(unicodedata.normalize('NFC',raw)):
        if protected:
            if s.startswith('@') and MENTION.fullmatch(s):event('TECHNICAL_AT_MENTION',s,'',offset);parts.append(' ')
            else:parts.append(mask(s))
        else:parts.append(process(s,offset))
    result=v31(''.join(parts),accepted_tokens=accepted_tokens,source=source,abbreviations=abbreviations)
    text=result['text_normalized']
    def recover_residual(m):
        token=m[0];parts=token.split('_')
        if source!='legacy_29k_unverified':return token
        if all(p in evidence for p in parts):
            replacement=token.replace('_',' ')
            event('FB_DISTINCT_TOKEN_EVIDENCE',token,replacement,m.start(),'v3.2 residual after v3.1');return replacement
        remaining.append(dict(token=token,reason='INSUFFICIENT_FB_EVIDENCE'));flags.add('UNDERSCORE_INSUFFICIENT_FB_EVIDENCE');return token
    text=COMPOUND.sub(recover_residual,text)
    for key,s in masks.items():text=text.replace(key,s)
    for e in result['normalization_events']:
        e=dict(e,stage='preserved v3.1 components')
        for field in ('before','after'):
            if isinstance(e.get(field),str):
                for key,s in masks.items():e[field]=e[field].replace(key,s)
        events.append(e)
    flags.update(result['normalization_flags'])
    # Diagnostics only; no automatic exclusion or sentiment assignment.
    semantic=re.sub(r'(?<!\w)(?:-_-|\^_\^|T_T|\._\.|>_<)(?!\w)','',text)
    if not any(c.isalpha() for c in semantic) and not re.fullmatch(r'\s*\d+(?:[.,]\d+)?\s*/\s*\d+(?:[.,]\d+)?\s*',text):flags.add('NON_TEXT_REVIEW')
    return dict(text_normalized=text,text_normalized_v3_2=text,preprocessing_version=VERSION,
        transform_events=events,normalization_flags=sorted(flags),unresolved_underscore=remaining,
        normalization_approval='PENDING_HUMAN_NORMALIZATION_APPROVAL')


def normalize(raw,source='unknown',accepted_tokens=(),evidence_tokens=(),abbreviations=None,aliases=None):
    if not isinstance(raw,str):raise TypeError('Raw must be literal string')
    aliases=aliases_resource()['aliases'] if aliases is None else aliases
    current=raw;events=[];flags=set()
    for n in range(4):
        result=_pass(current,source,accepted_tokens,set(evidence_tokens),abbreviations,aliases)
        events.extend(dict(e,pipeline_pass=n+1) for e in result['transform_events']);flags.update(result['normalization_flags'])
        if result['text_normalized']==current:
            result.update(transform_events=events,normalization_flags=sorted(flags));return result
        current=result['text_normalized']
    raise ValueError('v3.2 did not reach text fixed point')
