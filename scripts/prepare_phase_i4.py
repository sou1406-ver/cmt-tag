"""Prepare human semantic review and readiness evidence, without release or preprocessing."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.phase_i4 import build
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,default=Path('configs/phase_i4.json'))
    p.add_argument('--output',type=Path,default=Path('outputs/phase_i4/v5'));a=p.parse_args();r=build(a.config,a.output)
    print({k:r[k] for k in ('phase','status','review_rows','holdout_rows','format_status')})
