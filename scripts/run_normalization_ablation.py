"""Run fixed G.3 experiments or emit a truthful PARTIAL when isolation fails."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.baseline.normalization_ablation import run


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path('configs/normalization_ablation.json'))
    p.add_argument('--output',type=Path,default=Path('outputs/phase_g3/ablation'))
    a=p.parse_args();r=run(a.config,a.output)
    print({k:r[k] for k in ('status','strict_experiment_fits','historical_reference_fits','reference_A_macro_f1')})
    if r['status']=='PARTIAL':p.exit(2,'Frozen folds violate strict master-component isolation; no qualified A/B/C/D comparison produced\n')


if __name__=='__main__':main()
