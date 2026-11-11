"""Reviewed subset of Unicode CLDR English short names, version 1."""
import re

VERSION = 'cldr_alias_subset_v1'
# Unicode CLDR annotations/en.xml: https://github.com/unicode-org/cldr/blob/main/common/annotations/en.xml
ALIASES = {'rolling_on_the_floor_laughing': '🤣', 'red_heart': '❤️', 'crying_face': '😢',
           'face_with_tears_of_joy': '😂', 'loudly_crying_face': '😭', 'smiling_face_with_heart_eyes': '😍'}
PROTECTED = re.compile(r'https?://\S+|www\.\S+|`[^`]*`', re.I)
ALIAS = re.compile(r'(?<![\w:/]):([a-z][a-z_]*):(? !\w)'.replace('? !', '?!'))


def normalize_aliases(text):
    events = []
    def replace(match):
        value = ALIASES.get(match[1])
        if value is None:
            return match[0]
        events.append({'alias': match[0], 'replacement': value})
        return value
    pieces=[]; start=0
    for match in PROTECTED.finditer(text):
        pieces.extend([ALIAS.sub(replace,text[start:match.start()]),match[0]])
        start=match.end()
    pieces.append(ALIAS.sub(replace,text[start:]))
    return ''.join(pieces), events
