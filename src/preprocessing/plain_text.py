"""Raw-to-plain view with explicit lexical evidence and protected regions."""
import difflib
import html
import re
import unicodedata
from src.dataset.common import ROOT,load
from .emoji_aliases import ALIASES

VERSION='plain_text_v1'
LEXICON=set(load(ROOT/'configs/plain_text_lexicon_v1.json')['compounds'].split())
PROTECTED=re.compile(r'```[\s\S]*?```|`[^`]*`|https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|(?<!\w)[@#][\w.]+')
TOKEN=re.compile(r'(?<![\w:/@#])(?::[a-z][a-z_]*:|[\w]+(?:_[\w]+)+)(?![\w:/])',re.UNICODE)
ENTITY=re.compile(r'&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]+);')
VIETNAMESE=re.compile(r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]|\b(?:phim|hay|khong|không|quá)\b',re.I)


def preprocess(raw):
    if not isinstance(raw,str):raise TypeError('Raw must be literal string')
    events=[];counts={};unknown=[]
    def count(kind):counts[kind]=counts.get(kind,0)+1
    def transform(segment,offset):
        nfc=unicodedata.normalize('NFC',segment)
        control=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]','',nfc)
        decoded=control
        while True:
            value=ENTITY.sub(lambda m:html.unescape(m[0]),decoded)
            if value==decoded:break
            decoded=value
        if segment!=decoded:events.append(dict(rule='NFC_CONTROL_HTML',raw_offset=offset,before=segment,after=decoded))
        def token_replace(m):
            token=m[0];bare=token.strip(':'); replacement=None;rule=None
            if bare in ALIASES:
                count('emoji_alias')
                if token.startswith(':') or VIETNAMESE.search(raw):replacement=ALIASES[bare];rule='VERIFIED_EMOJI_ALIAS'
                else:unknown.append(token);count('ambiguous_alias')
            elif token.casefold() in LEXICON:
                count('vietnamese_segmentation');replacement=token.replace('_',' ');rule='REVIEWED_COMPOUND_RESTORATION'
            elif any(c.isdigit() for c in token):count('identifier_protected')
            else:count('unknown');unknown.append(token)
            if replacement is not None:
                events.append(dict(rule=rule,stage_offset=m.start(),raw_segment_offset=offset,before=token,after=replacement))
                return replacement
            return token
        replaced=TOKEN.sub(token_replace,decoded)
        spaced=re.sub(r'\s+',' ',replaced)
        if spaced!=replaced:events.append(dict(rule='WHITESPACE',raw_segment_offset=offset,before=replaced,after=spaced))
        return spaced
    pieces=[];start=0
    for m in PROTECTED.finditer(raw):
        pieces.append(transform(raw[start:m.start()],start));pieces.append(m[0])
        token=m[0]
        if '_' in token:
            kind='code' if token.startswith('`') else 'url' if token.startswith(('http','www.')) else 'hashtag' if token.startswith('#') else 'mention' if token.startswith('@') else 'email'
            count(kind+'_protected')
        start=m.end()
    pieces.append(transform(raw[start:],start));text=''.join(pieces).strip()
    if ''.join(pieces)!=text:events.append(dict(rule='TRIM_EDGES',before=''.join(pieces),after=text))
    return dict(text_clean=text,text_annotation=text,preprocessing_version=VERSION,transform_events=events,
        underscore_audit=counts,unresolved_tokens=unknown)
