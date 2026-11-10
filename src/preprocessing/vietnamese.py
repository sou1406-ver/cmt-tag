"""Conservative Vietnamese text transforms, with literal symbol tokens and audit counts."""
from collections import Counter
from dataclasses import dataclass
from importlib.metadata import version
import re
import unicodedata


EMOTICON = re.compile(r"[:=;][\-^']?[)(]+|[:=;][\-^']?[dDpP]+(?!\w)|(?<!\w)[xX][dD]+(?!\w)|<3")
BASE = r'[\U0001F300-\U0001FAFF\u2600-\u27BF]'
MODIFIER = r'[\uFE0E\uFE0F]?[\U0001F3FB-\U0001F3FF]?'
EMOJI = re.compile(r'[\U0001F1E6-\U0001F1FF]{2}|[0-9#*]\uFE0F?\u20E3|'+BASE+MODIFIER+r'(?:\u200D'+BASE+MODIFIER+r')*')
PROTECTED = re.compile(r'\b(?:emoji(?:_u[0-9a-f]+)+|emot(?:_u[0-9a-f]+)+|ten_phim|ten_nhan_vat)\b')


@dataclass
class TextView:
    text: str
    steps: list
    counts: dict


class VietnamesePreprocessor:
    def __init__(self, config, segmenter=None):
        self.config = config
        self.segmenter = segmenter
        if (config.get('segmenter')!='underthesea' or config.get('segmenter_token_normalize') is not False
                or config.get('emoji')!='literal_unicode_codepoint_tokens'
                or config.get('emoticon')!='literal_codepoint_tokens'):
            raise ValueError('Explicit local segmentation and literal symbol policies required')
        mapping = config.get('teencode_map', {})
        if any(not k or not re.fullmatch(r'\w+', k) or k != k.lower() or not isinstance(v,str) or not v for k,v in mapping.items()):
            raise ValueError('Teencode map needs lowercase whole tokens and nonempty literal replacements')
        if any(k in mapping for k in ('không','chưa','chẳng','chả','đừng')):
            raise ValueError('Existing negation words must not be rewritten or deleted')
        if config.get('intensifier_map'):
            raise ValueError('Intensifiers need a separate experiment; vl/vch are unchanged here')
        if config.get('k_policy') != 'standalone_except_after_number':
            raise ValueError('Explicit k ambiguity policy required')
        self.teen_pattern = re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(k) for k in sorted(mapping,key=len,reverse=True))+r')(?!\w)') if mapping else None

    def _segment(self, text):
        if self.segmenter is None:
            expected = self.config['segmenter_version']
            if version('underthesea') != expected:
                raise ValueError('Install the pinned segmentation dependency from requirements-phase-e.txt')
            from underthesea import word_tokenize
            self.segmenter = lambda value: word_tokenize(value,format='text',use_token_normalize=False)
        # Protect literal emoji/emoticon/entity tokens from segmenter punctuation processing.
        parts=[];position=0
        for match in PROTECTED.finditer(text):
            if match.start()>position:parts.append(self.segmenter(text[position:match.start()]))
            parts.append(match.group());position=match.end()
        if position<len(text):parts.append(self.segmenter(text[position:]))
        return ' '.join(' '.join(parts).split())

    def transform(self, text, *, light=False, segment=False, teencode=False):
        if not isinstance(text,str):raise ValueError('Text must be a string')
        if (segment or teencode) and not light:raise ValueError('Segmentation/teencode are ablations on the light view')
        steps=[];counts=Counter()
        def apply(name, function):
            nonlocal text
            before=text;text=function(text)
            steps.append(dict(step=name,changed=before!=text))
        def symbols(pattern,prefix):
            def convert(match):
                counts[prefix+'_occurrences']+=1
                return ' '+prefix+''.join('_u'+format(ord(c),'x') for c in match.group())+' '
            return lambda value:pattern.sub(convert,value)
        if light:
            apply('unicode_nfc',lambda value:unicodedata.normalize('NFC',value))
            apply('whitespace',lambda value:' '.join(value.split()))
            apply('lowercase',str.lower)
            apply('emoticon_tokens',symbols(EMOTICON,'emot'))
            apply('emoji_tokens',symbols(EMOJI,'emoji'))
        if teencode and self.teen_pattern:
            def replace(value):
                def convert(match):
                    token=match.group()
                    if token=='k' and re.search(r'\d\s*$',value[:match.start()]):
                        counts['k_after_number_preserved']+=1
                        return token
                    counts['teencode_'+token]+=1
                    return self.config['teencode_map'][token]
                return self.teen_pattern.sub(convert,value)
            apply('teencode',replace)
        if segment:apply('segmentation',self._segment)
        if light:apply('final_whitespace',lambda value:' '.join(value.split()))
        return TextView(text,steps,dict(counts))
