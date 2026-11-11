"""Audit the fixed legacy source and prepare a blinded human train-annotation task."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.legacy_audit import audit


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path('configs/legacy_audit.json'))
    p.add_argument('--output',type=Path,default=Path('outputs/phase_g2/legacy_audit'))
    a=p.parse_args();r,m=audit(a.config,a.output)
    print({k:r[k] for k in ('rows','unique_normalized_texts','near_duplicate_pairs','trust_groups','train_candidates',
                           'annotation_candidates_selected','connected_to_exposed_master_component','independent_test_candidates')})
    if m['status']=='PARTIAL':p.exit(2,'Insufficient safe candidates; no annotation workbook claimed\n')


if __name__=='__main__':main()
