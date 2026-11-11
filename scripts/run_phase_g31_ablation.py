"""Run the fixed G.3.1 direct-isolation A/B/C/D development comparison."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.baseline.direct_leakage_ablation import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/normalization_ablation_direct.json'))
    parser.add_argument('--output', type=Path, default=Path('outputs/phase_g31/ablation'))
    args = parser.parse_args()
    result = run(args.config, args.output)
    print({'status': result['status'], 'fits': result['fits'],
           'reference_A_macro_f1': result['reference_A_macro_f1']})


if __name__ == '__main__':
    main()
