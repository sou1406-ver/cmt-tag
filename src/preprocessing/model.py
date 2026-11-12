"""Opt-in development model views. Never replace the immutable minimal view."""
import re
from dataclasses import dataclass
from . import minimal_filter_text

TEENCODE = {'ko': 'không', 'k0': 'không', 'khong': 'không', 'hok': 'không',
            'hông': 'không', 'khum': 'không', 'đc': 'được', 'cx': 'cũng'}
# Context-limited mn only; not a general-purpose Vietnamese disambiguator.
MN_NEXT = {'ơi', 'xem', 'thấy', 'nghĩ', 'cảm', 'đừng', 'hãy', 'có', 'nên', 'đều'}
WORD = re.compile(r'\w+', re.UNICODE)
EMOTICON = r':\):\)|(?::|;|=)(?:-|\^)?(?:\)+|\(+|[vVpPdD/\\])|-_-|\^\^|<3'
EMOJI_BASE = r'(?:[0-9#*]\ufe0f?\u20e3|[\U0001f1e6-\U0001f1ff]{2}|[\U0001f000-\U0001faff\u2600-\u27bf])'
EMOJI = EMOJI_BASE + r'[\ufe0e\ufe0f\U0001f3fb-\U0001f3ff\U000e0020-\U000e007f]*(?:\u200d' + EMOJI_BASE + r'[\ufe0e\ufe0f\U0001f3fb-\U0001f3ff]*)*'
PROTECTED = re.compile(r'https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|' + EMOTICON + '|' + EMOJI)


class ModelText(str):
    """Marks an already processed value; prevents accidental double PyVi."""


@dataclass(frozen=True)
class ModelOptions:
    teencode: bool = True
    elongation: bool = True
    punctuation: bool = True
    segment: bool = True


def normalize_teencode(text):
    def replace(match):
        token = match[0]
        if token == 'mn':
            following = re.match(r'\s+(\w+)', text[match.end():])
            return 'mọi người' if following and following[1] in MN_NEXT else token
        return TEENCODE.get(token, token)
    return WORD.sub(replace, text)


def reduce_elongation(text):
    # The literal repeated-letter rule is an ablation, not a spelling correction.
    return re.sub(r'([^\W\d_])\1{2,}', r'\1', text, flags=re.UNICODE)


def text_model(text, options=ModelOptions()):
    if isinstance(text, ModelText):
        raise ValueError('Already a model view; start from the original text_view')
    if not isinstance(text, str):
        raise TypeError('Model preprocessing requires a string')
    base = minimal_filter_text(text)
    def transform(part):
        part = part.lower()
        if options.teencode: part = normalize_teencode(part)
        if options.elongation: part = reduce_elongation(part)
        if options.punctuation: part = re.sub(r'([^\w\s])', r' \1 ', part)
        part = ' '.join(part.split())
        if options.segment and part:
            from pyvi import ViTokenizer
            part = ViTokenizer.tokenize(part)
        return part
    # Segment ordinary spans separately: protected symbols never enter PyVi,
    # lowercasing, elongation, punctuation splitting or placeholder restoration.
    parts = []; cursor = 0
    for match in PROTECTED.finditer(base):
        parts.extend([transform(base[cursor:match.start()]), match[0]])
        cursor = match.end()
    parts.append(transform(base[cursor:]))
    return ModelText(' '.join(part for part in parts if part))


def model_view(row, observation=None):
    """Conservative DOM-rule view for future train AND annotation use.

    dom_text_v2 reports aggregate account-link deletions, not node evidence.
    A successful check is DOM_RULE_MATCH, never VERIFIED_DOM_VIEW.
    The caller must checksum-bind an observation to the original source row.
    """
    raw = row['text_raw']; fallback = row.get('text_minimal', minimal_filter_text(raw))
    result = dict(record_id=row['record_id'], source=row['source_dataset'],
                  text_view=fallback, view_method='RAW', reason='NO_DOM_METADATA')
    if row['source_dataset'] != 'facebook':
        return dict(result, reason='LEGACY_NO_DOM_POLICY')
    if observation is None: return result
    if observation.get('text_raw') != raw or any(
            str(observation.get(k) or '') != str(row.get(k) or '') for k in ('comment_id', 'post_id')):
        return dict(result, reason='OBSERVATION_IDENTITY_OR_RAW_MISMATCH')
    if observation.get('text_extraction_version') != 'dom_text_v2':
        return dict(result, reason='UNKNOWN_DOM_VERSION')
    count = observation.get('mention_count')
    if isinstance(count, str) and count.isdecimal(): count = int(count)
    if type(count) is not int or count <= 0:
        return dict(result, reason='NO_REPORTED_MENTION_DELETION')
    dom = observation.get('text_without_mentions')
    # Reuse the locked protocol's conservative deletion check, unchanged.
    from src.annotation.gold import display_text
    selected = display_text(raw, dom, count)
    if selected == raw:
        return dict(result, reason='DOM_DELETION_RULE_REJECTED_OR_UNCHANGED')
    return dict(result, text_view=minimal_filter_text(selected), view_method='DOM_RULE_MATCH',
                reason='SOURCE_BOUND_V2_AGGREGATE_METADATA_AND_DELETION_RULE;NOT_NODE_VERIFIED')
