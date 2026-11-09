"""Synthetic fixture only. No real annotation/gold is created by this command."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from src.annotation.core import GUIDELINE, GUIDELINE_VERSION, now, release, save
from src.data.importers import canonical_json, digest
from src.data.pipeline import ROOT, prepare_data
from src.data.validation import read_jsonl


def make(output):
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    source=ROOT/'tests/fixtures/baseline_synthetic.json'
    cfg={'schema_version':'1.0','inputs':[{'path':str(source),'source_dataset':'synthetic_210',
         'format':'json','post_namespace':'synthetic','columns':{'text_raw':'body','post_id':'pid'},
         'license':'synthetic fixture','privacy':'no real people'}],
         'quality':{'ui_strings':[],'spam_patterns':[]},
         'near_duplicate':{'threshold':0.9,'min_chars':10000,'shingle_size':3},
         'split':{'seed':42,'ratios':{'train':0.6,'dev':0.2,'test':0.2}}}
    save(output/'config.json',cfg)
    report,processed,_=prepare_data(output/'config.json',output/'phase_b')
    labels={r['body']:r['expected_label'] for r in json.loads(source.read_text(encoding='utf-8'))}
    event_path=output/'synthetic_events.jsonl'
    with event_path.open('x',encoding='utf-8') as f:
        for r in read_jsonl(processed/'records.jsonl'):
            # Human-shaped provenance is deliberately marked fixture-only.
            # These are authored synthetic expected outputs, never real humans.
            e={'id':r['id'],'dataset_version':report['data_version'],'guideline_sha256':digest(GUIDELINE.read_bytes()),
               'cohort':'synthetic','decision':{'label_source':'human','label':labels[r['text_raw']],
               'status':'LABELED','confirmed':True,'is_pseudo':False,'needs_review':False,
               'annotator_id':'SYNTHETIC_EXPECTED_OUTPUT','evidence_mode':'blind','decided_at':now(),
               'guideline_version':GUIDELINE_VERSION,'fixture_only':True}}
            f.write(canonical_json(e)+'\n')
    return release(output/'phase_b',report['data_version'],[event_path],output/'release',synthetic=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',type=Path,required=True)
    print(make(p.parse_args().output))
