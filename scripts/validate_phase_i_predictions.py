"""Validate real Codex/Claude/Gemini prediction files against the local Phase I pilot."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dataset.common import load, read_jsonl, save, write_csv
from src.dataset.phase_i import consensus, validate_predictions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot-dir', type=Path, default=Path('outputs/phase_i/v5'))
    parser.add_argument('--predictions-dir', type=Path, required=True)
    parser.add_argument('--consensus', action='store_true')
    args = parser.parse_args()
    manifest = load(args.pilot_dir/'blind_input_manifest.local.json')
    pilot = read_jsonl(args.pilot_dir/'pilot_rows.local.jsonl') if (args.pilot_dir/'pilot_rows.local.jsonl').exists() else None
    if pilot is None:
        from src.dataset.common import csv_rows
        rows, _ = csv_rows((args.pilot_dir/'pilot_500_annotation_input.csv').read_bytes())
        ids = [row['id'] for row in rows]
    else:
        ids = [row['id'] for row in pilot]
    paths = {name: args.predictions_dir/f'{name}_predictions.csv' for name in ('codex','claude','gemini')}
    metadata_paths = {name: args.predictions_dir/f'{name}_metadata.json' for name in paths}
    validated = {}
    for name in ('codex','claude','gemini'):
        if not paths[name].exists() or not metadata_paths[name].exists():
            if args.consensus:
                raise FileNotFoundError('Consensus is unavailable until all three real result files and metadata sidecars exist')
            continue
        validated[name] = validate_predictions(paths[name], metadata_paths[name], ids)
    if args.consensus:
        if set(validated) != {'codex','claude','gemini'}:
            raise FileNotFoundError('Consensus is unavailable until all three result sets are present')
        predictions = {}
        for name, path in paths.items():
            from src.dataset.common import csv_rows
            predictions[name] = csv_rows(path.read_bytes())[0]
        results = consensus(predictions)
        write_csv(args.predictions_dir/'consensus.local.csv', results, ['id','status','label','label_source'])
        print({'consensus_rows': len(results), 'labels_are_gold': False})
    else:
        print({name: {'rows': value['rows'], 'statuses': value['status_counts'], 'labels': value['label_counts']}
               for name, value in validated.items()})


if __name__ == '__main__':
    main()
