"""Transparent domain/quality proposals requiring human validation."""
import re
import unicodedata
from src.dataset.phase_i import EMOTICON, TEENCODE
from src.preprocessing.normalization import EMOJI, signals
from src.preprocessing.emoji_aliases import ALIASES

FILM=re.compile(r'(?<!\w)(?:phim|kịch[ _]bản|diễn[ _]xuất|đạo[ _]diễn|nhân[ _]vật|cảnh[ _]quay|cinema|movie|âm[ _]nhạc|nhịp[ _]phim)(?!\w)',re.I)
AD=re.compile(r'(?<!\w)(?:mua ngay|đặt hàng|liên hệ|inbox|khuyến mãi|giảm giá|hotline|freeship)(?!\w)',re.I)


def assess(row,text,repetition):
    evidence=[]
    provenance=bool(row.get('platform')=='facebook' and row.get('movie_id') and row.get('post_id'))
    film=bool(FILM.search(text)); ad=len(AD.findall(text))>=2
    if ad:domain='OFF_TOPIC_LIKELY';evidence.append('MULTIPLE_ADVERTISING_CUES_REVIEW')
    elif row.get('parent_comment_id') and len(text)<=80:domain='CONTEXT_NEEDED';evidence.append('SHORT_REPLY_NO_PARENT_TEXT')
    elif film or provenance:domain='IN_DOMAIN_LIKELY';evidence.append('FILM_CUE' if film else 'VERIFIED_FILM_POST_METADATA')
    else:domain='UNCERTAIN';evidence.append('INSUFFICIENT_DOMAIN_EVIDENCE')
    reasons=[]
    bare_alias=any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',text) for name in ALIASES)
    if bare_alias:reasons.append('BARE_EMOJI_ALIAS_REQUIRES_REVIEW')
    if domain!='IN_DOMAIN_LIKELY':reasons.extend(evidence)
    if repetition['repetition_risk']:reasons.append('REPEATED_LONG_TOKEN_BLOCKS')
    if len(text)>1000:reasons.append('LONG_TEXT_NEEDS_HUMAN_REVIEW')
    residue=EMOJI.sub('',EMOTICON.sub('',text))
    if text and not re.search(r'\w',residue):reasons.append('SYMBOL_OR_EMOJI_ONLY_CONTEXT_REQUIRED')
    if '\ufffd' in text:reasons.append('REPLACEMENT_CHARACTER')
    if re.fullmatch(r'(?:[@#][\w.]+\s*)+',text):reasons.append('MENTION_ONLY')
    status='EXCLUDE' if not text else 'REVIEW' if reasons else 'KEEP'
    scripts={}
    for c in text:
        if c.isalpha():
            script=unicodedata.name(c,'UNKNOWN').split()[0]
            scripts[script]=scripts.get(script,0)+1
    return dict(quality_status=status,domain_status=domain,domain_evidence=evidence,
        domain_method='unvalidated lexical cues and verified source metadata; no semantic classifier',
        quality_reason_code=reasons or (['EMPTY_TEXT'] if not text else []),
        exclusion_candidate_reason='STRUCTURAL_LONG_BLOCK_REPETITION' if repetition['repetition_status']=='EXCLUDE_CANDIDATE' else '',
        annotation_eligibility=status=='KEEP',script_counts=scripts,multiple_script_signal=len(scripts)>1,
        bare_alias_signal=bare_alias,
        sentence_count=len([s for s in re.split(r'[.!?]+',text) if s.strip()]),
        paragraph_count=len([s for s in row['text_raw'].splitlines() if s.strip()]),
        teencode_preserved=len(TEENCODE.findall(text)),underscore_signals=signals(text)['underscore_kinds'])
