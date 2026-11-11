"""Build raw-derived plain text and local quality-workbook inputs."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.phase_i2 import build
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,default=Path('configs/phase_i2.json'))
    p.add_argument('--output',type=Path,default=Path('outputs/phase_i2/v2'));a=p.parse_args()
    r=build(a.config,a.output);print({k:v for k,v in r.items() if k not in ('audit_strata','token_categories','duplicates')})
