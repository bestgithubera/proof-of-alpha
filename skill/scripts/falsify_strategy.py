"""One-command pipeline: family/spec -> evaluate grid -> falsify -> report.

Usage:
  python skill/scripts/falsify_strategy.py --family xs_momentum --out demo/output
  python skill/scripts/falsify_strategy.py --spec specs/my_idea.json --out demo/output
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from data_layer.panel import load_panel
from strategies.families import FAMILIES, evaluate_family
from strategies.spec import StrategySpec
from validation.core import TrialLedger
from validation.gate import falsify
from validation.report_md import render_markdown


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=sorted(FAMILIES))
    ap.add_argument("--spec", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "demo" / "output")
    ap.add_argument("--min-dsr", type=float, default=0.95)
    ap.add_argument("--bait-window-days", type=int, default=540,
                    help="overfit_bait evaluates on this many recent days only")
    ap.add_argument("--regime-context", type=Path,
                    help="optional live CMC regime-context JSON (see regime_context.py)")
    ap.add_argument("--ledger", type=Path, default=ROOT / "data" / "trial_ledger.json",
                    help="trial-ledger path; use a scratch path for experiments so the "
                         "canonical cumulative ledger is not polluted by repeated runs")
    args = ap.parse_args()
    if not args.family and not args.spec:
        ap.error("need --family or --spec")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    panel = load_panel()
    ledger = TrialLedger(args.ledger)

    if args.spec:
        base = StrategySpec.from_json(args.spec)
    else:
        base = FAMILIES[args.family]()

    window = slice(-args.bait_window_days, None) if base.name == "overfit_bait" else None
    print(f"[1/3] evaluating '{base.name}' grid "
          f"({len(base.params_grid)} axes) on {panel.close.shape[1]} tokens…")
    ev = evaluate_family(base, panel.close, funding=panel.funding, fng=panel.fng,
                         ledger=ledger, stamp=stamp, window=window)
    print(f"  grid={ev.returns_matrix.shape[1]} best={ev.best_name} "
          f"ledger-total={ev.ledger_total}")

    print("[2/3] falsifying…")
    rep = falsify(ev, close=panel.close, ledger=ledger, funding=panel.funding,
                  fng=panel.fng, volume_usd=panel.volume_usd, min_dsr=args.min_dsr)

    print("[3/3] writing artifacts…")
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    ev.best_spec.to_json(out / f"{base.name}_best_spec.json")
    (out / f"{base.name}_report.json").write_text(
        json.dumps(rep.to_dict(), indent=2, default=str))
    ev.best_returns.rename("net_return").to_csv(out / f"{base.name}_best_returns.csv")
    regime = None
    if args.regime_context and args.regime_context.exists():
        regime = json.loads(args.regime_context.read_text())
    md = render_markdown(rep, stamp=stamp, regime_context=regime)
    (out / f"{base.name}_report.md").write_text(md)

    print()
    print(f"VERDICT: {rep.verdict} — {rep.reasons[0]}")
    print(f"report: {out / (base.name + '_report.md')}")


if __name__ == "__main__":
    main()
