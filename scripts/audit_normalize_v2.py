"""Compare the frozen normalization function with the V2 reading workbook."""

import argparse
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook

from scripts.chuan_hoa_binh_luan_v2 import (
    CORRECTIONS, NON_DEV, correct, normalize_abbreviations, normalize_reviewed_variants, technical_text,
)
from src.dataset.common import ROOT, save, seal, sha, staged, verify, write_jsonl


DEFAULT_WORKBOOK = ROOT / 'outputs/02_Du_lieu_va_nhan/01_Crawl_va_nguon_goc/Cmt_V2_ban_chuan.xlsx'


def audit(workbook, output):
    before = sha(workbook)
    book = load_workbook(workbook, read_only=True, data_only=True)
    comparisons = Counter()
    differences = []
    mappings = Counter()
    identifiers = set()
    try:
        spelling = {
            source: target for status,source,target in
            book['Chính tả'].iter_rows(min_row=5, max_col=3, values_only=True) if status == 'Đã sửa'
        }
        if spelling != CORRECTIONS:
            raise ValueError('The frozen spelling rules differ from the reviewed workbook')
        applied_in_workbook = Counter({
            (token,result):int(count) for token,result,count in
            book['Viết tắt đã sửa'].iter_rows(min_row=5,max_col=3,values_only=True)
            if token and count is not None
        })
        sheet = book['Bình luận']
        for old, _, raw, cid, _, _, role in sheet.iter_rows(min_row=5,max_col=7,values_only=True):
            if not isinstance(cid,str) or cid in identifiers or not isinstance(raw,str):
                raise ValueError('Missing or duplicate comment ID or source text')
            identifiers.add(cid)
            base, _, _ = normalize_abbreviations(technical_text(raw), replacements=mappings)
            previous, _ = correct(base)
            updated = normalize_reviewed_variants(previous)
            comparisons[role, 'rows'] += 1
            if previous != updated:
                comparisons[role, 'vilexnorm_changed'] += 1
            if old == updated:
                continue
            if old == previous:
                reason = 'vilexnorm_reviewed'
            elif role in NON_DEV and old == base:
                reason = 'spelling_applied_uniformly'
            else:
                reason = 'unresolved_mismatch'
            comparisons[role, reason] += 1
            differences.append(dict(id=cid, role=role, reason=reason, original=raw,
                                    excel=old, normalize_v2=updated))
    finally:
        book.close()
    if len(identifiers)!=14408 or comparisons['T2_SCORE','rows']!=613 or sha(workbook)!=before:
        raise ValueError('Workbook changed or missing part of the frozen V2 scope')
    if mappings != applied_in_workbook:
        raise ValueError('Abbreviation counts differ from the audit sheet')

    roles = sorted({role for role, _ in comparisons})
    result = dict(rows=len(identifiers), matches=len(identifiers)-len(differences), differences=len(differences),
                  unresolved=sum(n for (_, reason), n in comparisons.items() if reason == 'unresolved_mismatch'),
                  by_role={role:{reason:n for (key,reason),n in comparisons.items() if key==role} for role in roles},
                  abbreviation_mappings=len(mappings), gold_T_scored=False, workbook_updated=False)
    with staged(output) as work:
        save(work/'summary.json', result)
        write_jsonl(work/'differences.local.jsonl',differences)
        examples = sorted(differences,key=lambda r:(r['reason']!='unresolved_mismatch',r['role'],r['id']))[:30]
        lines = ['Đối chiếu văn bản V2. Các ví dụ giữ cục bộ.', f'Có {len(examples)} ví dụ trên {len(differences)} câu lệch.', '']
        for row in examples:
            lines.extend((f"{row['id']} · {row['role']} · {row['reason']}",
                          f"Gốc: {row['original']}", f"Excel: {row['excel']}",
                          f"normalize_v2: {row['normalize_v2']}", ''))
        (work/'examples.local.txt').write_text('\n'.join(lines),encoding='utf-8')
        seal(work,dict(kind='V2_TEXT_EQUIVALENCE_AUDIT', workbook_sha256=before,
                       normalization_sha256=sha(ROOT/'scripts/chuan_hoa_binh_luan_v2.py'),
                       gold_T_scored=False))
    verify(output)
    print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook',type=Path,default=DEFAULT_WORKBOOK)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    audit(args.workbook,args.output)
