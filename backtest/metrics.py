"""Performance metrics. Every annualisation takes an explicit ``freq``."""

from __future__ import annotations

import math

import pandas as pd


def sharpe(returns: pd.Series, *, freq: float) -> float:
    r = pd.Series(returns).dropna()
    sd = r.std(ddof=1)
    return float(r.mean() / sd * math.sqrt(freq)) if sd > 1e-12 else 0.0


def cagr(returns: pd.Series, *, freq: float) -> float:
    r = pd.Series(returns).dropna()
    n = len(r)
    if not n:
        return 0.0
    return float((1.0 + r).prod() ** (freq / n) - 1.0)


def max_drawdown(equity: pd.Series) -> float:
    eq = pd.Series(equity).dropna()
    return float((eq / eq.cummax() - 1.0).min()) if len(eq) else 0.0


def ann_turnover(turnover: pd.Series, *, freq: float) -> float:
    t = pd.Series(turnover).dropna()
    return float(t.mean() * freq) if len(t) else 0.0


def summary(returns: pd.Series, equity: pd.Series, turnover: pd.Series,
            *, freq: float) -> dict:
    return {
        "sharpe_ann": sharpe(returns, freq=freq),
        "cagr": cagr(returns, freq=freq),
        "max_drawdown": max_drawdown(equity),
        "ann_turnover": ann_turnover(turnover, freq=freq),
        "n_bars": int(pd.Series(returns).dropna().shape[0]),
    }
