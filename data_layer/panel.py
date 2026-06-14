"""Assemble backtest panels from the parquet cache.

Outputs (all UTC, daily grid):
- ``close``: wide close-price frame, one column per tradeable token symbol
- ``volume_usd``: matching quote-volume frame (for ADV/capacity)
- ``funding``: DAILY-AGGREGATED funding rate (sum of the 3 8h stamps), columns
  matching ``close`` where a perp exists
- ``fng``: market-wide Fear & Greed series
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from data_layer.store import load
from data_layer.universe import load_universe

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Panel:
    close: pd.DataFrame
    volume_usd: pd.DataFrame
    funding: pd.DataFrame
    fng: pd.Series


def load_panel(root: Path | None = None, bar: str = "1d") -> Panel:
    root = root or ROOT
    uni = load_universe(root / "data" / "universe.json")
    tradeable = [r for r in uni if r["tradeable"]]

    closes, vols, fundings = {}, {}, {}
    for r in tradeable:
        sym = r["symbol"]
        k = load(f"binance_{bar}", r["binance_spot"], root / "data" / "cache")
        if k is None or len(k) < 30:
            continue
        idx = k.index.normalize() if bar == "1d" else k.index
        closes[sym] = pd.Series(k["close"].to_numpy(), index=idx)
        vols[sym] = pd.Series(k["quote_volume"].to_numpy(), index=idx)
        if r["binance_perp"]:
            f = load("binance_funding", r["binance_perp"], root / "data" / "cache")
            if f is not None and len(f):
                daily = f["funding_rate"].groupby(f.index.normalize()).sum()
                fundings[sym] = daily

    close = pd.DataFrame(closes).sort_index()
    volume = pd.DataFrame(vols).reindex(close.index)
    funding = pd.DataFrame(fundings).reindex(close.index) if fundings else \
        pd.DataFrame(index=close.index)
    funding = funding.reindex(columns=close.columns)

    fng_df = load("sentiment", "fear_greed", root / "data" / "cache")
    fng = (fng_df["fng"].astype(float).reindex(close.index).ffill()
           if fng_df is not None else pd.Series(index=close.index, dtype=float))
    return Panel(close=close, volume_usd=volume, funding=funding, fng=fng)
