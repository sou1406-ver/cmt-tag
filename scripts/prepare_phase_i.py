"""Build local Phase I corpus, clean views and blinded annotation pilot."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dataset.phase_i import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/phase_i.json'))
    parser.add_argument('--output', type=Path, default=Path('outputs/phase_i/v5'))
    args = parser.parse_args()
    result = build(args.config, args.output)
    print({key: result[key] for key in ('phase', 'status', 'dataset_version', 'rows', 'selected')})


if __name__ == '__main__':
    main()
