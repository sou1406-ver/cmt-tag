"""Create a new immutable Phase G master from accessible sources only."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dataset.master import build


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=Path('configs/master_dataset.json'))
    p.add_argument('--output', type=Path, default=Path('outputs/phase_g/master'))
    args = p.parse_args()
    result = build(args.config, args.output)
    print(json.dumps({k: result[k] for k in ('status','dataset_version','observations','records','human_decisions','movies','posts')}))


if __name__ == '__main__': main()
