"""Reserve a blind test only when independence evidence and quotas suffice."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dataset.blind import prepare


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=Path('configs/blind_test.json'))
    p.add_argument('--output', type=Path, default=Path('outputs/phase_g/blind_test'))
    args = p.parse_args(); result = prepare(args.config, args.output)
    print(json.dumps({k: result[k] for k in ('status','target','selected','eligible_before_quota','attainable_under_quota','blocker')}))
    if result['status'] == 'PARTIAL': p.exit(2, 'PARTIAL: no test or gold fabricated. See availability.json\n')


if __name__ == '__main__': main()
