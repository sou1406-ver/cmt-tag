"""Import complete, real human domain review and compute sample-only diagnostics."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.phase_i4 import import_domain
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--coordinator',type=Path,default=Path('outputs/phase_i4/v5/workbook_input.local.json'))
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=import_domain(a.input,a.coordinator,a.output)
    print({k:r[k] for k in ('rows','off_topic_precision','off_topic_recall','off_topic_in_keep','false_exclusions')})
