"""Create local-only G.3.2 diagnostics from sealed G.3.1 OOF predictions."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.baseline.legacy_error_analysis import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='outputs/phase_g32/error_analysis_v3')
    args = parser.parse_args()
    result = analyze(args.output)
    print({'status': result['status'], 'predictions': result['predictions']})


if __name__ == '__main__':
    main()
