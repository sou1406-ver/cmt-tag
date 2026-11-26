"""Chuẩn hóa bản đọc bình luận V2 từ Excel hoặc một câu nhập bằng CMD.

Cần Python 3.10 trở lên. Chế độ Excel cần openpyxl.
Quy tắc và bảng viết tắt đã chốt được đóng gói trong tệp này.
"""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import re
import sys
import tempfile
import unicodedata


# Các nghĩa đã duyệt dùng cho bản đọc. Nhãn không tham gia vào chuẩn hóa.
DEFAULT_GLOSSARY = {'AI': 'skip',
 'BHD': 'skip',
 'BVS': 'skip',
 'BWS': 'skip',
 'Btw': 'by the way',
 'CA': 'công an',
 'CCTV': 'skip',
 'CD': 'skip',
 'CEO': 'skip',
 'CGI': 'cái gì',
 'CHT': 'chân hoàn truyện',
 'CL': 'cái gì vậy / chuyện kỳ vậy',
 'CLVB': 'cua lại vợ bầu',
 'CNT': 'skip',
 'CT': 'châu tấn',
 'CVB': 'skip',
 'DH': 'diên hi',
 'DHCL': 'diên hi công lược',
 'DOP': 'skip',
 'Dr': 'giữ nguyên',
 'EEAAO': 'check bên trên có rồi',
 'GOT': 'game of throne',
 'GOTG': 'guardian of the galaxy',
 'HBO': 'skip',
 'HH': 'hoàng hậu',
 'HN': 'Hà Nội',
 'HQ': 'hàn quốc',
 'IG': 'instagram',
 'IQ': 'skip',
 'KJW': 'skip',
 'KSH': 'skip',
 'LA': 'skip',
 'LH': 'lý hải',
 'LHP': 'liên hoan phim',
 'LM': 'lật mặt',
 'LM1': 'lật mặt 1',
 'LM5': 'lật mặt 5',
 'LM6': 'lật mặt 6',
 'LM7': 'lặt mặt 7',
 'LM8': 'lật mặt 8',
 'LOTR': 'lord of the ring',
 'LR': 'lovely runner',
 'MBC': 'skip',
 'MCU': 'skip',
 'MLT': 'skip',
 'MODOK': 'skip',
 'MV': 'mv',
 'NB': 'nhật bản',
 'NBN': 'nhà bà nữ',
 'NBT': 'Người bất tử',
 'NVC': 'nhân vật chính',
 'NYT': 'như ý truyện',
 'Nch': 'nói chung',
 'Ncl': 'nói chung là',
 'Nf': 'netflix',
 'OST': 'ost',
 'Omg': 'oh my god',
 'P5': 'phần 5',
 'PAD': 'phương anh đào',
 'PAĐ': 'phương anh đào',
 'PN': 'skip',
 'PP': 'skip',
 'QBDX': 'skip',
 'QMTM': 'skip',
 'QOT': 'queen of tear',
 'QS': 'skip',
 'RDJ': 'skip',
 'RE': 'resident evil',
 'S8': 'season 8',
 'SAH': 'siêu anh hùng',
 'SBS': 'skip',
 'SFX': 'sfx',
 'SKTH': 'skip',
 'SQ': 'skip',
 'Ss5': 'season 5',
 'SxF': 'spy x family',
 'TGBM': 'skip',
 'TNK': 'tôn ngộ không',
 'TNM': 'skip',
 'TQ': 'trung quốc',
 'TSHS': 'skip',
 'TT': 'Trấn Thành',
 'TTCPQG': 'skip',
 'TTRR': 'skip',
 'TVB': 'skip',
 'TVHK': 'skip',
 'VFX': 'vfx',
 'VH': 'skip',
 'VN': 'việt nam',
 'VNB': 'skip',
 'VT': 'skip',
 'WS': 'skip',
 'WTPR': 'when the phone ring',
 'WTPS': 'skip',
 'WW': 'skip',
 'WYW': 'skip',
 'Wtf': 'chuyện gì vậy / thật sao',
 'XTM': 'xa thi mạn',
 'XXL': 'skip',
 'YYS': 'skip',
 'acc': 'giữ nguyên',
 'ace': 'anh chị em',
 'ads': 'quảng cáo',
 'ae': 'anh em',
 'bg': '',
 'bh': 'bao giờ',
 'bk': 'biên kịch',
 'bn': 'bao nhiên',
 'bnhieu': 'bao nhiêu',
 'bt': 'bình thường',
 'bth': 'bình thường',
 'bthg': 'bình thường',
 'bv': 'bệnh viện',
 'bxh': 'bảng xếp hạng',
 'cbh': 'chưa bao giờ',
 'cc': 'rất tệ',
 'cdg': 'cái gì vậy',
 'cf': 'skip',
 'cg': 'cũng',
 'cgv': 'skip',
 'ch': 'chích điện',
 'chs': 'chơi',
 'ck': 'chồng',
 'clg': 'bất cứ thứ gì / cái gì vậy',
 'clm': 'trời ơi / thật sao',
 'cm': 'con mẹ',
 'cmm': 'cái gì kỳ vậy',
 'cmn': 'thật sự / quá',
 'cmnl': 'thật sự / đúng hẳn',
 'cmnr': 'mất rồi / thật rồi',
 'cmt': 'comment',
 'cn': 'chúng nó hoặc con',
 'cs': 'skip',
 'cty': 'công ty',
 'cx': 'cũng',
 'dc': 'được',
 'dcd': 'không nhịn được / không chịu nổi',
 'dcm': 'trời ơi / thật sao',
 'dhs': 'skip',
 'dl': 'skip',
 'dm': 'trời ơi / thật sao',
 'dmwb': '',
 'ds': 'skip',
 'dth': 'dễ thương',
 'dv': 'diễn viên',
 'ep4': 'epsode 4',
 'ez': 'easy',
 'fb': 'face book',
 'gd': 'gia đình',
 'gg': 'google',
 'gpt': 'skip',
 'gr': 'group',
 'grp': 'group',
 'gth': 'giới thiệu',
 'hd': 'skip',
 'hg': 'không',
 'hk': 'không',
 'hl': 'rất khó chịu',
 'hok': 'không',
 'hqa': 'hôm qua',
 'htrc': 'hôm trước',
 'hum': 'không',
 'hy': 'hy',
 'hđ': 'hợp đồng',
 'ib': 'inbox',
 'idk': 'I don’t kniw',
 'j': 'gì',
 'jz': 'gì vậy',
 'k': 'không',
 'kb': 'không biết/ kịch bản',
 'kbt': 'không biết',
 'kh': 'không',
 'khong': 'không',
 'khs': 'không hiểu sao',
 'kk': 'skip',
 'klq': 'không liên quan',
 'kp': 'không phải',
 'kpop': 'kpop',
 'lmao': 'cười quá',
 'lol': 'cười / trời ơi',
 'mb': 'ko phải viết tắt',
 'mik': 'mình',
 'mk': 'mình',
 'mkt': 'maketing',
 'ml': 'quá tệ / đáng bực',
 'mn': 'mọi người',
 'mng': 'mọi người',
 'mqh': 'mối quan hệ',
 'ms': 'mới',
 'mxh': 'mạng xã hội',
 'nc': 'nước',
 'ncc': 'rất tệ',
 'nd': 'nội dung',
 'ng': 'người',
 'nh': 'nhiều',
 'nhg': 'nhưng mà',
 'nhma': 'nhưng mà',
 'nma': 'nhưng mà',
 'npc': 'giữ nguyên',
 'nph': 'nhà phát hành',
 'ns': 'nói',
 'nsx': 'nhà sản xuất',
 'nt': '',
 'ntn': 'như thế nào',
 'nv': 'nhân vật/ nhân viên tùy context',
 'nx': 'nữa',
 'ny': 'ngoiwuf yêu',
 'nyc': 'người yêu cũ',
 'p1': 'phần 1',
 'p13': 'phần 13',
 'p18': 'phần 18',
 'p2': 'phần 2',
 'p3': 'phần 3',
 'ph': '',
 'pr': 'giữ nguyên',
 'pt': 'phân tích',
 'qc': 'quảng cáo',
 'qg': 'quốc gia',
 'qh': 'quan hệ',
 'qq': 'quần què',
 'qt': 'quốc tế',
 'r': 'rồi',
 'rep': 'giữ nguyên',
 'rs': 'skip',
 'rv': 'review',
 'rw': 'review',
 's1': 'season 1',
 's11': 'season 11',
 'sh': 'skip',
 'sml': 'dữ dội',
 'sp': 'sản phẩm',
 'sr': 'skip',
 'ss': 'season',
 'ss1': 'season 1',
 'ss12': 'season 12',
 'ss2': 'season 2',
 'ss3': 'season 3',
 'ss4': 'season 4',
 'ss7': 'season 7',
 'ss9': 'season 9',
 'td': 'tình dục',
 'tg': 'thế giới',
 'th': 'thật',
 'thg': 'thằng',
 'thk': 'thằng',
 'tht': 'thật',
 'tk': 'thằng',
 'tl': 'trả lời',
 'tr': 'trời',
 'trc': 'trước',
 'trg': 'trong',
 'ttk': 'thám tử kiên',
 'tv': 'tivi',
 'ty': 'ty',
 'v': 'vậy',
 'vc': 'quá',
 'vcc': 'rất / quá / trời ơi',
 'vcd': 'rất / quá / trời ơi',
 'vch': 'rất / quá / trời ơi',
 'vcl': 'rất / quá / trời ơi',
 'vd': 'ví dụ',
 'vde': 'vấn đề',
 'vk': 'vợ',
 'vkl': 'rất / quá / trời ơi',
 'vl': 'rất / quá / trời ơi',
 'vll': 'rất / quá / trời ơi',
 'vs': 'với',
 'vtv': 'giữ nguyên',
 'vđ': 'vvasix đái',
 'wb': 'skip',
 'wv': 'skip',
 'xh': 'xã hội',
 'xl': 'xin lỗi',
 'xp': 'skip',
 'yt': 'youtube',
 'ytb': 'youtube',
 'z': 'vậy',
 'zl': 'rất / quá / trời ơi',
 'đc': 'được',
 'đcm': 'trời ơi / thật sao',
 'đm': 'trời ơi / thật sao',
 'đr': 'đún rồi'}

DEFAULT_SUPPLEMENT = {'44': ('tự tử', 'Khi dùng với nghĩa tự tử'),
 'b': ('bạn', ''),
 'e': ('em', ''),
 'gđ': ('gia đình', ''),
 'h': ('giờ', ''),
 'iu': ('yêu', ''),
 'ko': ('không', ''),
 'kphai': ('không phải', ''),
 'nam8': ('nam phụ', ''),
 'nam9': ('nam chính', ''),
 'nchung': ('nói chung', ''),
 'ngkhac': ('người khác', ''),
 'ngta': ('người ta', ''),
 'nu9': ('nữ chính', ''),
 'nữ8': ('nữ phụ', ''),
 'nữ9': ('nữ chính', ''),
 'rep': ('trả lời', ''),
 't': ('tao/tôi/tớ', ''),
 'vcđ': ('vãi cả đái', ''),
 'vđ': ('vãi đái', ''),
 'đ': ('del', '')}

MN_NEXT = {'ơi', 'xem', 'thấy', 'nghĩ', 'cảm', 'đừng', 'hãy', 'có', 'nên', 'đều'}

EMOTICON = r':\):\)|(?::|;|=)(?:-|\^)?(?:\)+|\(+|[vVpPdD/\\])|-_-|\^\^|<3'

EMOJI_BASE = r'(?:[0-9#*]\ufe0f?\u20e3|[\U0001f1e6-\U0001f1ff]{2}|[\U0001f000-\U0001faff\u2600-\u27bf])'

EMOJI = EMOJI_BASE + r'[\ufe0e\ufe0f\U0001f3fb-\U0001f3ff\U000e0020-\U000e007f]*(?:\u200d' + EMOJI_BASE + r'[\ufe0e\ufe0f\U0001f3fb-\U0001f3ff]*)*'

PROTECTED = re.compile(r'https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|' + EMOTICON + '|' + EMOJI)

DIRECT = set('xh cty mqh htrc klq mxh cmt cx nma bth ntn mng nhma ib thg '
             'hok khong kp nhg bthg trc rv nd mik dth hqa bnhieu kbt khs '
             'nyc jz cbh bxh thk tht grp gth vde'.split())

SETTLED = {'ko': 'không', 'k0': 'không', 'khum': 'không'}

NAME_KEYS = set('SxF CHT NVC LR XTM NYT DHCL NBN PAĐ LHP NBT CLVB SAH QOT WTPR EEAAO VN TQ HQ LOTR'.split())

NAMES = {
    'SxF': 'Spy × Family', 'CHT': 'Chân Hoàn Truyện', 'LR': 'Lovely Runner',
    'XTM': 'Xa Thi Mạn', 'NYT': 'Như Ý Truyện', 'DHCL': 'Diên Hi Công Lược',
    'NBN': 'Nhà Bà Nữ', 'PAĐ': 'Phương Anh Đào', 'NBT': 'Người Bất Tử',
    'CLVB': 'Cua Lại Vợ Bầu',
    'QOT': 'Queen of Tears', 'WTPR': 'When the Phone Rings',
    'EEAAO': 'Everything Everywhere All at Once', 'VN': 'Việt Nam',
    'TQ': 'Trung Quốc', 'HQ': 'Hàn Quốc', 'LOTR': 'The Lord of the Rings',
}

SHORTCUTS = {
    'ae': 'anh em', 'ace': 'anh chị em', 'nsx': 'nhà sản xuất', 'nph': 'nhà phát hành',
    'fb': 'Facebook', 'ytb': 'YouTube', 'bk': 'biên kịch', 'rw': 'review',
    'nch': 'nói chung', 'ncl': 'nói chung là', 'đr': 'đúng rồi', 'ny': 'người yêu',
    'idk': 'I don’t know',
    'mk': 'mình', 'gr': 'nhóm', 'vd': 'ví dụ', 'bth': 'bình thường',
}

INTENSIFIERS = set('vl vcl vkl vcc vcd vll vch zl vc vđ vcđ'.split())

INTERJECTIONS = set('đm đcm dm dcm clm'.split())

LITERAL_SLANG = INTENSIFIERS | INTERJECTIONS | {
    'dmm', 'đmm', 'đcmm', 'đkm', 'wtf', 'lmao', 'sml', 'ncc', 'cc', 'đ',
}

SUPPLEMENT_DIRECT = set('ngta ko rep iu nu9 nam9 nữ9 gđ kphai ngkhac nchung nam8 nữ8'.split())

ADJECTIVES = (r'(?:hay|dở|đẹp|chán|tệ|sợ|ghê|hài|cuốn|nhạt|ảo|xịn|đỉnh|'
              r'dở tệ|vô lý|khó chịu|cảm động|đáng sợ|buồn cười|báo|lố|gắt|đơ|'
              r'chậm|nhanh|tối|ồn|giả|giống|mệt|buồn|vui|hóng|sượng|tiếc|sốc|ngon|ổn|'
              r'sôi máu|kinh dị|seeding|đạt|thoải mái|cringe|bình thường|vô tri|bực|hèn|dị|cute)')

FILM = re.compile(r'\b(?:phim|tập|trailer|kịch bản|diễn xuất|diễn viên|nội dung|'
                  r'khán giả|nhà đài|đạo diễn|nhân vật|góc quay|kỹ xảo)\b')

CHARACTER_CONTEXT = re.compile(r'\b(?:truyện|cốt truyện|hư cấu|tạo hình|tuyến chính|tuyến phụ|đóng vai)\b')

WORKPLACE = re.compile(r'\b(?:tuyển|nhân viên|tuyển dụng|thử việc|chấm công|'
                       r'ca làm|cửa hàng|công ty|quản lý|bảo vệ|phục vụ|lễ tân|'
                       r'giao hàng|bán hàng|thu ngân|rạp chiếu|hậu trường|nghỉ việc|ca trực|tăng lương)\b')

WORD = re.compile(r'\w+')

OPAQUE = re.compile(PROTECTED.pattern + r'|`[^`\n]*`|(?<!\w)[@#][\w.-]+')

VIETNAMESE = re.compile(r'[ăâđêôơưà-ãè-éì-íò-õù-úýạ-ỹ]')

NEGATABLE = set('ai bao bảo bằng biết bị cần cho chê chi chịu chơi có coi dám đi đọc đúng được đc '
                'đáng đủ hiểu hay hợp làm lấy muốn nghe ngờ nghĩ ngại nhìn nói phải quan rảnh '
                'sợ thấy thể thích tin tới trọn tưởng vô xem xúc yêu ổn oan'.split())

def make_normalizer(glossary, supplemental=None, *, reading_copy=False):
    supplemental = supplemental or {}
    finalized = {key: meaning for key, (meaning, _) in supplemental.items()
                 if meaning and meaning.casefold() not in {'skip', 'giữ nguyên'}}
    approved = {
        token for token, meaning in glossary.items()
        if meaning and meaning.casefold() != 'skip' and 'giữ nguyên' not in meaning.casefold()
    }
    exact = {key: glossary[key] for key in DIRECT & approved}
    exact.update({key: NAMES.get(key, glossary[key]) for key in NAME_KEYS & approved})
    exact.update({key: value for key, value in SHORTCUTS.items()
                  if key in {token.casefold() for token in approved}})
    exact.update(SETTLED)
    exact.update({key: finalized[key] for key in SUPPLEMENT_DIRECT & finalized.keys()})
    exact.update({key.lower(): exact[key] for key in ['NYT', 'DHCL', 'CHT', 'NBN', 'CLVB', 'QOT', 'WTPR', 'EEAAO']
                  if key in exact})
    allowed = {token.casefold() for token in approved} | SETTLED.keys() | {'h'} | finalized.keys()
    folded = {key.casefold() for key in exact if key == key.lower()}
    candidates = re.compile(r'(?<!\w)(?:như[ \t]+cc|\w+)(?!\w)', re.IGNORECASE)

    def normalize(text, replacements=None):
        matches = []
        held = []
        opaque = list(OPAQUE.finditer(text))
        span_index = 0
        edits = []
        for token in candidates.finditer(text):
            while span_index < len(opaque) and opaque[span_index].end() <= token.start():
                span_index += 1
            if span_index < len(opaque) and opaque[span_index].start() < token.end():
                continue
            original = token[0]
            key = original.casefold()
            if reading_copy and (key in LITERAL_SLANG or re.fullmatch(r'như[ \t]+cc', key)):
                continue
            if key not in allowed and key != 'như cc' and not re.fullmatch(r'\w+ +cc', key):
                continue
            before = text[:token.start()].casefold()
            after = text[token.end():].casefold()
            following = re.match(r'\s+(\w+)', after)
            next_word = following[1] if following else ''
            before_word = re.search(r'(\w+)[ \t]*$', before)
            previous_word = before_word[1] if before_word else ''
            # Keep shorthand within obfuscated words, codes and numeric units literal.
            in_code = bool(re.match(r'[./-]\w', after) or re.search(r'\w[./-]$', before))
            after_number = previous_word.isdecimal()
            nearby = before[-100:] + ' ' + after[:100]
            film_context = FILM.search(nearby)
            vietnamese = VIETNAMESE.search(nearby)
            at_clause_end = not after.strip() or bool(
                re.match(r'\s*(?:[,.!?;:)]|=+\)|nữa\b|ạ\b|nha\b|nhé\b|mà\b)', after)
            ) or (span_index < len(opaque) and not text[token.end():opaque[span_index].start()].strip())
            replacement = exact.get(original)
            if original.islower() and key in folded:
                replacement = exact[key]
            elif key in folded and original.istitle() and not before.strip():
                replacement = exact[key][0].upper() + exact[key][1:]

            if key in INTENSIFIERS and not in_code:
                if original.islower() and (
                    key not in {'vc', 'vđ', 'zl'} or re.search(rf'\b{ADJECTIVES}[ \t]+$', before)
                ):
                    replacement = 'vl'
            elif key in INTERJECTIONS and (original.islower() or original.istitle()) and not in_code:
                is_exclamation = (
                    (vietnamese or at_clause_end)
                    and not after_number
                    and previous_word not in {'của', 'hãng', 'nhóm', 'công ty', 'mã', 'chữ', 'từ', 'viết', 'gõ'}
                )
                if is_exclamation:
                    replacement = 'Đm' if original.istitle() else 'đm'
            elif key == 'mn' and original.islower() and vietnamese and (
                next_word in MN_NEXT | {'bảo', 'nói', 'giúp', 'biết', 'ạ', 'cho', 'nhỉ'}
                or at_clause_end
            ):
                replacement = 'mọi người'
            elif key == 'ng' and original.islower() and (
                next_word in {'ta', 'xem', 'hâm', 'khác', 'này', 'kia', 'đó', 'yêu', 'lớn', 'đóng', 'die', 'chết'}
                or re.search(r'\b(?:có|tìm|cứu|giết|gặp|mấy|những|nhiều|mỗi|mọi|từng|số|\d+)\s+$', before)
            ):
                replacement = 'người'
            elif key in {'đc', 'dc'} and original.islower() and next_word not in {'comics', 'studio', 'studios', 'universe'}:
                if key == 'đc' or (vietnamese and (
                    next_word in {'cái', 'rồi', 'nữa', 'không', 'k', 'chưa', 'gì', 'thì'}
                    or re.search(r'\b(?:xem|coi|làm|nói|nghe|thấy|cũng|mới|kiếm|chưa|không|k|ko|đọc|hiểu|nếu|thành|có|để|mở|khó|bị)\s+$', before)
                )):
                    replacement = 'được'
            elif key in {'k', 'kh', 'hk'} and not in_code and not after_number:
                before_bt = reading_copy and next_word == 'bt'
                if (vietnamese or before_bt) and (original.islower() or (not before.strip() and next_word in NEGATABLE)):
                    protected_name = re.search(r'\b(?:vitamin|mã|chữ|độ|hệ|biến|loại|ký hiệu|mô hình|protein|định dạng)\s+$', before)
                    if not protected_name and (
                        next_word in NEGATABLE or before_bt
                        or key == 'k' and (next_word or at_clause_end) and not next_word.isdecimal()
                        or re.search(r'\b(?:có|được|đc|phải|hiểu|đúng|hay|ổn|thích|biết|nhỉ|phim)\s+$', before)
                        and (at_clause_end or next_word in {'bà', 'm', 'bạn'})
                    ):
                        replacement = 'Không' if original.isupper() else 'không'
            elif key in {'b', 'e', 't', 'h'} and key in finalized and original.islower() and not in_code and not after_number:
                if key in {'b', 'e'} and next_word == 'ơi':
                    replacement = finalized[key]
                elif reading_copy and key == 'b' and vietnamese and not re.search(
                    r'\b(?:loại|mã|chữ|nhóm|idol|đội|hạng|vitamin|nốt|phương án|diễn viên)\s+$', before
                ) and (
                    next_word in NEGATABLE | {'nên', 'ạ', 'mới', 'ngầu', 'khác', 'đã', 'đang', 'cũng', 'vẫn',
                                              'bảo', 'nhỉ', 'nghĩ', 'ơi', 'giúp'}
                    or previous_word in {'cho', 'hỏi', 'thank', 'theo', 'với'}
                    or previous_word in {'đâu', 'đó', 'á', 'thôi', 'nha', 'nhé', 'nè'} and at_clause_end
                ):
                    replacement = finalized[key]
                elif key == 't' and vietnamese and next_word in {'nghĩ', 'thấy', 'nhớ', 'xem', 'nói', 'hỏi'}:
                    replacement = 'tôi' if finalized[key] == 'tao/tôi/tớ' else finalized[key]
                elif key == 'h' and previous_word in {'bao', 'bây'}:
                    replacement = finalized[key]
            elif key == '44' and reading_copy and key in finalized and not in_code and not after_number:
                numeric_context = re.match(r'\s*(?:[.,]\d|[%/]|tuổi\b|phút\b|giờ\b|lần\b|ngày\b|giây\b|tập\b|triệu\b|tỷ\b|km\b|kg\b)', after)
                numeric_prefix = re.search(r'\b(?:idol|số|tập|phần|hạng|mã|trang|điểm|câu|phút|giờ|ngày)\s*$', before)
                clear_context = re.search(r'\b(?:tự tử|thuốc|súng|kill|điều ước|dũng khí|không chịu nổi)\b', nearby)
                if not numeric_context and not numeric_prefix and (
                    clear_context
                    or previous_word in {'tính', 'định', 'muốn', 'để', 'hoặc'} and next_word in {'rồi', 'vì', 'bằng', 'không', 'nữa', 'để'}
                    or previous_word in {'bear', 'nikki'} and next_word in {'rồi', 'nữa', 'bằng'}
                ):
                    replacement = finalized[key]
            elif key == 'r' and original.islower() and vietnamese and before.rstrip() and (
                at_clause_end or next_word in {'mà', 'nên', 'thì', 'mới', 'vẫn', 'cũng', 'ấy', 'đó'}
                or re.search(r'\b(?:xem|coi|thấy|biết|đọc|nói|mất|hết|lâu|xong|đúng|đủ|hay|chán|tệ|thế|vậy|chưa|đc|được)\s+$', before)
            ) and not re.search(r'\b(?:loại|hạng|mã|kênh|chữ|ngôn ngữ|gói)\s+$', before):
                replacement = 'rồi'
            elif key in {'j', 'v', 'z'} and original.islower() and not in_code:
                preceding = (r'cái|phim|phần|kiểu|thứ|điều|chuyện|làm|xem|nói|có|từ|tên'
                             if key == 'j' else r'sao|gì|j|thế|như|nói|gọi|tệ|hay|đẹp|chán')
                if key == 'v':
                    if re.search(r'\b(?:sao|gì|j|thế|như|gọi là)\s+$', before) and at_clause_end:
                        replacement = 'vậy'
                elif vietnamese and (re.search(rf'\b(?:{preceding})\s+$', before)
                    or (before.rstrip() and at_clause_end)
                    or (key == 'j' and next_word in {'cả', 'cho', 'cũng', 'thế', 'vậy', 'v', 'z'})
                    or (key != 'j' and next_word in {'các', 'bác', 'mọi', 'mn', 'thì', 'mà'})):
                    replacement = 'gì' if key == 'j' else 'vậy'
            elif key == 'vs' and original.islower() and vietnamese and next_word and (
                next_word in {'cả', 'lại', 'cái', 'nhiều', 'diễn', 'nữ', 'nam', 'mấy', 'nhân', 'phim', 'mình', 'nó', 'bạn'}
                or re.search(r'\b(?:so|hợp|khác|giống|cùng|chung|kèm|thua|hơn|ngang|so sánh)\s+$', before)
            ):
                replacement = 'với'
            elif key == 'nvc' and original.islower() and not in_code and (
                film_context or CHARACTER_CONTEXT.search(nearby)
                or reading_copy and (
                    previous_word in {'thằng', 'con', 'dàn', 'team', 'tụi', 'nhà', 'vai', 'là'}
                    or bool(re.search(r'\bhào quang\s+$', before))
                    or re.match(r'\s+và\s+(?:nam|nữ) chính\b', after)
                )
            ):
                replacement = 'nhân vật chính'
            elif key == 'nv' and not in_code:
                character_role = re.match(r'\s+(?:chính|phụ|phản diện|lịch sử|hư cấu)\b', after)
                job_role = re.match(r'\s+(?:bảo vệ|phục vụ|bán hàng|thu ngân|soát vé|lễ tân|giao hàng)\b', after)
                workplace = WORKPLACE.search(nearby)
                if (job_role and (workplace or not film_context)) or (
                    workplace and not film_context and not character_role and original.islower()
                ):
                    replacement = 'nhân viên'
                elif (character_role and not workplace) or (
                    original.islower() and (film_context or CHARACTER_CONTEXT.search(nearby)) and not workplace
                ):
                    replacement = 'nhân vật'
            elif key == 'dv' and original.islower() and film_context and (
                next_word in {'chính', 'phụ', 'nam', 'nữ', 'này', 'nào', 'đó', 'đã'} or at_clause_end
            ):
                replacement = 'diễn viên'
            elif key == 'bt' and reading_copy and not in_code and (original.islower() or original.istitle()):
                film_subject = re.search(r'\b(?:phim|nội dung|kịch bản|kỹ xảo|đồ họa|diễn xuất)(?:\s+(?:nó|thì|cũng))?\s+$', before)
                rating = previous_word in {'thấy', 'rất', 'quá', 'khá'} or film_subject
                if previous_word in {'không', 'khong', 'ko', 'k0', 'khum', 'k', 'kh', 'hk', 'hok', 'chẳng', 'chả', 'chưa', 'đéo'}:
                    replacement = 'biết'
                elif rating and (at_clause_end or next_word in {'thôi', 'lắm', 'thế', 'so', 'nhưng', 'v', 'vậy', 'vl', 'mà', 'luôn'}):
                    replacement = 'bình thường'
                elif not rating and (
                    next_word in {'rằng', 'gì', 'cái', 'chuyện', 'gu', 'cách', 'chỗ', 'nó', 'y'} and previous_word
                    or next_word == 'là' and (not before.strip() or previous_word in {'có', 'nó', 'ai', 't', 'mình', 'tôi'})
                    or previous_word in {'có', 'mới', 'đã', 'đâu'} and next_word in {'không', 'ko', 'k', 'nữa', 'đâu'}
                ):
                    replacement = 'biết'
                if replacement and original.istitle():
                    replacement = replacement[0].upper() + replacement[1:]
            elif key == 'bt' and original.islower() and re.search(r'\b(?:thấy|rất|quá|khá)\s+$', before) and (
                at_clause_end or next_word in {'thôi', 'lắm', 'mà'}
            ):
                replacement = 'bình thường'
            elif key == 'bn' and original.islower() and next_word in {'tiền', 'tuổi', 'tập', 'phút', 'mùa', 'phần', 'năm', 'điểm'}:
                replacement = 'bao nhiêu'
            elif key == 'tr' and original.islower() and next_word == 'ơi':
                replacement = 'trời'
            elif key == 'nc' and original.islower() and next_word in {'ngoài', 'nào', 'mình', 'ta'}:
                replacement = 'nước'
            elif key == 'kb' and original.islower() and film_context and re.search(r'\b(?:đổi|viết|đọc|sửa|chê)\s+$', before):
                replacement = 'kịch bản'
            elif key in {'cg', 'ms', 'ns'} and original.islower() and vietnamese and next_word in NEGATABLE | {'vừa', 'đang', 'xong', 'lại', 'gì', 'ghét'}:
                replacement = {'cg': 'cũng', 'ms': 'mới', 'ns': 'nói'}[key]
            elif key in {'vk', 'ck'} and original.islower() and (
                next_word in {'ck', 'iu', 'yêu', 'khờ', 'chồng'} or re.search(r'\b(?:bỏ|lấy|chồng|vợ|2|hai|mấy)\s+$', before)
            ):
                replacement = {'vk': 'vợ', 'ck': 'chồng'}[key]
            elif re.fullmatch(r'ss\d+|lm\d+|ep\d+|p\d+|s\d+', key):
                prefix, number = re.fullmatch(r'([a-z]+)(\d+)', key).groups()
                if prefix in {'ss', 'lm', 'ep'} or film_context or re.search(r'\b(?:xem|coi|mùa|phần)\s+$', before):
                    name = {'ss': 'mùa', 's': 'mùa', 'lm': 'Lật Mặt', 'ep': 'tập', 'p': 'phần'}[prefix]
                    replacement = f'{name} {number}'
            elif key == 'ss' and (next_word.isdecimal() or (
                film_context and re.search(r'\b\d+\s+$', before) and next_word in {'đầu', 'sau', 'trước'})):
                replacement = 'mùa'

            if replacement and replacement != original:
                matches.append(key)
                edits.append((token.start(), token.end(), replacement))
                if replacements is not None:
                    replacements[(key, replacement)] += 1
            else:
                held.append(key)
        output = []
        end = 0
        for start, stop, replacement in edits:
            output.extend((text[end:start], replacement))
            end = stop
        output.append(text[end:])
        return ''.join(output), matches, held

    return normalize

CORRECTIONS = {
    'xuất chiếu': 'suất chiếu',
    'kỹ sảo': 'kỹ xảo',
    'kĩ sảo': 'kĩ xảo',
    'lập đi lập lại': 'lặp đi lặp lại',
    'chỉnh chu': 'chỉn chu',
    'tác dunng': 'tác dụng',
    'dfungs': 'đúng',
    'gia to6c': 'gia tộc',
    'bỡi vì': 'bởi vì',
    'nhan vật': 'nhân vật',
}

REVIEW = {
    'luon': ('luôn', 'Dạng bỏ dấu có thể là chủ ý'),
    'coá': ('có', 'Có thể là giọng viết của người bình luận'),
    'đag': ('đang', 'Có thể là viết tắt có chủ ý'),
    'cũg': ('cũng', 'Có thể là viết tắt có chủ ý'),
    'đún': ('đúng', 'Có thể là giọng viết của người bình luận'),
    'trùi': ('trời', 'Cách viết cảm thán, có thể có chủ ý'),
    'dể': ('dễ / để', 'Cần xem nghĩa và kiểu nói trong câu'),
    'câu truyện': ('câu chuyện', 'Xem người viết đang dùng theo nghĩa nào'),
    'lập lại': ('lặp lại', 'Có thể mang nghĩa lập lại hoặc lặp lại'),
    'netflit': ('Netflix', 'Xác nhận cách viết tên riêng'),
    'mat day': ('mất dạy', 'Cụm bỏ dấu và mang sắc thái công kích'),
    'khac': ('khác', 'Dạng bỏ dấu có thể là chủ ý'),
}

def word_pattern(terms):
    return re.compile(r'(?<!\w)(?:' + '|'.join(map(re.escape, sorted(terms, key=len, reverse=True))) + r')(?!\w)', re.I)

CORRECTION_PATTERN = word_pattern(CORRECTIONS)

REVIEW_PATTERN = word_pattern(REVIEW)

NON_DEV = {'T2_SCORE', 'T2_REVIEW_OR_EXCLUDE', 'PENDING_SUPPLEMENT'}

def eligible_matches(pattern, text):
    """Match literal phrases outside emoji, code, URLs, tags and handles."""
    protected = list(OPAQUE.finditer(text))
    cursor = 0
    for match in pattern.finditer(text):
        while cursor < len(protected) and protected[cursor].end() <= match.start():
            cursor += 1
        if cursor < len(protected) and protected[cursor].start() < match.end():
            continue
        yield match

def correct(text):
    pieces = []
    edits = []
    cursor = 0
    for match in eligible_matches(CORRECTION_PATTERN, text):
        source = match[0]
        replacement = CORRECTIONS[source.casefold()]
        if source.isupper():
            replacement = replacement.upper()
        elif source[0].isupper():
            replacement = replacement[0].upper() + replacement[1:]
        pieces.extend((text[cursor:match.start()], replacement))
        edits.append((match.start(), match.end(), source, replacement))
        cursor = match.end()
    pieces.append(text[cursor:])
    return ''.join(pieces), edits

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


# Prefer the source column when both text views already exist.
TEXT_HEADERS = (
    'trước chuẩn hóa viết tắt và chính tả',
    'trước chuẩn hóa viết tắt',
    'text_source', 'text_clean', 'text_normalized', 'text_raw',
    'bình luận gốc', 'nội dung bình luận', 'văn bản gốc',
    'bình luận', 'comment_text', 'comment', 'nội dung', 'cmt', 'text',
)
ROLE_HEADERS = {'vai trò dữ liệu', 'split_role'}
OUTPUT_HEADER = 'Bình luận chuẩn hóa'
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]')
normalize_abbreviations = make_normalizer(DEFAULT_GLOSSARY, DEFAULT_SUPPLEMENT, reading_copy=True)


def technical_text(text):
    return ' '.join(CONTROL.sub('', minimal_filter_text(text)).split())


def normalize_comment(text, *, apply_spelling=True):
    """Giữ nguyên chữ tục, emoji, emoticon và sắc thái ngoài quy tắc đã duyệt."""
    base = technical_text(text)
    abbreviated, _, _ = normalize_abbreviations(base)
    return correct(abbreviated)[0] if apply_spelling else abbreviated


def normalize_v2(text):
    """Áp dụng cùng quy tắc đã chốt cho mọi câu, kể cả train và test."""
    return normalize_comment(text)


def folded_word(word):
    return ''.join(c for c in unicodedata.normalize('NFD', word.replace('đ', 'd'))
                   if unicodedata.category(c) != 'Mn')


def deletion_keys(word):
    return {word} | {word[:i]+word[i+1:] for i in range(len(word))}


def near_spelling(left, right):
    if left == right:
        return True
    if len(left) == len(right):
        diff = [i for i,(a,b) in enumerate(zip(left,right)) if a!=b]
        if len(diff)==1:
            return True
        return (len(diff)==2 and diff[1]==diff[0]+1
                and left[diff[0]]==right[diff[1]] and left[diff[1]]==right[diff[0]])
    if abs(len(left)-len(right)) == 1:
        if len(left)>len(right):
            left,right=right,left
        return left in deletion_keys(right)
    return False


def corpus_suggestions(texts, limit=40):
    """Rank similar spellings by corpus frequency and observed neighboring words.

    Suggestions are evidence for review. They do not change any comment.
    """
    frequency=Counter()
    surface=Counter()
    contexts=defaultdict(Counter)
    samples={}
    for text in texts:
        # Remove protected spans before looking for neighboring words.
        for segment in re.split(r'\n|[.!?;,:]',OPAQUE.sub('\n',text)):
            matches=list(WORD.finditer(segment))
            words=[m[0].casefold() for m in matches]
            frequency.update(words)
            for i,match in enumerate(matches):
                term=words[i]
                surface[term] += match[0].islower()
                neighbors=contexts[term]
                if i:
                    neighbors['left',words[i-1]]+=1
                if i+1<len(words):
                    neighbors['right',words[i+1]]+=1
                samples.setdefault(term,'“'+segment[max(0,match.start()-60):match.end()+65].strip()+'”')
    known=defaultdict(set)
    folded_terms={term:folded_word(term) for term in frequency}
    for term,n in frequency.items():
        if n>=5 and term.isalpha() and 3<=len(term)<=16 and surface[term]:
            for key in deletion_keys(folded_terms[term]):
                known[key].add(term)

    accepted_sources=set(CORRECTIONS)|set(REVIEW)|LITERAL_SLANG
    suggestions=[]
    for term,n in frequency.items():
        if n>3 or len(term)<4 or len(term)>16 or not surface[term] or not term.isalnum() or term in accepted_sources:
            continue
        folded=folded_terms[term]
        alternatives={candidate for sig in deletion_keys(folded) for candidate in known[sig]}
        best=None
        for candidate in alternatives:
            target_n=frequency[candidate]
            other=folded_terms[candidate]
            if candidate==term or target_n<max(5,3*n) or not near_spelling(folded,other):
                continue
            matched=contexts[term].keys() & contexts[candidate].keys()
            # Common function words give weak evidence on their own.
            informative={j for j in matched if j[1] not in {'là','và','có','của','thì','mà','nó','cái','đó','rồi','này','với','tôi','cho'}}
            weight=sum(min(contexts[term][j],contexts[candidate][j]) for j in informative)
            if not weight:
                continue
            strongest=max(informative,key=lambda j:(min(contexts[term][j],contexts[candidate][j]),j))
            direction,neighbor=strongest
            evidence=f'{neighbor} {candidate}' if direction=='left' else f'{candidate} {neighbor}'
            score=(folded==other,weight,target_n,candidate)
            if best is None or score>best[0]:
                best=(score,[term,candidate,n,target_n,weight,evidence,samples[term]])
        if best is not None:
            suggestions.append(best)
    suggestions.sort(key=lambda item:(not item[0][0],-item[0][1],-item[1][2],-item[0][2],item[1][0]))
    return [row for _,row in suggestions[:limit]]


def find_text_table(book, sheet_name, column_name, header_row):
    """Find the source column from its header, or use explicit column and row."""
    from openpyxl.utils.cell import column_index_from_string

    if sheet_name is not None:
        if sheet_name not in book.sheetnames:
            raise ValueError(f'Không tìm thấy sheet {sheet_name!r}. Có: {", ".join(book.sheetnames)}')
        sheets = [book[sheet_name]]
    else:
        sheets = sorted(book.worksheets, key=lambda sheet: sheet.title.casefold()!='bình luận')

    recognized = [column_name.strip().casefold()] if column_name else TEXT_HEADERS
    for sheet in sheets:
        for number in ([header_row] if header_row is not None else range(1, min(sheet.max_row,12)+1)):
            lookup = {str(cell.value).strip().casefold(): cell.column for cell in sheet[number] if cell.value is not None}
            selected = next((name for name in recognized if name in lookup), None)
            if selected is not None:
                return sheet, number, lookup[selected]
        if column_name and header_row is not None and re.fullmatch(r'[A-Za-z]{1,3}',column_name):
            return sheet, header_row, column_index_from_string(column_name.upper())
    raise ValueError('Không nhận ra cột bình luận. Dùng --sheet, --column và --header-row để chỉ định.')


def export_workbook(input_file, output_file, sheet_name, column_name, header_row, *, suggest=False,
                    output_column=OUTPUT_HEADER):
    try:
        from openpyxl import load_workbook
    except ModuleNotFoundError as error:
        raise ValueError('Cần openpyxl cho chế độ Excel. Chạy: py -m pip install openpyxl') from error
    if input_file.suffix.lower() != '.xlsx' or output_file.suffix.lower() != '.xlsx':
        raise ValueError('Đầu vào và đầu ra phải là tệp .xlsx')
    if not input_file.is_file():
        raise ValueError(f'Không tìm thấy tệp: {input_file}')
    if output_file.exists():
        raise ValueError(f'Tệp đích đã tồn tại: {output_file}. Chọn tên đầu ra mới.')
    if not output_file.parent.is_dir():
        raise ValueError(f'Không tìm thấy thư mục đầu ra: {output_file.parent}')

    book = load_workbook(input_file)
    pending = None
    try:
        sheet, header, source = find_text_table(book, sheet_name, column_name, header_row)
        headers = {str(cell.value).strip().casefold():cell.column for cell in sheet[header] if cell.value is not None}
        role = next((headers[key] for key in sorted(ROLE_HEADERS) if key in headers), None)
        existing_column = headers.get(output_column.strip().casefold())
        destination = existing_column or sheet.max_column+1
        if destination == source:
            raise ValueError('Chọn cột văn bản đầu vào khác với cột kết quả.')
        from copy import copy
        if existing_column is None:
            target_header = sheet.cell(header, destination, output_column)
            target_header._style = copy(sheet.cell(header,source)._style)
            sheet.column_dimensions[target_header.column_letter].width = 68
        reviewed = changed = formulas = 0
        development_texts=[]
        for row in range(header+1,sheet.max_row+1):
            original = sheet.cell(row,source)
            target = sheet.cell(row,destination)
            if original.data_type == 'f':
                formulas += 1
                target.value = None
                continue
            value = original.value
            if not isinstance(value,str):
                target.value = value
                continue
            split = str(sheet.cell(row,role).value or '').strip().upper() if role is not None else ''
            if suggest and split not in NON_DEV:
                development_texts.append(normalize_comment(value,apply_spelling=False))
            result = normalize_v2(value)
            if target.value != result or target.data_type != 's':
                target.value = result
                target.data_type = 's'
            if existing_column is None:
                target.alignment = copy(original.alignment)
            reviewed += 1
            changed += (result != value)
        if suggest:
            from openpyxl.styles import Alignment, Font, PatternFill

            audit_name = 'Gợi ý từ corpus'
            if audit_name in book.sheetnames:
                raise ValueError(f'Tệp đầu vào đã có sheet {audit_name!r}. Đổi tên sheet này trước khi tạo đợt gợi ý mới.')
            audit = book.create_sheet(audit_name)
            audit.append(['Gợi ý để rà. Cột bình luận giữ nguyên các dạng này cho đến khi có quy tắc được chốt.'])
            audit.append(['Dạng gốc','Dạng gần giống','Lượt dạng gốc','Lượt dạng gợi ý','Lượt khớp ngữ cảnh','Cụm đã gặp','Ví dụ gốc'])
            for row in corpus_suggestions(development_texts):
                audit.append(row)
            audit.merge_cells('A1:G1')
            for cell in audit[2]:
                cell.fill=PatternFill('solid', fgColor='253C58')
                cell.font=Font(color='FFFFFF', bold=True)
                cell.alignment=Alignment(wrap_text=True,vertical='center')
            audit.row_dimensions[2].height=30
            for row in audit.iter_rows(min_row=3):
                row[-1].alignment=Alignment(wrap_text=True,vertical='center')
                audit.row_dimensions[row[0].row].height=34
            for letter,width in zip('ABCDEFG',(20,25,14,15,18,34,75),strict=True):
                audit.column_dimensions[letter].width=width
            audit.freeze_panes='A3'
            audit.auto_filter.ref=f'A2:G{audit.max_row}'
        with tempfile.NamedTemporaryFile(dir=output_file.parent, suffix='.xlsx', delete=False) as stream:
            pending = Path(stream.name)
        book.save(pending)
        if output_file.exists():
            raise ValueError(f'Tệp đích đã tồn tại: {output_file}')
        pending.rename(output_file)
    finally:
        book.close()
        if pending is not None:
            pending.unlink(missing_ok=True)
    print(f'Đã đọc {reviewed} câu, thay đổi {changed} câu. Đã xuất {output_file}.')
    if formulas:
        print(f'Có {formulas} ô công thức ở cột nguồn. Các ô kết quả tương ứng để trống.', file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--input', type=Path, help='File Excel .xlsx đầu vào')
    mode.add_argument('--text', help='Một bình luận cần chuẩn hóa')
    parser.add_argument('--output',type=Path,help='File Excel .xlsx mới sẽ xuất')
    parser.add_argument('--sheet',help='Tên sheet cần xử lý')
    parser.add_argument('--column',help='Tiêu đề cột. Có thể truyền chữ cột khi đi kèm --header-row.')
    parser.add_argument('--output-column',help='Tiêu đề cột kết quả. Cập nhật cột này trong file xuất nếu đã có.')
    parser.add_argument('--header-row',type=int,help='Số hàng chứa tiêu đề, bắt đầu từ 1')
    parser.add_argument('--suggest',action='store_true',help='Thêm sheet gợi ý chính tả từ tần suất và ngữ cảnh trong Excel đầu vào')
    args = parser.parse_args()
    if args.header_row is not None and args.header_row < 1:
        parser.error('--header-row phải lớn hơn hoặc bằng 1')
    if args.text is not None:
        if args.suggest or any(value is not None for value in (args.output,args.sheet,args.column,args.header_row,args.output_column)):
            parser.error('--text chỉ nhận một câu, không dùng kèm tham số Excel')
        print(normalize_v2(args.text))
        return
    if args.output is None:
        parser.error('--input cần đi kèm --output')
    try:
        export_workbook(args.input,args.output,args.sheet,args.column,args.header_row,
                        suggest=args.suggest, output_column=args.output_column or OUTPUT_HEADER)
    except (ValueError,OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()

