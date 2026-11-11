"""Import complete human quality decisions without changing sentiment or releasing pilot."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.quality_workbook import import_review
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--coordinator',type=Path,default=Path('outputs/phase_i2/v2/workbook_input.local.json'))
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print({'imported':import_review(a.input,a.coordinator,a.output)})
