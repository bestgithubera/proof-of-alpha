"""Spec format tests: round-trip, validation, grid expansion, compiler."""
import numpy as np
import pandas as pd
import pytest

from backtest.engine import backtest
from strategies.spec import StrategySpec, compile_strategy, expand_grid

IDX = pd.date_range("2024-01-01", periods=300, freq="D", tz="UTC")
HYP = "Cross-sectional momentum persists because attention flows are autocorrelated."


def _spec(**over) -> StrategySpec:
    base = dict(
        name="test_mom",
        hypothesis=HYP,
        signals=[{"id": "mom", "fn": "ts_momentum", "args": {"window": 60}}],
        portfolio={"type": "xs_topk", "score": "mom", "k": 2,
                   "direction": "long", "rebalance": "W-MON"},
        universe={"filter": "tradeable", "min_history_days": 10},
        params_grid={"signals.mom.args.window": [30, 60],
                     "portfolio.k": [2, 3]},
    )
    base.update(over)
    return StrategySpec(**base)


def _panel(seed: int = 0, n_assets: int = 6) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cols = [f"A{i}" for i in range(n_assets)]
    rets = rng.normal(0.0, 0.02, (len(IDX), n_assets))
    rets[:, 0] += 0.012  # asset A0 trends hard (~4.6 sigma over 60d) -> tops momentum ranks
    return pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=IDX, columns=cols)


def test_entry_exit_holds_between_entry_and_exit():
    close = _panel()                                   # A0 trends hard up
    spec = StrategySpec(
        name="ee", hypothesis=HYP,
        signals=[{"id": "mom", "fn": "ts_momentum", "args": {"window": 20}}],
        portfolio={"type": "entry_exit",
                   "entry": {"all": [{"signal": "mom", "op": ">", "value": 0.05}]},
                   "exit": {"any": [{"signal": "mom", "op": "<", "value": 0.0}]},
                   "sizing": "equal", "max_positions": 3, "rebalance": "1d"},
        universe={"filter": "tradeable", "min_history_days": 10})
    cs = compile_strategy(spec, close)
    assert (cs.weights["A0"].iloc[100:] > 0).mean() > 0.7   # strong uptrend held
    sums = cs.weights.sum(axis=1)
    assert (sums <= 1.0 + 1e-9).all()                       # long-only, never > 100%
    assert (sums.iloc[100:] > 0).any()                      # invested in the back half


def test_entry_exit_validate_rejects_unknown_signal():
    spec = StrategySpec(
        name="ee_bad", hypothesis=HYP,
        signals=[{"id": "mom", "fn": "ts_momentum", "args": {}}],
        portfolio={"type": "entry_exit",
                   "entry": {"all": [{"signal": "ghost", "op": ">", "value": 0}]},
                   "exit": {"any": [{"signal": "mom", "op": "<", "value": 0}]}})
    with pytest.raises(ValueError, match="ghost"):
        spec.validate()


def test_apply_vol_target_delevers_in_turbulence():
    from strategies.spec import _apply_vol_target
    idx = pd.date_range("2023-01-01", periods=300, freq="D", tz="UTC")
    rng = np.random.default_rng(0)
    calm = rng.normal(0.0, 0.005, 150)
    rough = rng.normal(0.0, 0.04, 150)               # 8x the vol in the back half
    close = pd.DataFrame(
        {"A": 100 * np.exp(np.cumsum(np.concatenate([calm, rough])))}, index=idx)
    w = pd.DataFrame(1.0, index=idx, columns=["A"])  # always fully invested
    wt = _apply_vol_target(w, close, target_ann_vol=0.40, lookback=20, max_leverage=5.0)
    assert wt["A"].iloc[60:140].mean() > wt["A"].iloc[220:300].mean()  # delevers when rough


def test_round_trip_json(tmp_path):
    s = _spec()
    p = tmp_path / "spec.json"
    s.to_json(p)
    s2 = StrategySpec.from_json(p)
    assert s2.__dict__ == s.__dict__


def test_validation_rejects_stub_hypothesis_and_unknown_fn():
    with pytest.raises(ValueError, match="hypothesis"):
        _spec(hypothesis="trust me").validate()
    bad = _spec(signals=[{"id": "x", "fn": "astrology", "args": {}}],
                portfolio={"type": "xs_topk", "score": "x", "k": 2})
    with pytest.raises(ValueError, match="astrology"):
        bad.validate()


def test_expand_grid_cross_product():
    variants = expand_grid(_spec())
    assert len(variants) == 4  # 2 windows x 2 k
    windows = {v.signals[0]["args"]["window"] for v in variants}
    ks = {v.portfolio["k"] for v in variants}
    assert windows == {30, 60} and ks == {2, 3}
    assert all(not v.params_grid for v in variants)  # concrete variants, no grid


def test_expand_grid_supports_list_index_paths():
    spec = StrategySpec(
        name="ee", hypothesis=HYP,
        signals=[{"id": "rsi", "fn": "rsi", "args": {"window": 14}}],
        portfolio={"type": "entry_exit",
                   "entry": {"all": [{"signal": "rsi", "op": "<", "value": 30}]},
                   "exit": {"any": [{"signal": "rsi", "op": ">", "value": 70}]}},
        params_grid={"portfolio.exit.any.0.value": [70, 75, 80]})
    variants = expand_grid(spec)
    assert len(variants) == 3
    assert {v.portfolio["exit"]["any"][0]["value"] for v in variants} == {70, 75, 80}


def test_compile_xs_topk_picks_the_trending_asset():
    close = _panel()
    cs = compile_strategy(_spec(), close)
    held_weight_a0 = cs.weights["A0"].iloc[100:]
    assert (held_weight_a0 > 0).mean() > 0.9       # trending asset ~always selected
    # weights are a valid long book: rows sum to ~1 (or 0 pre-history)
    sums = cs.weights.iloc[100:].sum(axis=1)
    assert ((sums - 1.0).abs() < 1e-9).all()


def test_regime_gate_zeroes_book():
    close = _panel()
    fng = pd.Series(10.0, index=IDX)               # extreme fear the whole time
    spec = _spec(signals=[
        {"id": "mom", "fn": "ts_momentum", "args": {"window": 60}},
        {"id": "fng", "fn": "fear_greed", "args": {}},
    ])
    spec.portfolio["regime_gate"] = {"signal": "fng", "min": 20, "max": 100}
    cs = compile_strategy(spec, close, fng=fng)
    assert cs.weights.abs().sum().sum() == 0.0      # gate keeps the book flat


def test_funding_carry_is_price_neutral_and_earns_funding():
    close = _panel(seed=3)
    funding = pd.DataFrame(0.0003, index=IDX, columns=close.columns)  # +3bps/day everywhere
    spec = StrategySpec(
        name="carry",
        hypothesis="Positive perp funding pays the short leg of a hedged carry book persistently.",
        signals=[{"id": "f", "fn": "funding_rate", "args": {"window": 7}}],
        portfolio={"type": "funding_carry", "score": "f", "k": 2,
                   "rebalance": "W-MON", "min_funding_daily": 0.0},
        universe={"filter": "tradeable", "min_history_days": 10},
    )
    cs = compile_strategy(spec, close, funding=funding)
    assert cs.weights.abs().sum().sum() == 0.0      # zero net price exposure
    assert (cs.funding_weights.min().min() < 0)     # short perp leg exists
    assert cs.fee_bps == pytest.approx(20.0)        # both legs charged

    res = backtest(close, cs.weights, fee_bps=0.0, slippage_bps=0.0,
                   funding_daily=funding, funding_weights=cs.funding_weights)
    assert res.equity.iloc[-1] > 1.01               # funding income, no price PnL


def test_fng_divergence_plays_momentum_in_fear():
    from strategies.spec import sig_fng_divergence

    idx = pd.date_range("2023-01-01", periods=120, freq="D", tz="UTC")
    a = pd.Series(np.linspace(100, 200, 120), index=idx)   # high momentum
    b = pd.Series(np.full(120, 100.0), index=idx)          # flat
    close = pd.DataFrame({"A": a, "B": b})
    fng = pd.Series(10.0, index=idx)                       # extreme FEAR

    div = sig_fng_divergence(close, fng=fng, price_window=30, fng_pivot=50.0)
    assert div.shape == close.shape
    assert div["A"].iloc[-1] > div["B"].iloc[-1]           # in fear: momentum -> A on top


def test_fng_divergence_flips_to_contrarian_in_greed():
    """Regression guard: F&G MUST change the cross-sectional ranking. In greed
    the high-momentum name ranks BELOW the loser — the signal is not a no-op
    market-wide scalar that collapses to plain momentum."""
    from strategies.spec import sig_fng_divergence

    idx = pd.date_range("2023-01-01", periods=120, freq="D", tz="UTC")
    a = pd.Series(np.linspace(100, 200, 120), index=idx)   # high momentum
    b = pd.Series(np.full(120, 100.0), index=idx)          # flat
    close = pd.DataFrame({"A": a, "B": b})
    fear = pd.Series(10.0, index=idx)
    greed = pd.Series(90.0, index=idx)

    div_fear = sig_fng_divergence(close, fng=fear, price_window=30, fng_pivot=50.0)
    div_greed = sig_fng_divergence(close, fng=greed, price_window=30, fng_pivot=50.0)
    # the ranking flips between regimes -> F&G genuinely drives selection
    assert div_fear["A"].iloc[-1] > div_fear["B"].iloc[-1]
    assert div_greed["A"].iloc[-1] < div_greed["B"].iloc[-1]


def test_fng_divergence_without_fng_is_all_nan():
    from strategies.spec import sig_fng_divergence
    idx = pd.date_range("2023-01-01", periods=40, freq="D", tz="UTC")
    close = pd.DataFrame({"A": np.arange(40.0)}, index=idx)
    out = sig_fng_divergence(close, fng=None)
    assert out.isna().all().all()


def test_macd_histogram_tracks_trend_turn():
    from strategies.spec import sig_macd
    idx = pd.date_range("2023-01-01", periods=120, freq="D", tz="UTC")
    px = np.concatenate([np.linspace(100, 200, 60), np.linspace(200, 100, 60)])
    close = pd.DataFrame({"X": px}, index=idx)
    h = sig_macd(close, fast=12, slow=26, signal=9)
    assert h.shape == close.shape
    assert h["X"].iloc[10:55].max() > 0     # positive while trending up
    assert h["X"].iloc[65:115].min() < 0    # negative after the turn down


def test_funding_market_is_mean_across_names():
    from strategies.spec import sig_funding_market
    idx = pd.date_range("2023-01-01", periods=20, freq="D", tz="UTC")
    close = pd.DataFrame({"A": np.arange(20.0), "B": np.arange(20.0)}, index=idx)
    funding = pd.DataFrame({"A": 0.001, "B": 0.003}, index=idx)
    fm = sig_funding_market(close, funding=funding, window=3)
    assert isinstance(fm, pd.Series)
    assert fm.iloc[-1] == pytest.approx(0.002)            # mean of the two legs
    assert sig_funding_market(close, funding=None).isna().all()
