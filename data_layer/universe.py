"""Tradeable universe = eligible tokens ∩ Binance USDT markets.

The competition list is fixed (149 BEP-20 symbols); we can only backtest names
with real price history, so the working universe is the intersection with
Binance USDT spot pairs (and, where available, USDT perps for the funding leg).
Stablecoins and wrapped-gold stay in the file but are FLAGGED — they are cash
legs, not momentum candidates.
"""

from __future__ import annotations

import json
from pathlib import Path

STABLE_OR_PEGGED = {
    "USDT", "USDC", "DAI", "TUSD", "FDUSD", "USDD", "USD1", "USDe", "USDf", "USDF",
    "FRAX", "FRXUSD", "DUSD", "XUSD", "EURI", "lisUSD", "STABLE",
    "XAUt", "XAUM",  # gold-pegged
}


def load_eligible(path: str | Path) -> list[str]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(s)
    return out


def build_universe(
    eligible: list[str], spot_symbols: set[str], perp_symbols: set[str],
) -> list[dict]:
    """Map each eligible token to its Binance USDT spot/perp symbol (if listed).

    Matching is plain ``<SYMBOL>USDT`` uppercase; tokens with non-ASCII or
    unlisted symbols simply get no market and are excluded from backtests.
    """
    rows = []
    for sym in eligible:
        pair = f"{sym.upper()}USDT"
        spot = pair if pair in spot_symbols else None
        # 1000-prefixed perps for micro-priced tokens (e.g. 1000SHIBUSDT)
        perp = pair if pair in perp_symbols else (
            f"1000{sym.upper()}USDT" if f"1000{sym.upper()}USDT" in perp_symbols else None
        )
        rows.append({
            "symbol": sym,
            "binance_spot": spot,
            "binance_perp": perp,
            "is_stable_or_pegged": sym in STABLE_OR_PEGGED,
            "tradeable": spot is not None and sym not in STABLE_OR_PEGGED,
        })
    return rows


def save_universe(rows: list[dict], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, indent=2, ensure_ascii=False))


def load_universe(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
