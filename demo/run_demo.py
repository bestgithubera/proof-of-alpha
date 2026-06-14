"""End-to-end demo: falsify all four families on real cached data, then build
the combined equity chart and a verdict summary.

Usage: .venv/bin/python demo/run_demo.py [--skip-run]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "demo" / "output"
# Dedicated, rebuilt-each-run ledger so the demo's cumulative N is reproducible
# and the canonical data/trial_ledger.json (Rule 3: never reset) stays sacred.
DEMO_LEDGER = OUT / "demo_ledger.json"
REGIME = OUT / "regime_context.json"
# Curated demo set: headline strategy + the 3 organizer example builds +
# a risk-managed variant + the villain. family CLI key -> spec name.
FAMILIES = {"xs_momentum": "xs_momentum",                       # headline (DEFENSIBLE)
            "xs_mom_voltarget": "xs_mom_voltarget",             # risk-managed variant
            "momentum_rsi_macd_fng": "momentum_rsi_macd_fng",   # example build 1 (rules)
            "sentiment_divergence": "sentiment_divergence",     # example build 2
            "funding_regime_switch": "funding_regime_switch",   # example build 3
            "overfit_bait": "overfit_bait"}                     # the villain (FAIL)


def run_families() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DEMO_LEDGER.unlink(missing_ok=True)        # one clean, complete search per demo
    # best-effort live CMC regime context (skip silently if no key / offline)
    subprocess.run(
        [sys.executable, str(ROOT / "skill" / "scripts" / "regime_context.py"),
         "--out", str(REGIME)], check=False)
    regime_args = ["--regime-context", str(REGIME)] if REGIME.exists() else []
    for fam in FAMILIES:  # CLI keys
        print(f"=== {fam} ===", flush=True)
        subprocess.run(
            [sys.executable, str(ROOT / "skill" / "scripts" / "falsify_strategy.py"),
             "--family", fam, "--out", str(OUT),
             "--ledger", str(DEMO_LEDGER), *regime_args],
            check=True,
        )


def build_chart_and_summary() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    fig, ax = plt.subplots(figsize=(11, 6))
    lines = ["# Proof of Alpha — demo verdicts", ""]
    for fam in FAMILIES.values():
        rep = json.loads((OUT / f"{fam}_report.json").read_text())
        rets = pd.read_csv(OUT / f"{fam}_best_returns.csv", index_col=0,
                           parse_dates=True)["net_return"]
        eq = (1.0 + rets.fillna(0.0)).cumprod()
        verdict = rep["verdict"]
        h = rep["headline"]
        label = (f"{fam} [{verdict}] Sharpe {h['sharpe_ann']:.2f}, "
                 f"CAGR {h['cagr']*100:+.0f}%")
        passlike = verdict in ("STRONG", "DEFENSIBLE")
        ax.plot(eq.index, eq.values, label=label,
                linewidth=2.2 if passlike else 1.2,
                linestyle="-" if passlike else "--")
        lines.append(f"- **{fam}** → **{verdict}** — {rep['reasons'][0]} "
                     f"(alt-school: {rep['alt_verdict']})")

    job = ROOT / "bnbagent_demo" / "last_job.json"
    if job.exists():
        j = json.loads(job.read_text())
        lines += ["", "## On-chain proof (BNB AI Agent SDK)",
                  f"- ERC-8004 identity: agentId 1379 (BSC testnet)",
                  f"- evidence keccak256: `{j.get('raw_evidence_keccak256', 'n/a')}`"]
        if j.get("status") == "COMPLETED":
            tx = j.get("tx", {})
            lines.append(f"- ERC-8183 job {j.get('job_id')} settled COMPLETED; "
                         f"submit tx `{tx.get('submit')}`")
        else:
            lines.append(f"- ERC-8183 escrow loop: {j.get('status')} "
                         "(awaits testnet faucet funding)")
    ax.set_yscale("log")
    ax.set_ylabel("equity (log)")
    ax.set_title("Proof of Alpha: every strategy ships with a falsification verdict")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curves.png", dpi=140)
    (OUT / "SUMMARY.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT/'equity_curves.png'} and {OUT/'SUMMARY.md'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-run", action="store_true",
                    help="only rebuild chart/summary from existing artifacts")
    args = ap.parse_args()
    if not args.skip_run:
        run_families()
    build_chart_and_summary()
