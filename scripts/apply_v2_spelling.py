"""Audit clear typing mistakes in the V2 reading copy."""

import argparse
from collections import Counter
from pathlib import Path

from scripts.chuan_hoa_binh_luan_v2 import NON_DEV, REVIEW, REVIEW_PATTERN, correct, eligible_matches
from src.dataset.common import load, read_jsonl, save, verify


def context(text, start, end, phrase):
    left = max(0, start-75)
    right = min(len(text), end+85)
    return ('“' + ('… ' if left else '') + text[left:start] + '[' + phrase + ']'
            + text[end:right] + (' …' if right < len(text) else '') + '”')


def audit(view, excel_input, output):
    manifest = verify(view)
    if not manifest.get('reading_copy') or not manifest.get('profanity_preserved_verbatim'):
        raise ValueError('Use the verified V2 reading copy')
    source = read_jsonl(view/'V2_sau_chuan_hoa_viet_tat.local.jsonl')
    by_id = {r['comment_id']: r for r in source}
    payload = load(excel_input)
    applied, pending = Counter(), Counter()
    samples = {}
    changed = 0
    eligible = 0
    for row in payload['rows']:
        record = by_id[row[3]]
        if row[0]!=record['text_abbreviations'] or row[1]!=record['label']:
            raise ValueError('Excel input differs from the sealed text or labels')
        if record['split_role'] in NON_DEV:
            continue
        eligible += 1
        text = row[0]
        corrected, edits = correct(text)
        for start,end,value,replacement in edits:
            key = (value.casefold(), replacement.casefold())
            applied[key] += 1
            samples.setdefault(('fixed',key), (context(text,start,end,value), context(text,start,end,replacement)))
        for match in eligible_matches(REVIEW_PATTERN, corrected):
            key = match[0].casefold()
            pending[key] += 1
            samples.setdefault(('pending',key), (context(corrected,match.start(),match.end(),match[0]), ''))
        if edits:
            row[0] = corrected
            changed += 1
    payload['stats'].append(['Đã sửa chính tả', changed, f'Rà {eligible:,} câu ngoài T2 và hàng chờ test'.replace(',','.')])
    payload['spelling'] = [
        ['Đã sửa', a, b, n, *samples['fixed',(a,b)], '']
        for (a,b),n in applied.most_common()
    ] + [
        ['Cần rà', key, REVIEW[key][0], n, *samples['pending',key], REVIEW[key][1]]
        for key,n in pending.most_common()
    ]
    payload['spelling_summary'] = dict(eligible=eligible, changed=changed, replacements=applied.total(),
                                       review_terms=len(pending))
    save(output,payload)
    print(payload['spelling_summary'])


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--view', type=Path, required=True)
    parser.add_argument('--excel-input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit(args.view,args.excel_input,args.output)
