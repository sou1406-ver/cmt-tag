"""Import completed format review into a new local artifact, without label changes."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.format_workbook import import_review
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--coordinator',type=Path,default=Path('outputs/phase_i3/validation_v1/workbook_input.local.json'))
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();print({'imported':import_review(a.input,a.coordinator,a.output)})
