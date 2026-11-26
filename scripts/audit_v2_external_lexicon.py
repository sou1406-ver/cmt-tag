"""Rank ViLexNorm mappings for review using V2 development comments."""

import argparse
from collections import Counter, defaultdict
import csv
from difflib import SequenceMatcher
from pathlib import Path
import re

from openpyxl import load_workbook

from scripts.chuan_hoa_binh_luan_v2 import (
    LITERAL_SLANG, OPAQUE, REVIEW, folded_word, normalize_comment, technical_text,
)
from src.dataset.common import ROOT, save, sha
from src.preprocessing.model import reduce_elongation


WORKBOOK = ROOT / 'outputs/02_Du_lieu_va_nhan/01_Crawl_va_nguon_goc/Cmt_V2_ban_chuan.xlsx'
SOURCES = ROOT / 'data/local_resources/lexical_normalization'
VILEXNORM = SOURCES / 'vilexnorm-train-1070c6b.csv'
VIET74K = SOURCES / 'viet74k-688b095.txt'
DEV_ROLES = {'TRAIN_CANDIDATE', 'CORPUS'}
TOKEN = re.compile(r'\w+|[^\w\s]')
PROTECTED_FORMS = LITERAL_SLANG | {
    'đéo', 'đếch', 'đek', 'déo', 'deo', 'éo', 'méo', 'lol', 'địt', 'mịa', 'mệ',
}
REVIEW_PROFANITY = PROTECTED_FORMS | {'cl', 'qq', 'quãi', 'tró', 'moẹ', 'mọe', 'mie'}
AMBIGUOUS_FORMS = set('th ch nh cf cn tp cs nt lm lp ac ce gd tk bh kb pà pé đk đh hs ty ca'.split())
DOUBLED_LETTER = re.compile(r'([^\W\d_])\1+')


def screening_reasons(row, locked):
    source = row['source']
    target = row['targets'][0]
    removed_repeat = DOUBLED_LETTER.sub(r'\1', source)
    elongated = reduce_elongation(source) != source or (
        source != removed_repeat and folded_word(removed_repeat) == folded_word(target['text'])
    )
    checks = [
        (source in locked, 'Đã có trong bảng ánh xạ cũ'),
        (bool(REVIEW_PROFANITY.intersection((source + ' ' + target['text']).split())),
         'Từ tục hoặc biến thể cần giữ'),
        (source in AMBIGUOUS_FORMS, 'Viết tắt ngắn đa nghĩa'),
        (elongated, 'Chữ kéo dài'),
        (row['in_dictionary'], 'Dạng gốc có trong Viet74K'),
        (not target['in_dictionary'], 'Dạng đề xuất vắng trong Viet74K'),
        (target['rows'] < 5, 'Dưới 5 câu hỗ trợ'),
        (target['rows'] * 10 < row['external_rows'] * 7, 'Tỷ lệ hỗ trợ dưới 70%'),
    ]
    return [reason for excluded, reason in checks if excluded]


def external_mappings(path):
    supported = defaultdict(Counter)
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    originals = []
    for row in rows:
        original = TOKEN.findall(technical_text(row['original']).casefold())
        normalized = TOKEN.findall(technical_text(row['normalized']).casefold())
        originals.append(original)
        edits = set()
        for tag, i, j, k, l in SequenceMatcher(None, original, normalized, autojunk=False).get_opcodes():
            left, right = original[i:j], normalized[k:l]
            if (tag == 'replace' and 1 <= len(left) <= 3 and 1 <= len(right) <= 3
                    and all(token.isalpha() for token in left + right)
                    and not PROTECTED_FORMS.intersection(left + right)):
                source = ' '.join(left)
                if len(source) >= 2:
                    edits.add((source, ' '.join(right)))
        for source, target in edits:
            supported[source][target] += 1
    return supported, originals


def phrase_hits(tokens, candidates):
    """Yield candidate phrases with their starting token index."""
    words = [token.casefold() for token in tokens]
    for index, token in enumerate(words):
        for size, forms in candidates.get(token, {}).items():
            source = ' '.join(words[index:index + size])
            if source in forms:
                yield source, index, size


def audit(workbook, vilexnorm, viet74k, *, min_external=3, min_v2=3):
    input_hashes = {path.name: sha(path) for path in (workbook, vilexnorm, viet74k)}
    supported, originals = external_mappings(vilexnorm)
    candidates = defaultdict(lambda: defaultdict(set))
    for source, targets in supported.items():
        if max(targets.values()) >= min_external:
            first, *rest = source.split()
            candidates[first][len(rest) + 1].add(source)
    external = Counter(source for tokens in originals
                       for source in {hit[0] for hit in phrase_hits(tokens, candidates)})
    dictionary = {technical_text(line).casefold()
                  for line in viet74k.read_text(encoding='utf-8-sig').splitlines()} - {''}
    raw_counts = Counter()
    remaining = Counter()
    occurrences = Counter()
    examples = defaultdict(list)
    row_count = 0
    book = load_workbook(workbook, read_only=True, data_only=True)
    try:
        locked = defaultdict(set)
        for source, target, count in book['Viết tắt đã sửa'].iter_rows(min_row=5, max_col=3, values_only=True):
            if isinstance(source, str) and isinstance(target, str) and isinstance(count, int):
                locked[technical_text(source).casefold()].add(target)
        for row in book['Bình luận'].iter_rows(min_row=5, max_col=7):
            if row[6].value not in DEV_ROLES:
                continue
            raw = row[2].value
            if not isinstance(raw, str):
                raise ValueError('Missing source text in an eligible V2 row')
            current = normalize_comment(raw, apply_reviewed_variants=False)
            row_count += 1
            raw_tokens = TOKEN.findall(OPAQUE.sub(' | ', technical_text(raw)))
            raw_forms = Counter(hit[0] for hit in phrase_hits(raw_tokens, candidates))
            raw_counts.update(raw_forms.keys())
            remaining_forms = Counter()
            for segment in OPAQUE.split(current):
                tokens = list(TOKEN.finditer(segment))
                for source, start, size in phrase_hits([token[0] for token in tokens], candidates):
                    if source not in raw_forms:
                        continue
                    remaining_forms[source] += 1
                    if remaining_forms[source] == 1 and len(examples[source]) < 2:
                        left, right = tokens[start].start(), tokens[start + size - 1].end()
                        context = (segment[max(0, left - 43):left] + '[' + segment[left:right] + ']'
                                   + segment[right:right + 43]).strip()
                        if context not in examples[source]:
                            examples[source].append(context)
            remaining.update(remaining_forms.keys())
            occurrences.update(remaining_forms & raw_forms)
    finally:
        book.close()
    if any(sha(path) != input_hashes[path.name] for path in (workbook, vilexnorm, viet74k)):
        raise ValueError('An input changed while collecting suggestions')

    suggestions = []
    for source, count in remaining.most_common():
        if count < min_v2:
            continue
        targets = sorted(supported[source].items(), key=lambda pair: (-pair[1], pair[0]))
        row = dict(source=source, targets=[dict(text=target, rows=n, in_dictionary=target in dictionary)
                                         for target, n in targets],
                   external_rows=external[source], in_dictionary=source in dictionary,
                   v2_raw_rows=raw_counts[source], v2_remaining_rows=count,
                   v2_remaining_occurrences=occurrences[source], reviewed_spelling=source in REVIEW,
                   contexts=examples[source], locked_targets=sorted(locked.get(source, ())))
        row['excluded_reasons'] = screening_reasons(row, locked)
        suggestions.append(row)
    suggestions.sort(key=lambda row: (-row['v2_remaining_rows'], -row['targets'][0]['rows'], row['source']))
    return dict(v2_rows=row_count, external_train_rows=len(originals), dictionary_entries=len(dictionary),
                min_external_rows=min_external, min_v2_rows=min_v2, suggestions=suggestions,
                input_sha256=input_hashes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path, default=WORKBOOK)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.workbook, VILEXNORM, VIET74K)
    save(args.output, report)
    print(f"{report['v2_rows']} V2 rows, {len(report['suggestions'])} forms for review")
