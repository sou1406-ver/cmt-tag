"""Export the pending V2 annotation CSVs using normalize_v2."""

import argparse
from collections import defaultdict
from pathlib import Path

from scripts.chuan_hoa_binh_luan_v2 import normalize_v2
from src.dataset.common import ROOT, csv_rows, load, read_jsonl, seal, sha, staged, verify, write_csv


PENDING_ROOT = ROOT / 'outputs/01_T2_va_cho_gan'
QUEUE_INDEX = PENDING_ROOT / 'T2_da_khoa/cmt_cho_gan_chi_muc.local.csv'
CORPUS = ROOT / 'outputs/02_Du_lieu_va_nhan/05_Chuan_hoa_ky_thuat_V2/V2_chuan_hoa_va_giu_nhan.local.jsonl'
OUTPUT = PENDING_ROOT / '18_lo_da_chuan_hoa'
FIELDS = ['comment_id', 'text_clean']
GUIDES = {
    '01_Prompt_gan_nhan.md': ROOT / 'docs/annotation/AI_LABEL_PROMPT.md',
    '02_Guideline_gan_nhan.md': ROOT / 'docs/guidelines/SENTIMENT_GUIDELINE.md',
}


def export_batches(output):
    source_hashes = {}
    for path in (QUEUE_INDEX, CORPUS):
        digest = sha(path)
        if digest != load(path.parent / 'manifest.json')['output_sha256'][path.name]:
            raise ValueError(f'Frozen source changed: {path.name}')
        source_hashes[path.name] = digest
    index, _ = csv_rows(QUEUE_INDEX.read_bytes())
    pending = [row for row in read_jsonl(CORPUS) if row['split_role'] == 'PENDING_SUPPLEMENT']
    text_by_id = {row['comment_id']: row['text_source'] for row in pending}
    ids = [row['comment_id'] for row in index]
    if (len(ids) != 1731 or len(pending) != len(ids) or len(set(ids)) != len(ids)
            or set(ids) != text_by_id.keys() or any(not cid.isascii() or not cid.isdecimal() for cid in ids)):
        raise ValueError('The index and corpus must refer to the same 1,731 pending IDs')
    groups = defaultdict(list)
    for row in index:
        groups[int(row['chunk'])].append(row['comment_id'])
    if sorted(groups) != list(range(1, 19)):
        raise ValueError('The pending V2 queue must contain its 18 frozen batches')
    if any(sha(path) != source_hashes[path.name] for path in (QUEUE_INDEX, CORPUS)):
        raise ValueError('A frozen source changed during export')

    batches = {}
    with staged(output) as dest:
        for chunk, group in sorted(groups.items()):
            normalized = []
            excluded_empty = []
            changed = 0
            for cid in group:
                raw = text_by_id[cid]
                text = normalize_v2(raw)
                if text:
                    normalized.append({'comment_id': cid, 'text_clean': text})
                    changed += text != raw
                else:
                    excluded_empty.append(cid)
            name = f'cmt_cho_gan_{chunk:02}_chuan_hoa.csv'
            write_csv(dest / name, normalized, FIELDS)
            batches[name] = dict(rows=len(normalized), changed=changed, excluded_empty_ids=excluded_empty)
        for name, guide in GUIDES.items():
            (dest / name).write_bytes(guide.read_bytes())
        seal(dest, dict(kind='V2_NORMALIZED_ANNOTATION_BATCHES', text_view='normalize_v2',
                        normalizer_sha256=sha(ROOT / 'scripts/chuan_hoa_binh_luan_v2.py'),
                        source_sha256=source_hashes, input_count=len(ids), batches=batches,
                        row_count=sum(batch['rows'] for batch in batches.values()),
                        changed_count=sum(batch['changed'] for batch in batches.values())))
    return verify(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    manifest = export_batches(args.output)
    print(f"Exported {manifest['row_count']} normalized rows in {len(manifest['batches'])} batches. "
          f"Updated text in {manifest['changed_count']} rows.")
