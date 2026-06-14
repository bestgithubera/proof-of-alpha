"""Family evaluator tests on synthetic data — grid size, ledger, matrix shape."""
import numpy as np
import pandas as pd

from strategies.families import (
    FAMILIES,
    evaluate_family,
    family_overfit_bait,
    family_sentiment_divergence,
    family_xs_momentum,
)
from strategies.spec import expand_grid
from validation.core import TrialLedger

IDX = pd.date_range("2023-01-01", periods=500, freq="D", tz="UTC")


def _close(seed=0, n=8):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.02, (len(IDX), n))
    return pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=IDX,
                        columns=[f"A{i}" for i in range(n)])


def test_all_families_are_valid_specs():
    for name, fac in FAMILIES.items():
        spec = fac() if name != "overfit_bait" else fac(8)
        spec.validate()
        assert spec.params_grid, f"{name} must declare its searched grid"


def test_evaluate_family_ledgers_full_grid(tmp_path):
    led = TrialLedger(tmp_path / "ledger.json")
    base = family_xs_momentum()
    ev = evaluate_family(base, _close(), ledger=led, stamp="2026-06-12")
    n_grid = 5 * 4  # windows x ks
    assert len(ev.results) == n_grid
    assert ev.returns_matrix.shape[1] == n_grid
    assert led.total == n_grid                       # every cell counted
    assert ev.best_name in ev.returns_matrix.columns
    assert ev.best_spec.name == ev.best_name


def test_bait_family_finds_lucky_random(tmp_path):
    led = TrialLedger(tmp_path / "ledger.json")
    base = family_overfit_bait(n_seeds=30)
    ev = evaluate_family(base, _close(seed=5), ledger=led, stamp="2026-06-12",
                         window=slice(-200, None))
    # the best of 30 random books on a short window looks "good" in-sample...
    assert ev.results["sharpe_ann"].max() > 0.5
    # ...and the ledger remembers all 30 trials for the gate to use
    assert led.total == 30


def test_sentiment_divergence_family_evaluates_and_ledgers(tmp_path):
    led = TrialLedger(tmp_path / "ledger.json")
    rng = np.random.default_rng(1)
    fng = pd.Series(np.clip(50 + np.cumsum(rng.normal(0, 2, len(IDX))), 1, 99), index=IDX)
    base = family_sentiment_divergence()
    n_grid = len(expand_grid(base))
    ev = evaluate_family(base, _close(seed=2), fng=fng, ledger=led, stamp="t")
    assert ev.returns_matrix.shape[1] == n_grid
    assert led.total == n_grid
    assert base.portfolio["score"] == "div"
