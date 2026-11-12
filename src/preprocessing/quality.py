"""Narrow, opt-in tag/link decisions for future annotation/model inputs."""
import re
import unicodedata
from . import minimal_filter_text
from .model import model_view, EMOJI, EMOTICON

# Deliberately conservative bare-domain suffixes. File extensions are not TLDs.
BARE_TLDS = r'com|net|org|vn|edu|gov|io|co|tv|info|biz|me|xyz|link|online|site|store|app|ai|dev'
LABEL = r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?'
HOST = '(?:' + LABEL + r'\.)+[A-Za-z]{2,24}'
BARE = '(?:' + LABEL + r'\.)+(?:' + BARE_TLDS + ')'
TAIL = r'(?::\d{1,5})?(?:[/?#][^\s<>\[\]{}"\x27()]*)?'
URL = re.compile(r'https?://' + HOST + TAIL + r'|(?<![\w@./\\])(?:www\.' + HOST + '|' + BARE + r')(?![\w-]|\.\w)' + TAIL, re.I)
EMAIL = re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
SEPARATORS = re.compile(r'^[\s,.;:|/\\\-–—·•()\[\]{}]*$')
EXPRESSION = re.compile(EMOJI + '|' + EMOTICON + r'|\){2,}|\({2,}')
MEANING = re.compile(r'(?<!\w)(?:hay|dở|tốt|tệ|chán|đỉnh|đẹp|thích|ghét|ổn|phim|kịch bản|diễn xuất|đáng tiền|xuất sắc)(?!\w)|\d+(?:[.,]\d+)?\s*/\s*10', re.I)
AD_CUES = re.compile(r'(?<!\w)(?:mua ngay|đặt hàng|khuyến mãi|giảm giá|hotline|casino|cá cược|nhà cái)(?!\w)', re.I)
PRIORITY = ('EXCLUDE_TAG_ONLY','EXCLUDE_LINK_ONLY','POSSIBLE_LINK_SPAM','LINK_REVIEW','TAG_ONLY_REVIEW')


def url_spans(text):
    emails = [m.span() for m in EMAIL.finditer(text)]
    spans = []
    for match in URL.finditer(text):
        start, end = match.span()
        if any(start < b and end > a for a,b in emails): continue
        # Sentence punctuation belongs to the comment, never to the removed URL.
        while end > start and text[end-1] in '.,;:!?': end -= 1
        if end > start: spans.append((start,end))
    return spans


def strip_urls(text):
    parts = []; cursor = 0
    for start,end in url_spans(text):
        parts.extend((text[cursor:start], ' ')); cursor = end
    parts.append(text[cursor:])
    return ' '.join(''.join(parts).split())


def name_only_cue(text):
    """Review cue only. Never delete these words or claim a real identity."""
    if MEANING.search(text): return False
    words = text.strip().split()
    return 1 <= len(words) <= 4 and all(w.isalpha() and w[0].isupper() and
        (len(w)==1 or w[1:].islower()) for w in words)


def dom_view(row, observation=None):
    view = model_view(row, observation)
    if view['view_method'] == 'DOM_RULE_MATCH': return view
    # The locked display_text rejects empty DOM. Only extend the *empty* case:
    # a single full deletion of 1..6 name words, count >=1, pinned identities.
    if row['source_dataset'] != 'facebook' or not observation: return view
    from src.data.quality import verified_post
    if not verified_post(row): return view
    if observation.get('text_raw') != row['text_raw'] or any(
        str(observation.get(k) or '') != str(row.get(k) or '') for k in ('post_id','comment_id')): return view
    count = observation.get('mention_count')
    if isinstance(count,str) and count.isdecimal(): count = int(count)
    if type(count) is not int or count < 1 or observation.get('text_extraction_version') != 'dom_text_v2': return view
    dom = observation.get('text_without_mentions')
    if not isinstance(dom,str) or dom.strip(): return view
    words = row['text_raw'].strip().split()
    if not 1 <= len(words) <= 6: return view
    if not all(w.isalpha() and (w[0].isupper() or all('LATIN' not in unicodedata.name(c,'') for c in w)) for w in words): return view
    return dict(view, text_view='', view_method='DOM_RULE_MATCH',
                reason='SOURCE_BOUND_V2_FULL_NAME_DELETION;NOT_NODE_VERIFIED')


def quality_view(row, observation=None):
    view = dom_view(row, observation)
    # Nonempty DOM must also have valid post identity in the new quality filter.
    if view['view_method']=='DOM_RULE_MATCH':
        from src.data.quality import verified_post
        if not verified_post(row): view = model_view(row)
    text = view['text_view']; cleaned = strip_urls(text)
    # Include URL evidence from raw when a DOM link deletion already removed it.
    has_url = bool(url_spans(row['text_raw']) or url_spans(text))
    empty = bool(SEPARATORS.fullmatch(cleaned)) and not EXPRESSION.search(cleaned)
    flags = []
    if view['view_method']=='DOM_RULE_MATCH' and empty: flags.append('EXCLUDE_TAG_ONLY')
    if has_url and empty: flags.append('EXCLUDE_LINK_ONLY')
    if not empty:
        if name_only_cue(cleaned): flags.append('LINK_REVIEW' if has_url else 'TAG_ONLY_REVIEW')
        if has_url and not MEANING.search(cleaned): flags.append('LINK_REVIEW')
        if has_url and AD_CUES.search(cleaned): flags.append('POSSIBLE_LINK_SPAM')
        if view['view_method']=='DOM_RULE_MATCH' and not re.search(r'\w',cleaned) and EXPRESSION.search(cleaned):
            flags.append('TAG_ONLY_REVIEW')
    flags = [f for f in PRIORITY if f in flags]
    proposed = 'EXCLUDE' if any(f.startswith('EXCLUDE_') for f in flags) else 'REVIEW' if flags else 'KEEP'
    human = bool(row.get('human_decisions'))
    return dict(record_id=row['record_id'], text_annotation_view=row['text_minimal'] if human else cleaned,
        # text_model_input is an alias of text_annotation_view, not another stored copy.
        quality_flags=flags, quality_decision='KEEP' if human else proposed,
        quality_reason=('HUMAN_DECISION_PRESERVED;FLAG_ONLY;' if human else '')+(flags[0] if flags else 'NO_NEW_RULE_MATCH'),
        proposed_decision=proposed, view_method='RAW' if human else view['view_method'],
        view_reason='HUMAN_TEXT_PRESERVED' if human else view['reason'],
        url_count=len(url_spans(text)), has_url=has_url,
        audit_dom_view=view['text_view'], audit_after_urls=cleaned)
