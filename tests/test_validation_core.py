"""Tests for the anti-overfitting toolkit (validation.core).

Each test pins a KNOWN behaviour so the guardrails can't silently rot:
- effective_n_trials: == N for independent, ~1 for identical
- min_backtest_length: grows with trials, inf for non-positive Sharpe
- monte_carlo_null: brackets the point Sharpe, p_le_zero small for a real edge
- pbo_cscv: ~0.5 for pure noise, ~0 when one strategy genuinely dominates
- haircut_sharpe: never increases the Sharpe, harsher with more trials
- anomaly_decay: negative slope for a fading series
- parameter_sensitivity: robust for a plateau, fragile for a spike
- causality_audit: clean for identical, flags a shifted (leaked) series
- TrialLedger: accumulates and persists across instances
"""
import numpy as np
import pandas as pd

from validation.core import (
    TrialLedger,
    anomaly_decay,
    capacity_curve,
    causality_audit,
    cpcv_paths,
    effective_n_trials,
    haircut_sharpe,
    min_backtest_length,
    monte_carlo_null,
    parameter_sensitivity,
    parameter_stability,
    pbo_cscv,
)


def test_effective_n_trials_independent_vs_identical():
    rng = np.random.default_rng(0)
    indep = pd.DataFrame(rng.standard_normal((500, 20)))
    assert effective_n_trials(indep) > 15  # ~20 independent

    base = rng.standard_normal(500)
    identical = pd.DataFrame({i: base + 1e-9 * rng.standard_normal(500) for i in range(20)})
    assert effective_n_trials(identical) < 2  # all the same -> ~1


def test_min_backtest_length_monotonic_and_inf():
    assert min_backtest_length(1000, 1.0) > min_backtest_length(10, 1.0)
    assert min_backtest_length(100, 0.0) == float("inf")
    assert min_backtest_length(1, 1.0) == float("inf")


def test_monte_carlo_null_brackets_and_pvalue():
    rng = np.random.default_rng(1)
    # a clearly profitable series: positive drift, modest vol
    r = pd.Series(0.001 + 0.005 * rng.standard_normal(750))
    out = monte_carlo_null(r, n_sims=400, block=5, seed=2)
    lo, hi = out["ci"]
    assert lo <= out["sharpe"] <= hi
    assert out["p_le_zero"] < 0.20  # rarely looks unprofitable under resampling
    assert out["se"] > 0
    # ANNUALIZED Sharpe must be daily-Sharpe * sqrt(365), NOT * 365. Daily mean ~0.001,
    # std ~0.005 -> daily Sharpe ~0.2 -> annual ~3.8. A bare *365 would give ~70.
    assert 1.5 < out["sharpe"] < 7.0


def test_pbo_noise_is_half_edge_is_low():
    rng = np.random.default_rng(3)
    noise = pd.DataFrame(rng.standard_normal((480, 40)))
    pbo_noise = pbo_cscv(noise, n_blocks=10, seed=0)["pbo"]
    assert 0.30 < pbo_noise < 0.70  # IS-best is OOS-random ~ coin flip

    # one genuinely dominant strategy (real, persistent edge)
    M = rng.standard_normal((480, 40))
    M[:, 0] += 0.30  # column 0 always strongly best, IS and OOS
    edge = pd.DataFrame(M)
    pbo_edge = pbo_cscv(edge, n_blocks=10, seed=0)["pbo"]
    assert pbo_edge < 0.20


def test_haircut_never_increases_and_harsher_with_trials():
    h1 = haircut_sharpe(1.5, n_obs=1095, n_trials=10)
    h2 = haircut_sharpe(1.5, n_obs=1095, n_trials=1000)
    assert h1["haircut_sharpe"] <= 1.5 + 1e-9
    assert h2["haircut_sharpe"] <= h1["haircut_sharpe"]  # more trials -> bigger haircut
    assert h2["p_bonferroni"] >= h1["p_bonferroni"]


def test_anomaly_decay_detects_fade():
    # Sharpe declines across the record: strong drift early, none late
    n = 600
    early = 0.002 * np.ones(n // 2)
    late = np.zeros(n - n // 2)
    rng = np.random.default_rng(4)
    r = pd.Series(np.concatenate([early, late]) + 0.004 * rng.standard_normal(n))
    out = anomaly_decay(r, n_subperiods=6)
    assert out["slope"] < 0
    assert out["first_half"] > out["second_half"]
    # sub-period Sharpes are ANNUALIZED (sqrt(365)): early drift 0.002 / vol 0.004 ->
    # daily Sharpe ~0.5 -> annual ~9.6, not ~180. Guards the *365-vs-*sqrt(365) bug.
    assert out["first_half"] < 25.0


def test_parameter_sensitivity_plateau_vs_spike():
    # plateau: metric ~flat across the parameter
    plateau = pd.DataFrame({"p": list(range(10)), "metric": [1.0] * 10})
    rp = parameter_sensitivity(plateau, ["p"], "metric", tol=0.25)
    assert rp["robust"] is True

    # spike: one value huge, rest tiny
    spike_vals = [0.1] * 10
    spike_vals[5] = 2.0
    spike = pd.DataFrame({"p": list(range(10)), "metric": spike_vals})
    rs = parameter_sensitivity(spike, ["p"], "metric", tol=0.25)
    assert rs["robust"] is False


def test_causality_audit_clean_and_leak():
    idx = pd.date_range("2023-01-01", periods=200, freq="D")
    s = pd.Series(np.linspace(1, 2, 200), index=idx)
    clean = causality_audit(s, s.copy())
    assert clean["n_mismatch"] == 0
    assert clean["leak_suspected"] is False

    leaked = s.shift(-1).bfill()  # uses tomorrow's value = look-ahead
    flagged = causality_audit(s, leaked)
    assert flagged["leak_suspected"] is True


def test_trial_ledger_accumulates_and_persists(tmp_path):
    p = tmp_path / "ledger.json"
    led = TrialLedger(p)
    led.record("momentum-grid", 992, hypothesis="xs momentum", stamp="2026-06-12")
    led.record("funding-grid", 180, stamp="2026-06-12")
    assert led.total == 1172
    # reload from disk -> persisted
    led2 = TrialLedger(p)
    assert led2.total == 1172
    assert len(led2.data["entries"]) == 2


def test_cpcv_noise_regresses_edge_persists():
    rng = np.random.default_rng(7)
    # pure noise: the IS-best is a lucky draw -> big IS->OOS haircut, OOS ~ 0
    noise = pd.DataFrame(rng.standard_normal((480, 40)))
    n = cpcv_paths(noise, n_blocks=10, seed=0)
    assert n["selection_haircut"] > 0                  # you pay for selecting on noise
    assert n["is_sharpe_mean"] > n["oos_sharpe_mean"]  # IS-best regresses out-of-sample

    # one genuinely dominant strategy: IS-best is the same col both halves
    M = rng.standard_normal((480, 40))
    M[:, 0] += 0.30  # strong enough to clear the best-of-39-noise IS bar reliably
    edge = cpcv_paths(pd.DataFrame(M), n_blocks=10, seed=0)
    assert edge["oos_sharpe_mean"] > 0.5               # the real edge shows up OOS
    assert edge["frac_oos_positive"] > 0.8
    assert edge["selection_haircut"] < n["selection_haircut"]  # far less regression


def test_parameter_stability_consistent_vs_frontloaded():
    rng = np.random.default_rng(8)
    # consistent edge across the whole record
    steady = pd.Series(0.0008 + 0.004 * rng.standard_normal(1200))
    s = parameter_stability(steady, n_subperiods=6, min_sharpe=0.0)
    assert s["stable"] is True
    assert s["frac_above_min"] >= 0.75

    # edge only in the first half, fades to negative -> not stable
    first = 0.0015 * np.ones(600)
    second = -0.0004 * np.ones(600)
    fl = pd.Series(np.concatenate([first, second]) + 0.004 * rng.standard_normal(1200))
    f = parameter_stability(fl, n_subperiods=6, min_sharpe=0.0)
    assert f["stable"] is False
    assert f["worst"] < f["best"]


def test_capacity_curve_decays_and_scales_with_adv():
    grid = [1e5, 1e6, 1e7, 1e8, 1e9]
    small = capacity_curve(0.25, ann_turnover=4.0, n_positions=20,
                           median_adv_usd=2e5, aum_grid_usd=grid)
    net = small["net_ann_return"]
    # net is monotone non-increasing in AUM (impact only grows with size)
    assert all(b <= a + 1e-12 for a, b in zip(net, net[1:], strict=False))
    assert net[0] > net[-1]                                   # impact bites at size

    big = capacity_curve(0.25, ann_turnover=4.0, n_positions=20,
                         median_adv_usd=2e8, aum_grid_usd=grid)
    assert big["capacity_usd"] >= small["capacity_usd"]       # deeper book -> more capacity

    huge = capacity_curve(0.25, ann_turnover=4.0, n_positions=20,
                          median_adv_usd=1e12, aum_grid_usd=grid)
    assert huge["capacity_usd"] == max(grid)                  # impact negligible -> all investable


def test_effective_n_trials_survives_zero_variance_columns():
    rng = np.random.default_rng(9)
    R = pd.DataFrame(rng.standard_normal((300, 5)))
    R[5] = 0.0                    # a gated strategy that never traded
    n_eff = effective_n_trials(R)
    assert np.isfinite(n_eff) and 1.0 <= n_eff <= 5.5
