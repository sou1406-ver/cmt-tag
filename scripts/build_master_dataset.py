"""Build/filter data; never approve a candidate or overwrite existing output."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--filter-canonical', type=Path, help='Verified canonical raw lineage')
    mode.add_argument('--quality-filter', type=Path, help='New derived tag/link version from an immutable filtered candidate')
    mode.add_argument('--config', type=Path, help='Prepare versioned records/splits from explicit input config')
    parser.add_argument('--legacy-max-characters', type=int, default=1000)
    parser.add_argument('--facebook-max-characters', type=int)
    parser.add_argument('--output', type=Path, default=Path('outputs/canonical/versions/filtered_20261112_final'))
    parser.add_argument('--output-root', type=Path, default=ROOT/'data')
    parser.add_argument('--quality-review', type=Path, default=ROOT/'outputs/quality_filter_review')
    args = parser.parse_args()
    try:
        if args.quality_filter:
            from src.dataset.quality_filter import filter_quality
            result = filter_quality(args.quality_filter,args.output,args.quality_review)
        elif args.filter_canonical:
            from src.dataset.master import filter_canonical
            result = filter_canonical(args.filter_canonical, args.output, args.legacy_max_characters, args.facebook_max_characters)
        else:
            from src.data.pipeline import prepare_data
            report, processed, splits = prepare_data(args.config, args.output_root)
            result = dict(data_version=report['data_version'], counts=report['counts'], warnings=report['warnings'],
                          report=str(processed/'report.json'), manifest=str(splits/'manifest.json'))
        print(json.dumps(result, ensure_ascii=True))
    except (ValueError, KeyError, OSError, UnicodeError) as exc:
        parser.exit(2, f'build/filter: {type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    main()
