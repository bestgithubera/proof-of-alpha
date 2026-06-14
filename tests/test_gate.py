"""Gate tests: white noise must FAIL; a strong planted signal must PASS."""
import numpy as np
import pandas as pd

from strategies.families import evaluate_family, family_overfit_bait, family_xs_momentum
from validation.core import TrialLedger
from validation.gate import falsify
from validation.report_md import render_markdown

IDX = pd.date_range("2022-01-01", periods=1100, freq="D", tz="UTC")


def _noise_close(seed=0, n=10):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0, 0.02, (len(IDX), n))
    return pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=IDX,
                        columns=[f"A{i}" for i in range(n)])


def _planted_close(seed=1, n=10):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0, 0.015, (len(IDX), n))
    # planted persistent momentum: 3 assets with strong positive drift the whole time
    rets[:, :3] += 0.004
    return pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=IDX,
                        columns=[f"A{i}" for i in range(n)])


def test_overfit_bait_fails_the_gate(tmp_path):
    led = TrialLedger(tmp_path / "ledger.json")
    close = _noise_close()
    ev = evaluate_family(family_overfit_bait(n_seeds=60), close,
                         ledger=led, stamp="2026-06-12")
    rep = falsify(ev, close=close, ledger=led)
    assert rep.verdict == "FAIL"
    assert any("DSR" in r or "PBO" in r or "CPCV" in r for r in rep.reasons)
    md = render_markdown(rep, stamp="2026-06-12")
    assert "FAIL" in md and "noise" in md


def test_planted_edge_passes_the_gate(tmp_path):
    led = TrialLedger(tmp_path / "ledger.json")
    close = _planted_close()
    ev = evaluate_family(family_xs_momentum(), close, ledger=led, stamp="2026-06-12")
    rep = falsify(ev, close=close, ledger=led)
    assert rep.headline["sharpe_ann"] > 1.5          # the plant is strong by design
    assert rep.verdict in ("STRONG", "DEFENSIBLE")   # tiered effective-N gate
    md = render_markdown(rep, stamp="2026-06-12")
    assert rep.verdict in md


def test_planted_edge_survives_heavy_correlated_ledger(tmp_path):
    """The whole point of the effective-N gate: a real edge in a small correlated
    universe is NOT vetoed by a huge nominal trial count (which the old nominal-N
    DSR gate would have killed)."""
    led = TrialLedger(tmp_path / "ledger.json")
    led.record("previous-research", 100_000, stamp="2026-06-01")
    close = _planted_close()
    ev = evaluate_family(family_xs_momentum(), close, ledger=led, stamp="2026-06-12")
    rep = falsify(ev, close=close, ledger=led)
    assert rep.verdict in ("STRONG", "DEFENSIBLE")        # effective-N, not nominal 100k
    assert rep.dsr_block["n_trials_cumulative"] >= 100_000  # nominal lens still shown


def test_gate_uses_cumulative_ledger_not_local_grid(tmp_path):
    led = TrialLedger(tmp_path / "ledger.json")
    led.record("previous-research", 100_000, stamp="2026-06-01")  # heavy history
    close = _planted_close()
    ev = evaluate_family(family_xs_momentum(), close, ledger=led, stamp="2026-06-12")
    rep = falsify(ev, close=close, ledger=led)
    assert rep.dsr_block["n_trials_cumulative"] >= 100_000  # local grid alone would be 20
