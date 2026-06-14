"""Vectorized cost-aware portfolio backtester.

Contract:
- ``prices``: wide close-price frame (rows=bars, cols=assets), regular grid.
- ``weights``: target portfolio weights DECIDED at each bar close. Execution is
  NEXT bar: returns earned from bar t use weights decided at t-1 (one-bar shift,
  the no-look-ahead invariant pinned by tests).
- costs: ``(fee_bps + slippage_bps)/1e4`` charged on each bar's one-sided
  turnover ``sum(|w_t - w_{t-1,drifted}|)``. We use the simpler ``|Δtarget|``
  (no drift adjustment) — slightly conservative on costs for rebalanced books.
- ``funding_daily``: optional per-bar funding RATE frame (same grid). Longs PAY
  positive funding, shorts RECEIVE it: pnl -= w * funding.

Returns per-bar net returns, equity curve, turnover and gross exposure.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    returns: pd.Series          # net per-bar portfolio returns
    equity: pd.Series           # cumulative product of (1 + returns)
    turnover: pd.Series         # one-sided turnover per bar (at decision bar)
    exposure: pd.Series         # gross exposure sum(|w|) held during each bar
    costs: pd.Series            # cost drag per bar


def backtest(
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    *,
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    funding_daily: pd.DataFrame | None = None,
    funding_weights: pd.DataFrame | None = None,
) -> BacktestResult:
    """``funding_weights``: optional separate frame for the funding leg (carry
    books hold zero net price exposure but a short-perp funding leg). Defaults
    to ``weights``. Its turnover is charged too when provided separately."""
    prices = prices.sort_index()
    w = weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0)

    asset_ret = prices.pct_change(fill_method=None).fillna(0.0)
    held = w.shift(1).fillna(0.0)                 # next-bar execution
    gross = (held * asset_ret).sum(axis=1)

    fw = w if funding_weights is None else (
        funding_weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0))
    if funding_daily is not None:
        f = funding_daily.reindex(index=prices.index, columns=prices.columns).fillna(0.0)
        held_f = fw.shift(1).fillna(0.0)
        # funding accrues on the position HELD over the bar; longs pay, shorts receive
        gross = gross - (held_f * f).sum(axis=1)

    turn = (w - w.shift(1).fillna(0.0)).abs().sum(axis=1)
    if funding_weights is not None:
        turn = turn + (fw - fw.shift(1).fillna(0.0)).abs().sum(axis=1)
    cost_rate = (fee_bps + slippage_bps) / 1e4
    # costs hit when the trade EXECUTES (start of next bar)
    costs = (turn * cost_rate).shift(1).fillna(0.0)

    net = gross - costs
    equity = (1.0 + net).cumprod()
    return BacktestResult(
        returns=net, equity=equity, turnover=turn,
        exposure=held.abs().sum(axis=1), costs=costs,
    )
