"""Backtest-engine tests — synthetic cases with hand-computable answers.

Pin the four properties that silently corrupt backtests when wrong:
(a) compounding exactness, (b) costs charged on turnover, (c) NEXT-bar execution
(no look-ahead), (d) funding accrual sign and timing.
"""
import numpy as np
import pandas as pd
import pytest

from backtest.engine import backtest
from backtest.metrics import max_drawdown, sharpe

IDX = pd.date_range("2024-01-01", periods=100, freq="D", tz="UTC")


def _prices_const_growth(rate: float = 0.01) -> pd.DataFrame:
    p = 100.0 * np.cumprod(np.full(len(IDX), 1.0 + rate))
    return pd.DataFrame({"AAA": p}, index=IDX)


def test_always_long_zero_cost_compounds_exactly():
    prices = _prices_const_growth(0.01)
    w = pd.DataFrame({"AAA": np.ones(len(IDX))}, index=IDX)
    res = backtest(prices, w, fee_bps=0.0, slippage_bps=0.0)
    # weights shift by 1 bar -> invested from bar 1 onward: (n-1) full +1% returns
    expected = 1.01 ** (len(IDX) - 1)
    assert res.equity.iloc[-1] == pytest.approx(expected, rel=1e-9)


def test_round_trip_costs_exactly_two_legs():
    prices = pd.DataFrame({"AAA": np.full(len(IDX), 100.0)}, index=IDX)  # flat market
    w = pd.DataFrame({"AAA": np.zeros(len(IDX))}, index=IDX)
    w.iloc[10] = 1.0           # enter at bar 11 (next-bar), exit at bar 12
    res = backtest(prices, w, fee_bps=10.0, slippage_bps=0.0)
    # one buy (turnover 1) + one sell (turnover 1) at 10 bps each
    assert res.equity.iloc[-1] == pytest.approx((1 - 0.001) ** 2, rel=1e-9)


def test_next_bar_execution_no_lookahead():
    # price jumps +50% at bar 5; a signal fired AT bar 5 must NOT catch that jump
    p = np.full(len(IDX), 100.0)
    p[5:] = 150.0
    prices = pd.DataFrame({"AAA": p}, index=IDX)
    w = pd.DataFrame({"AAA": np.zeros(len(IDX))}, index=IDX)
    w.iloc[5] = 1.0            # decided on the jump bar -> position from bar 6
    res = backtest(prices, w, fee_bps=0.0, slippage_bps=0.0)
    assert res.equity.iloc[-1] == pytest.approx(1.0, rel=1e-9)  # jump NOT captured

    w_early = pd.DataFrame({"AAA": np.zeros(len(IDX))}, index=IDX)
    w_early.iloc[3:7] = 1.0    # decided before the jump and HELD -> bar 5 move captured
    res2 = backtest(prices, w_early, fee_bps=0.0, slippage_bps=0.0)
    assert res2.equity.iloc[-1] > 1.4


def test_short_with_positive_funding_earns_funding():
    prices = pd.DataFrame({"AAA": np.full(len(IDX), 100.0)}, index=IDX)
    w = pd.DataFrame({"AAA": np.full(len(IDX), -1.0)}, index=IDX)   # short perp
    funding = pd.DataFrame({"AAA": np.full(len(IDX), 0.0003)}, index=IDX)  # daily-agg funding
    res = backtest(prices, w, fee_bps=0.0, funding_daily=funding, slippage_bps=0.0)
    # short pays nothing on flat price, RECEIVES funding: ~(1+0.0003)^(n-1)
    assert res.equity.iloc[-1] == pytest.approx(1.0003 ** (len(IDX) - 1), rel=1e-6)

    w_long = pd.DataFrame({"AAA": np.full(len(IDX), 1.0)}, index=IDX)
    res_long = backtest(prices, w_long, fee_bps=0.0, funding_daily=funding, slippage_bps=0.0)
    assert res_long.equity.iloc[-1] < 1.0   # long PAYS positive funding


def test_turnover_and_exposure_reported():
    prices = _prices_const_growth(0.0)
    w = pd.DataFrame({"AAA": np.zeros(len(IDX))}, index=IDX)
    w.iloc[10] = 1.0
    res = backtest(prices, w, fee_bps=0.0, slippage_bps=0.0)
    assert res.turnover.sum() == pytest.approx(2.0)     # in and out
    assert res.exposure.max() == pytest.approx(1.0)


def test_metrics_sharpe_and_mdd():
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.001, 0.01, 1000))
    assert sharpe(r, freq=365.0) == pytest.approx(
        float(r.mean() / r.std(ddof=1)) * np.sqrt(365.0), rel=1e-12)

    eq = pd.Series([1.0, 1.2, 0.9, 1.1, 0.6, 1.5])
    assert max_drawdown(eq) == pytest.approx(0.6 / 1.2 - 1.0)  # -50%
