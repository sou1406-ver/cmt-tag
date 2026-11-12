"""Minimal literal text view; never change raw observations or approve data."""
import re
import unicodedata

def minimal_filter_text(text):
    """Small data view: NFC, exact valid HTML, CRLF/NBSP and outer whitespace.

    Internal spacing/newlines and punctuation stay literal; no segmentation,
    alias conversion, teencode, case changes or mention/name guessing.
    """
    import html,html.entities
    entity=re.compile(r'&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);')
    technical=re.compile(r'```[\s\S]*?```|`[^`]*`|https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
    def decode(m):
        name=m[0][1:-1]
        if name.startswith('#'):
            try:code=int(name[2:],16) if name[1:2].lower()=='x' else int(name[1:])
            except ValueError:return m[0]
            if not 32<=code<=0x10ffff or 0xd800<=code<=0xdfff:return m[0]
        elif name+';' not in html.entities.html5:return m[0]
        return html.unescape(m[0])
    current=text
    while True:
        parts=[];cursor=0
        def clean(s):return entity.sub(decode,unicodedata.normalize('NFC',s)).replace('\r\n','\n').replace('\r','\n').replace('\u00a0',' ')
        for m in technical.finditer(current):parts.extend([clean(current[cursor:m.start()]),m[0]]);cursor=m.end()
        parts.append(clean(current[cursor:]));value=''.join(parts).strip()
        if value==current:return value
        current=value

# One public preprocessing implementation.
preprocess = minimal_filter_text
