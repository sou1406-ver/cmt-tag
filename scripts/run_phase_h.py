"""Run Phase H all folds or a single smoke/pilot model locally."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/phase_h/training.json")
    parser.add_argument("--data-config", default="configs/phase_h/data.json")
    parser.add_argument("--output")
    parser.add_argument("--model", choices=("phobert_v2", "visobert"))
    parser.add_argument("--fold", type=int, choices=(0, 1, 2))
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Run one synthetic forward/backward/eval step")
    args = parser.parse_args()
    if args.smoke:
        if not args.model:
            parser.error("--smoke requires --model")
        from src.transformer.smoke import run_smoke
        output = run_smoke(args.model, args.output or "outputs/phase_h/smoke_01", args.config, args.local_only)
        print(output)
        return
    from src.transformer.runner import run_phase_h
    output = run_phase_h(args.config, args.data_config, args.output, args.model, args.fold, args.local_only)
    print(output)


if __name__ == "__main__":
    main()
