"""Pull the full backtest dataset into data/cache/.

Usage: .venv/bin/python scripts/fetch_history.py [--years 3] [--bar4h-years 1]

- builds data/universe.json (eligible ∩ Binance USDT markets)
- 1d klines for every tradeable spot pair (default 3y)
- 4h klines for the same names (default 1y)
- full funding history for names with a USDT perp
- Fear & Greed: alternative.me backbone + CMC overlay (if key)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from data_layer.binance_client import BinanceClient
from data_layer.cmc_client import CmcClient, fear_greed_history
from data_layer.store import load_or_fetch, save
from data_layer.universe import build_universe, load_eligible, save_universe

ROOT = Path(__file__).resolve().parent.parent
MS_YEAR = 365 * 24 * 3600 * 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=float, default=3.0)
    ap.add_argument("--bar4h-years", type=float, default=1.0)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    bn = BinanceClient()

    print("[1/4] universe…", flush=True)
    eligible = load_eligible(ROOT / "data" / "universe_eligible.txt")
    spot = bn.get_exchange_symbols(futures=False)
    perp = bn.get_exchange_symbols(futures=True)
    rows = build_universe(eligible, spot, perp)
    save_universe(rows, ROOT / "data" / "universe.json")
    tradeable = [r for r in rows if r["tradeable"]]
    with_perp = [r for r in tradeable if r["binance_perp"]]
    print(f"  eligible={len(eligible)} tradeable-spot={len(tradeable)} with-perp={len(with_perp)}")

    now_ms = int(time.time() * 1000)
    t0_1d = now_ms - int(args.years * MS_YEAR)
    t0_4h = now_ms - int(args.bar4h_years * MS_YEAR)

    print("[2/4] klines…", flush=True)
    for i, r in enumerate(tradeable):
        sym = r["binance_spot"]
        d1 = load_or_fetch("binance_1d", sym,
                           lambda s=sym: bn.get_klines(s, "1d", t0_1d), refresh=args.refresh)
        d4 = load_or_fetch("binance_4h", sym,
                           lambda s=sym: bn.get_klines(s, "4h", t0_4h), refresh=args.refresh)
        print(f"  [{i+1}/{len(tradeable)}] {sym}: 1d={len(d1)} 4h={len(d4)}", flush=True)

    print("[3/4] funding…", flush=True)
    for i, r in enumerate(with_perp):
        sym = r["binance_perp"]
        f = load_or_fetch("binance_funding", sym,
                          lambda s=sym: bn.get_funding_history(s, start_ms=t0_1d),
                          refresh=args.refresh)
        print(f"  [{i+1}/{len(with_perp)}] {sym}: funding={len(f)}", flush=True)

    print("[4/4] fear & greed…", flush=True)
    fng = fear_greed_history(CmcClient())
    save(fng, "sentiment", "fear_greed")
    print(f"  fng rows={len(fng)} ({fng.index.min().date()} -> {fng.index.max().date()})")
    print("done.")


if __name__ == "__main__":
    main()
