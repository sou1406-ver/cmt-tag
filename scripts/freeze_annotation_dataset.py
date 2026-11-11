"""Future freeze/export CLI; requires complete real reviews and explicit approval files."""
from pathlib import Path
import sys,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.quality_release import freeze,export
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    f=sub.add_parser('freeze');f.add_argument('--source',type=Path,default=Path('outputs/phase_j/v2'))
    for name in ('format','normalization','domain','holdout'):f.add_argument('--'+name+'-import',type=Path,required=True)
    e=sub.add_parser('export');e.add_argument('--source',type=Path,default=Path('outputs/phase_j/v2'));e.add_argument('--frozen',type=Path,required=True);e.add_argument('--candidate',type=Path,required=True)
    for parser in (f,e):parser.add_argument('--approval',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    m=freeze(a.source,{name:getattr(a,name+'_import') for name in ('format','normalization','domain','holdout')},a.approval,a.output) if a.command=='freeze' else export(a.frozen,a.source,a.candidate,a.approval,a.output)
    print({k:m[k] for k in ('status','rows')})
