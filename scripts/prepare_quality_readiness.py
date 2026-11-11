"""Build Phase J proposals and same-ID review/holdout handoff; no release."""
from pathlib import Path
import sys,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.quality_readiness import build
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,default=Path('configs/phase_j_v1.json'));p.add_argument('--output',type=Path,default=Path('outputs/phase_j/v2'))
    a=p.parse_args();m=build(a.config,a.output);print({k:m[k] for k in ('status','rows','eligible_proposed','eligible_approved')})
