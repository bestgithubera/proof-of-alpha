"""Annualization-factor tests — the 16x-bug class.

A prior project's harness caught a silent 16x Sharpe inflation from a mixed-up
annualization factor. These tests pin sqrt(freq) for every crypto calendar so
the mistake cannot recur silently: daily=365, 4h=2190, funding=1095.
"""
import math

import numpy as np
import pandas as pd
import pytest

from validation.core import (
    ANN,
    ANN_4H,
    ANN_CRYPTO_DAILY,
    ANN_FUNDING,
    monte_carlo_null,
    validate_strategy,
)


def _series(n: int, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.001, 0.01, n))


def test_calendar_constants():
    assert ANN == 365.0  # module default is crypto daily, NOT equity 252
    assert ANN_CRYPTO_DAILY == 365.0
    assert ANN_4H == 365.0 * 6
    assert ANN_FUNDING == 365.0 * 3


@pytest.mark.parametrize("freq", [ANN_CRYPTO_DAILY, ANN_4H, ANN_FUNDING])
def test_sharpe_annualizes_at_sqrt_freq(freq):
    r = _series(3 * int(freq) if freq <= 400 else 2200)
    rep = validate_strategy(r, n_trials=1, freq=freq)
    per_period = float(r.mean() / r.std(ddof=1))
    assert rep.sharpe_ann == pytest.approx(per_period * math.sqrt(freq), abs=1e-9)


def test_4h_vs_daily_ratio_is_sqrt_6():
    # the SAME per-period series labelled 4h must report sqrt(6)x the daily Sharpe
    r = _series(2000)
    daily = validate_strategy(r, n_trials=1, freq=ANN_CRYPTO_DAILY).sharpe_ann
    four_h = validate_strategy(r, n_trials=1, freq=ANN_4H).sharpe_ann
    assert four_h / daily == pytest.approx(math.sqrt(6.0), rel=1e-9)


def test_monte_carlo_respects_freq():
    r = _series(800)
    daily = monte_carlo_null(r, n_sims=50, seed=1, freq=ANN_CRYPTO_DAILY)["sharpe"]
    funding = monte_carlo_null(r, n_sims=50, seed=1, freq=ANN_FUNDING)["sharpe"]
    assert funding / daily == pytest.approx(math.sqrt(3.0), rel=1e-9)


def test_cagr_uses_freq_not_252():
    # constant +10bps/day for 365 days -> CAGR vs zero baseline must be
    # (1.001)^365 - 1 ~ 44.0%, not the 252-day 28.6%
    r = pd.Series([0.001] * 365)
    base = pd.Series([0.0] * 365)
    rep = validate_strategy(r, n_trials=1, baseline_returns=base, freq=ANN_CRYPTO_DAILY)
    assert rep.excess_cagr_vs_baseline == pytest.approx(1.001 ** 365 - 1, rel=1e-6)
