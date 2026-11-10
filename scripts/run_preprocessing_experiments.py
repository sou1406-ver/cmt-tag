"""Run the frozen Phase E preprocessing/feature comparison."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.baseline.preprocessing_experiments import main

if __name__=='__main__':main()
