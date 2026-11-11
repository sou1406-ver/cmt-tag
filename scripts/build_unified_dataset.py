"""Prepare the fixed human-only unified corpus and normalization/fold audits."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.unified import build


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path('configs/unified_dataset.json'))
    p.add_argument('--output',type=Path,default=Path('outputs/phase_g3/unified'))
    a=p.parse_args();r=build(a.config,a.output)
    print({k:r[k] for k in ('status','rows','labels','blocked_fold_views','basic_new_duplicates','normalized_conflicts')})


if __name__=='__main__':main()
