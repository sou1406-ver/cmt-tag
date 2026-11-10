"""Run Phase E.1 against immutable Phase E artifacts."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.baseline.bow_robustness import main

if __name__=='__main__':main()
