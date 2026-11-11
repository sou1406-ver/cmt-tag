"""Import real domain and spam decisions without freezing or releasing data."""
from pathlib import Path
import sys,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.quality_review import import_review
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--coordinator',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();m=import_review(a.input,a.coordinator,a.output);print({k:m[k] for k in ('status','kind','rows')})
