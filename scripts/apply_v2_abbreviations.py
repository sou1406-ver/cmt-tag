"""Expand reviewed abbreviations in the merged V2 corpus, then join saved labels."""

import argparse
from collections import Counter
from pathlib import Path

from openpyxl import load_workbook

from src.dataset.common import ROOT, read_jsonl, save, seal, sha, staged, verify, write_csv, write_jsonl
from scripts.chuan_hoa_binh_luan_v2 import (
    INTENSIFIERS, INTERJECTIONS, LITERAL_SLANG, NAMES, OPAQUE, SETTLED, WORD, make_normalizer,
)


DATA = ROOT / 'outputs/02_Du_lieu_va_nhan'
SOURCE = DATA / '05_Chuan_hoa_ky_thuat_V2'
SOURCE_FILE = 'V2_chuan_hoa_va_giu_nhan.local.jsonl'
GLOSSARY = ROOT / 'outputs/01_T2_va_cho_gan/Bang_viet_tat_da_duyet_cmt_tag.xlsx'
SUPPLEMENT = ROOT / 'outputs/01_T2_va_cho_gan/Viet_tat_can_bo_sung_V2.xlsx'
OUTPUT = DATA / '10_Chuan_hoa_viet_tat_giu_sac_thai_V2'

def load_glossary(path):
    with path.open('rb') as stream:
        book = load_workbook(stream, read_only=True, data_only=True)
        try:
            return {
                values[0].strip(): str(values[2] or '').strip()
                for values in book['Từ cần tra'].iter_rows(min_row=5, values_only=True)
                if isinstance(values[0], str) and values[0].strip()
            }
        finally:
            book.close()


def load_supplement(path):
    with path.open('rb') as stream:
        book = load_workbook(stream, read_only=True, data_only=True)
        try:
            decisions = {}
            for key, _, _, meaning, note, *_ in book['Điền viết tắt'].iter_rows(min_row=5, values_only=True):
                if key and (meaning or note):
                    decisions[str(key).strip().casefold()] = (str(meaning or '').strip(), str(note or '').strip())
            return decisions
        finally:
            book.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--glossary', type=Path, default=GLOSSARY)
    parser.add_argument('--supplement', type=Path, default=SUPPLEMENT)
    parser.add_argument('--reading-copy', action='store_true',
                        help='Prepare a readable copy while preserving profanity and intensifiers verbatim')
    parser.add_argument('--excel-input', type=Path, help='Optional JSON for the Excel viewer')
    args = parser.parse_args()
    verify(SOURCE)
    input_paths = [SOURCE / 'manifest.json', SOURCE / SOURCE_FILE,
                   args.glossary.resolve(), args.supplement.resolve(), Path(__file__).resolve(),
                   Path(__file__).with_name('chuan_hoa_binh_luan_v2.py').resolve()]
    input_hashes = {path: sha(path) for path in input_paths}
    hashes = {str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path): checksum
              for path, checksum in input_hashes.items()}
    glossary = load_glossary(args.glossary)
    supplemental = load_supplement(args.supplement)
    normalize = make_normalizer(glossary, supplemental, reading_copy=args.reading_copy)
    source = read_jsonl(SOURCE / SOURCE_FILE)
    labels = {row['comment_id']: (row['label'], row['label_source']) for row in source}
    if len(labels) != len(source):
        raise ValueError('Duplicate corpus comment IDs')
    changed = Counter()
    held = Counter()
    mappings = Counter()
    totals = Counter()
    by_role = {}
    results = []
    for row in source:
        text, applied, skipped = normalize(row['text_normalized'], replacements=mappings)
        label, label_source = labels[row['comment_id']]
        result = dict(row, text_abbreviations=text, abbreviation_rules=applied,
                      label=label, label_source=label_source)
        results.append(result)
        totals.update({'rows': 1, 'changed': bool(applied), 'with_labels': bool(label),
                       'changed_with_label': bool(applied and label),
                       'changed_pending': bool(applied and not label)})
        totals.update({row['cohort']: 1, row['cohort'] + '_changed': bool(applied)})
        by_role.setdefault(row['split_role'], Counter()).update(rows=1, changed=bool(applied), replacements=len(applied))
        changed.update(applied)
        held.update(skipped)
    assert all({key: new[key] for key in old} == old for old, new in zip(source, results, strict=True))
    verify(SOURCE)
    if any(sha(path) != checksum for path, checksum in input_hashes.items()):
        raise ValueError('Normalization inputs changed during the run')
    with staged(args.output) as directory:
        write_jsonl(directory / 'V2_sau_chuan_hoa_viet_tat.local.jsonl', results)
        save(directory / 'thong_ke.json', dict(totals=totals, applied=changed, kept=held,
                                             by_role=by_role, supplemental_decisions=len(supplemental)))
        mapping_rows = [dict(abbreviation=key, replacement=value, count=count)
                        for (key, value), count in sorted(mappings.items(), key=lambda item: (-item[1], item[0]))]
        write_csv(directory/'anh_xa_da_ap_dung.csv', mapping_rows, ['abbreviation', 'replacement', 'count'])
        seal(directory, dict(kind='V2_ABBREVIATION_VIEW', source_sha256=hashes,
                             spelling_correction=False, relabeled=False,
                             profanity_preserved_verbatim=args.reading_copy, reading_copy=args.reading_copy))
    verify(args.output)
    if args.excel_input:
        fields = ['Sau chuẩn hóa viết tắt', 'Nhãn cũ', 'Trước chuẩn hóa viết tắt',
                  'ID bình luận', 'Mã phim', 'Nguồn', 'Vai trò dữ liệu',
                  'Viết tắt đã đổi', 'ID bài', 'Nguồn nhãn']
        visible = [r for r in results
                   if r['text_normalized'] or r['label'] or r['clean_status_source'] != 'EXCLUDE']
        rows = [[r['text_abbreviations'], r['label'], r['text_normalized'], r['comment_id'],
                 r['movie_id'], r['source_name'], r['split_role'],
                 ', '.join(r['abbreviation_rules']), r['post_id'], r['label_source']] for r in visible]
        stats = [
            ['Bình luận trong Excel', len(visible), 'Dữ liệu V2 để đối chiếu câu trước và sau chuẩn hóa'],
            ['Dòng trống đã loại khỏi Excel', len(results) - len(visible), 'Nguồn đã đánh dấu EXCLUDE và chưa có nhãn'],
            ['Bình luận có thay đổi', totals['changed'], 'Chỉ chuẩn hóa viết tắt và cách diễn đạt đã duyệt'],
            ['Bình luận có nhãn cũ', totals['with_labels'], 'Nhãn và nguồn nhãn ghép theo ID bình luận'],
            ['Đã có nhãn và được chuẩn hóa', totals['changed_with_label'], 'Giữ nguyên nhãn đã có'],
            ['Chưa có nhãn và được chuẩn hóa', totals['changed_pending'], 'Ô nhãn để trống'],
            ['Lượt thay viết tắt', changed.total(), 'Một bình luận có thể chứa nhiều từ được thay'],
        ]
        save(args.excel_input, dict(fields=fields, rows=rows, stats=stats))
    print(dict(totals))
    print(changed.most_common(15))


if __name__ == '__main__':
    main()
