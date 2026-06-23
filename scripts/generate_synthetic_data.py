"""Generate the approved baseline synthetic history for ABC Cruise Lines."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.generator import DEFAULT_HISTORY_SEED, generate_synthetic_history


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize the approved ABC Cruise Lines baseline history."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_HISTORY_SEED,
        help="Only the approved baseline seed 510 is supported.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional CSV path to write the generated history. If omitted, print to stdout.",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    history = generate_synthetic_history(seed=args.seed)
    if args.output is not None:
        output_path = args.output.resolve()
        history.to_csv(output_path, index=False)
        print(f"Wrote {len(history)} synthetic history rows to {output_path}")
        return 0

    print(history.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
