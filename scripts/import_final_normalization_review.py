"""Import completed 150-row patch review, without activating annotation text."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.normalization_workbook import import_review,import_cleaning
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--coordinator',type=Path,default=Path('outputs/phase_i4_1/v2/workbook_input.local.json'));p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cleaning-v3-2',action='store_true',help='Import strict ACCEPT/REJECT five-column candidate review; blank remains pending')
    p.add_argument('--human-convention',type=Path,help='Explicit workbook/coordinator hash-bound human interpretation; v3.2 only')
    a=p.parse_args()
    if a.human_convention and not a.cleaning_v3_2:p.error('--human-convention requires --cleaning-v3-2')
    r=import_cleaning(a.input,a.coordinator,a.output,a.human_convention) if a.cleaning_v3_2 else import_review(a.input,a.coordinator,a.output)
    print({'status':r['status'],'rows':r['rows'],**({'decision_counts':r['decision_counts']} if 'decision_counts' in r else {})})
