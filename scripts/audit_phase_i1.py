"""Prepare local quality audit and unapproved candidate pilot; no API or training."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.phase_i1 import build

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path('configs/phase_i1.json'))
    p.add_argument('--output',type=Path,default=Path('outputs/phase_i1/v2'))
    a=p.parse_args(); result=build(a.config,a.output)
    print({k:result[k] for k in ('rows','quality','domain','repetition_risk','exclude_candidates','alias_replacements','pool','pilot','audit','status')})
