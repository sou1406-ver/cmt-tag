"""Select explicit format boundary cases from immutable I.3 corpus."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.common import ROOT,read_jsonl,csv_rows,save,staged,seal,sha
from src.dataset.format_sample import select
if __name__=='__main__':
    root=ROOT/'outputs/phase_i3/v3';frequency,_=csv_rows((root/'token_frequency.local.csv').read_bytes())
    rows,summary=select(read_jsonl(root/'corpus.local.jsonl'),{r['token']:int(r['occurrences']) for r in frequency})
    if len(rows)!=200:raise ValueError('Not enough non-test validation rows')
    with staged(ROOT/'outputs/phase_i3/validation_v1') as out:
        save(out/'workbook_input.local.json',rows);save(out/'sampling.json',summary)
        seal(out,dict(status='PENDING_HUMAN_FORMAT_APPROVAL',rows=200,source_manifest_sha256=sha(root/'manifest.json')))
    print(summary)
