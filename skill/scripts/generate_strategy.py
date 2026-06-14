"""Emit a family's base spec as editable JSON (the starting point for a custom
hypothesis). Usage:
  python skill/scripts/generate_strategy.py --family xs_momentum --out specs/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from strategies.families import FAMILIES


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=sorted(FAMILIES), required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "specs")
    args = ap.parse_args()
    spec = FAMILIES[args.family]()
    path = args.out / f"{spec.name}.json"
    spec.to_json(path)
    print(f"wrote {path} — edit hypothesis/grid, then run falsify_strategy.py --spec {path}")


if __name__ == "__main__":
    main()
