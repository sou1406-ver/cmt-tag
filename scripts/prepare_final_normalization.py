"""Build/audit focused raw-derived normalization proposals without annotation release."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.final_normalization_audit import build
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,default=Path('configs/phase_i4_1.json'))
    p.add_argument('--output',type=Path,default=Path('outputs/phase_i4_1/v2'));a=p.parse_args();r=build(a.config,a.output)
    print({k:r[k] for k in ('status','rows','review_rows','annotation_pointer_updated')})
