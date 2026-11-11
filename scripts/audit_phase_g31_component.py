"""Create a metadata/hash-only Phase G.3.1 graph and fold audit."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dataset.common import ROOT, load, save, seal, sha, staged, verify
from src.dataset.component_audit import audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('outputs/phase_g31/audit'))
    args = parser.parse_args()
    master = ROOT/'outputs/phase_g/master'
    unified = ROOT/'outputs/phase_g3/unified'
    master_manifest = verify(master)
    unified_manifest = verify(unified)
    if sha(master/'manifest.json') != load('configs/unified_dataset.json')['master_manifest_sha256']:
        raise ValueError('Pinned Phase G master manifest changed')
    result = audit()
    result.update(master_manifest_sha256=sha(master/'manifest.json'),
                  unified_manifest_sha256=sha(unified/'manifest.json'),
                  master_status=master_manifest['status'], unified_status=unified_manifest['status'],
                  raw_text_written=False)
    with staged(args.output) as work:
        save(work/'component_and_fold_audit.json', result)
        seal(work, dict(status=result['direct_overlap_gate'], protocol=result['protocol'],
             master_manifest_sha256=result['master_manifest_sha256'],
             unified_manifest_sha256=result['unified_manifest_sha256'], raw_text_written=False))
    print({'status': result['direct_overlap_gate'], 'giant_records': result['master_graph']['giant_records'],
           'fb_posts': result['master_graph']['giant_facebook_post_count'], 'folds': len(result['folds'])})


if __name__ == '__main__':
    main()
