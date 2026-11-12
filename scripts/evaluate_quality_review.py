"""Compatibility entry point; prefer python -m src.dataset.quality_review."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.dataset.quality_review import main,evaluate
if __name__=='__main__':main(['evaluate']+sys.argv[1:])
