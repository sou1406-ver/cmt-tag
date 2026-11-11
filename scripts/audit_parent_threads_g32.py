"""Verify annotated Facebook parent/reply metadata against exact master provenance."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dataset.parent_thread_audit import write_audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='outputs/phase_g32/parent_audit_04')
    args = parser.parse_args()
    result = write_audit(args.output)
    print({'status': result['status'], 'rows': result['rows']})


if __name__ == '__main__':
    main()
