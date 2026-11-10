"""Audit candidate posts against sealed local metadata and selection history."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.exposure import audit


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--master',type=Path,default=Path('outputs/phase_g/master'))
    p.add_argument('--availability',type=Path,default=Path('outputs/phase_g/blind_test/availability.json'))
    p.add_argument('--output',type=Path,default=Path('outputs/phase_g/exposure_audit'))
    a=p.parse_args();r=audit(a.master,a.availability,a.output)
    print({k:r[k] for k in ('status','posts','status_counts','confirmed_unused','unreadable_evidence')})


if __name__=='__main__':main()
