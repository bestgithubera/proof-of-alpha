"""Anti-overfitting validation gate (Bailey & Lopez de Prado) — crypto edition.

Ported from the battle-tested gpw-ensemble toolkit (validation.py). A clean
backtest engine removes look-ahead in the *engine*; it does NOTHING about
selection bias from searching many strategies. This module deflates the
in-sample Sharpe for the number of trials, so a strategy that is merely the
best of N noise configs FAILS no matter how clean each individual backtest was.

Crypto is the worst-case environment for this failure mode: short histories,
fat tails, 24/7 data to mine until something looks good.

Key results encoded:
- Probabilistic Sharpe Ratio (PSR): P(true SR > benchmark) given sample size,
  skew and kurtosis (fat tails / negative skew shrink confidence).
- Expected-max-Sharpe-under-null: with N trials, the best of N pure-noise
  strategies has E[max SR] > 0. This is the benchmark the candidate must clear.
- Deflated Sharpe Ratio (DSR) = PSR against that expected-max benchmark.

CRYPTO CALENDARS — the 16x-bug class. Crypto trades 365 days/year, not 252.
Every annualisation here takes an explicit ``freq``; the module default ``ANN``
is 365 (daily bars). Use ``ANN_4H`` for 4-hour bars and ``ANN_FUNDING`` for
8-hour funding stamps. Mixing these up scales Sharpe by sqrt(freq-ratio) and
has historically produced silent 4x-16x inflation — tests pin each factor.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kurtosis as _kurtosis
from scipy.stats import norm
from scipy.stats import skew as _skew

EULER_GAMMA = 0.5772156649015329
ANN_CRYPTO_DAILY = 365.0   # crypto trades every day
ANN_4H = 365.0 * 6         # 4-hour bars
ANN_FUNDING = 365.0 * 3    # perp funding stamps every 8h
ANN_EQUITY_DAILY = 252.0   # kept for cross-checks against TradFi numbers
ANN = ANN_CRYPTO_DAILY     # module default: daily crypto bars


def probabilistic_sharpe_ratio(
    sr: float, n_obs: int, skew: float, kurt: float, sr_benchmark: float = 0.0
) -> float:
    """P(true per-period Sharpe > ``sr_benchmark``). ``kurt`` is RAW (normal=3)."""
    denom = math.sqrt(max(1e-12, 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr))
    return float(norm.cdf((sr - sr_benchmark) * math.sqrt(max(1, n_obs - 1)) / denom))


def expected_max_sharpe(n_trials: int, sr_trials_std: float) -> float:
    """E[max per-period Sharpe] across ``n_trials`` independent NULL strategies.

    The selection-bias benchmark: even pure noise, the best of N trials has a
    positive expected Sharpe. ``sr_trials_std`` = std of the per-period Sharpe
    estimates across trials.
    """
    if n_trials <= 1 or sr_trials_std <= 0:
        return 0.0
    z1 = norm.ppf(1.0 - 1.0 / n_trials)
    z2 = norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return float(sr_trials_std * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2))


def deflated_sharpe_ratio(
    sr: float, n_obs: int, skew: float, kurt: float, n_trials: int,
    sr_trials_std: float | None = None,
) -> tuple[float, float]:
    """Return (DSR, sr0_per_period). DSR = PSR against the expected-max-of-N
    benchmark. ``sr_trials_std`` defaults to the null sampling-std of the Sharpe
    estimator (conservative proxy when individual trial Sharpes aren't kept)."""
    if sr_trials_std is None:
        sr_trials_std = math.sqrt(
            max(1e-12, 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr) / max(1, n_obs - 1)
        )
    sr0 = expected_max_sharpe(n_trials, sr_trials_std)
    return probabilistic_sharpe_ratio(sr, n_obs, skew, kurt, sr_benchmark=sr0), sr0


@dataclass(frozen=True)
class ValidationReport:
    sharpe_ann: float
    n_obs: int
    n_trials: int
    psr: float                 # P(true SR > 0)
    dsr: float                 # P(true SR > expected-max-of-N-trials)
    sr0_ann: float             # the deflation benchmark, annualised
    excess_cagr_vs_baseline: float | None
    bear_mdd: float | None
    passed: bool
    reasons: tuple[str, ...]

    def __str__(self) -> str:
        ex = (
            f"{self.excess_cagr_vs_baseline*100:+.1f}pp"
            if self.excess_cagr_vs_baseline is not None else "n/a"
        )
        bm = f"{self.bear_mdd*100:.1f}%" if self.bear_mdd is not None else "n/a"
        return (
            f"Sharpe {self.sharpe_ann:.2f} (ann) | n_trials={self.n_trials} | "
            f"PSR {self.psr:.3f} | DSR {self.dsr:.3f} (vs sr0_ann {self.sr0_ann:.2f}) | "
            f"excess-vs-baseline {ex} | bear-MDD {bm} | "
            f"{'PASS' if self.passed else 'FAIL'} [{', '.join(self.reasons)}]"
        )


def validate_strategy(
    returns: pd.Series,
    *,
    n_trials: int,
    baseline_returns: pd.Series | None = None,
    bear_mdd: float | None = None,
    min_dsr: float = 0.95,
    min_excess_cagr: float = 0.0,
    max_bear_mdd: float = -0.30,
    freq: float = ANN,
) -> ValidationReport:
    """Run the anti-overfitting gate on per-period returns sampled at ``freq``
    periods/year. PASS requires: DSR >= min_dsr (Sharpe survives deflation for
    ``n_trials``), beats the baseline net CAGR, and (if a bear MDD is supplied)
    holds within ``max_bear_mdd``."""
    r = pd.Series(returns).dropna().astype(float)
    n = len(r)
    mu, sd = float(r.mean()), float(r.std(ddof=1))
    sr = mu / sd if sd > 1e-12 else 0.0
    sk = float(_skew(r)) if n > 2 else 0.0
    ku = float(_kurtosis(r, fisher=False)) if n > 3 else 3.0  # raw kurtosis
    psr = probabilistic_sharpe_ratio(sr, n, sk, ku, 0.0)
    dsr, sr0 = deflated_sharpe_ratio(sr, n, sk, ku, n_trials)

    excess = None
    if baseline_returns is not None:
        b = pd.Series(baseline_returns).dropna().astype(float)
        cagr_s = (1.0 + r).prod() ** (freq / max(1, n)) - 1.0
        cagr_b = (1.0 + b).prod() ** (freq / max(1, len(b))) - 1.0
        excess = float(cagr_s - cagr_b)

    reasons: list[str] = []
    if dsr < min_dsr:
        reasons.append(f"DSR {dsr:.2f}<{min_dsr}")
    if excess is not None and excess < min_excess_cagr:
        reasons.append(f"excess {excess*100:+.1f}pp<{min_excess_cagr*100:.0f}")
    if bear_mdd is not None and bear_mdd < max_bear_mdd:
        reasons.append(f"bear-MDD {bear_mdd*100:.0f}%<{max_bear_mdd*100:.0f}%")
    passed = not reasons
    if passed:
        reasons.append("ok")
    return ValidationReport(
        sharpe_ann=sr * math.sqrt(freq), n_obs=n, n_trials=n_trials,
        psr=psr, dsr=dsr, sr0_ann=sr0 * math.sqrt(freq),
        excess_cagr_vs_baseline=excess, bear_mdd=bear_mdd, passed=passed,
        reasons=tuple(reasons),
    )


# =====================================================================================
# Anti-overfitting toolkit (the protocol made mechanical).
# Grounded in Bailey & Lopez de Prado (DSR/PBO/CSCV/MinBTL) and Harvey & Liu 2015
# (haircut/FDR). The deflated Sharpe above handles the BEST-of-N; these handle the
# rest of the protocol: cumulative trial accounting, probability of backtest
# overfitting, effective trials under correlation, minimum backtest length, the
# multiple-testing haircut, decay, parameter robustness, and feature causality.
# =====================================================================================


def _sr(x: np.ndarray) -> float:
    """Per-period Sharpe (mean/std) of a 1-D array; 0 if degenerate."""
    sd = x.std(ddof=1)
    return float(x.mean() / sd) if sd > 1e-12 else 0.0


class TrialLedger:
    """Persistent CUMULATIVE trial counter — Rule 1 of the protocol.

    Every backtest on a dataset counts toward ``n_trials`` in the deflated Sharpe,
    FOREVER and across sessions. A strategy that "passes" a local gate of a few
    hundred trials can fail the cumulative thousands-trial gate (the 'local-pass'
    trap). This makes the cumulative count durable: load it, record each batch,
    pass ``total`` to the gate. Records the hypothesis + economic mechanism
    alongside, because a number without a hypothesis is just mining."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data: dict = {"total_trials": 0, "entries": []}
        if self.path.exists():
            self.data = json.loads(self.path.read_text())

    @property
    def total(self) -> int:
        return int(self.data.get("total_trials", 0))

    def record(self, label: str, n_trials: int, *, hypothesis: str = "",
               mechanism: str = "", stamp: str = "") -> int:
        """Add a batch of ``n_trials`` and persist. Returns the new cumulative total.
        ``stamp`` is an externally-supplied date string (no clock in this module)."""
        self.data["entries"].append({
            "label": label, "n_trials": int(n_trials), "hypothesis": hypothesis,
            "mechanism": mechanism, "stamp": stamp,
        })
        self.data["total_trials"] = self.total + int(n_trials)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2))
        return self.total


def effective_n_trials(returns_matrix: pd.DataFrame) -> float:
    """Effective number of INDEPENDENT trials given correlated strategies.

    Grid-searched configs are typically highly correlated (all variations of
    "long crypto beta"), so treating them as independent over-penalises (and
    invites the "your trials aren't independent" rebuttal). Uses the
    participation ratio of the correlation-matrix eigenvalues:
    ``N_eff = (sum lambda)^2 / sum(lambda^2) = N^2 / sum(lambda^2)``. Equals N
    when all independent, 1 when all identical. Honest middle ground."""
    R = pd.DataFrame(returns_matrix).dropna(how="all", axis=1).dropna()
    # zero-variance columns (e.g. a regime gate that never opens) carry no
    # correlation information and poison corrcoef with NaN — drop them
    R = R.loc[:, R.std(ddof=1) > 1e-12]
    if R.shape[1] < 2:
        return float(max(R.shape[1], 1))
    C = np.corrcoef(R.values, rowvar=False)
    C = np.nan_to_num(C, nan=0.0)
    lam = np.linalg.eigvalsh(C)
    lam = lam[lam > 0]
    return float((lam.sum() ** 2) / (lam ** 2).sum())


def min_backtest_length(n_trials: int, sharpe_ann: float) -> float:
    """Minimum backtest length (YEARS) below which an annual Sharpe of ``sharpe_ann``
    is indistinguishable from the best of ``n_trials`` pure-noise strategies
    (Bailey et al, "Pseudo-mathematics and financial charlatanism").

    MinBTL_years = ( [(1-g)Z(1-1/N) + g Z(1-1/(N e))] / SR_ann )^2 . Compare to the
    actual track length: if MinBTL > years_available, the result CANNOT be trusted
    no matter how clean — you simply don't have enough data for that many trials."""
    if n_trials <= 1 or sharpe_ann <= 0:
        return float("inf")
    z1 = norm.ppf(1.0 - 1.0 / n_trials)
    z2 = norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    emax = (1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2
    return float((emax / sharpe_ann) ** 2)


def monte_carlo_null(
    returns: pd.Series, *, n_sims: int = 1000, block: int = 5, seed: int = 0,
    freq: float = ANN,
) -> dict:
    """Stationary block-bootstrap of the Sharpe ratio -> uncertainty band + a luck
    p-value. Resamples blocks (mean length ``block``) to respect autocorrelation,
    recomputes the annualised Sharpe each sim. Returns the SE and 95% CI (Rule:
    report Sharpe +- SE, never a point estimate) and ``p_le_zero`` = fraction of
    resamples with Sharpe <= 0 (how fragile the 'profitable' verdict is)."""
    r = pd.Series(returns).dropna().to_numpy()
    n = len(r)
    sqrt_ann = math.sqrt(freq)
    if n < 20:
        return {"sharpe": _sr(r) * sqrt_ann, "se": float("nan"),
                "ci": (float("nan"), float("nan")), "p_le_zero": float("nan")}
    rng = np.random.default_rng(seed)
    p_cont = 1.0 - 1.0 / max(1, block)
    out = np.empty(n_sims)
    for s in range(n_sims):
        idx = np.empty(n, dtype=int)
        idx[0] = rng.integers(n)
        cont = rng.random(n) < p_cont
        jumps = rng.integers(n, size=n)
        for i in range(1, n):
            idx[i] = (idx[i - 1] + 1) % n if cont[i] else jumps[i]
        out[s] = _sr(r[idx]) * sqrt_ann
    return {
        "sharpe": _sr(r) * sqrt_ann,
        "se": float(out.std(ddof=1)),
        "ci": (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))),
        "p_le_zero": float((out <= 0).mean()),
    }


def pbo_cscv(returns_matrix: pd.DataFrame, *, n_blocks: int = 12, max_combos: int = 2000,
             seed: int = 0) -> dict:
    """Probability of Backtest Overfitting via Combinatorially-Symmetric Cross-
    Validation (Bailey, Borwein, Lopez de Prado, Zhu 2017).

    Splits the T x N returns matrix (rows=time, cols=strategies) into ``n_blocks``,
    and over the combinations of half-the-blocks-as-IS: picks the IS-best strategy
    and records its OOS RANK. PBO = fraction of splits where the IS-best lands BELOW
    the OOS median (logit <= 0). PBO near 1.0 => "the in-sample winner is, OOS,
    typically a below-median strategy" = the search is an overfitting machine.
    Complements the deflated Sharpe: DSR judges the single best number, PBO judges
    the SELECTION PROCESS itself."""
    R = pd.DataFrame(returns_matrix).dropna()
    M = R.to_numpy()
    T, N = M.shape
    if N < 2 or n_blocks * 2 > T:
        return {"pbo": float("nan"), "n_strategies": N,
                "median_oos_rank": float("nan"), "n_splits": 0}
    n_blocks -= n_blocks % 2
    edges = np.linspace(0, T, n_blocks + 1, dtype=int)
    blocks = [np.arange(edges[i], edges[i + 1]) for i in range(n_blocks)]
    half = n_blocks // 2
    combos = list(combinations(range(n_blocks), half))
    rng = np.random.default_rng(seed)
    if len(combos) > max_combos:
        combos = [combos[i] for i in rng.choice(len(combos), max_combos, replace=False)]
    logits, ranks = [], []
    for c in combos:
        is_rows = np.concatenate([blocks[i] for i in c])
        oos_rows = np.concatenate([blocks[i] for i in range(n_blocks) if i not in c])
        is_sr = M[is_rows].mean(0) / (M[is_rows].std(0, ddof=1) + 1e-12)
        oos_sr = M[oos_rows].mean(0) / (M[oos_rows].std(0, ddof=1) + 1e-12)
        n_star = int(np.argmax(is_sr))
        # relative OOS rank of the IS-best, in (0,1)
        omega = (np.sum(oos_sr < oos_sr[n_star]) + 1) / (N + 1)
        omega = min(max(omega, 1e-6), 1 - 1e-6)
        logits.append(math.log(omega / (1 - omega)))
        ranks.append(omega)
    logits = np.array(logits)
    return {
        "pbo": float((logits <= 0).mean()),
        "n_strategies": N,
        "n_splits": len(combos),
        "median_oos_rank": float(np.median(ranks)),
        "mean_logit": float(logits.mean()),
    }


def cpcv_paths(returns_matrix: pd.DataFrame, *, n_blocks: int = 12,
               max_combos: int = 2000, embargo: int = 0, seed: int = 0,
               freq: float = ANN) -> dict:
    """Combinatorial cross-validation: the DISTRIBUTION of out-of-sample Sharpe for
    the strategy you would have SELECTED in-sample, across many train/test block
    recombinations (Lopez de Prado, *Advances in Financial ML*, ch. 7/12).

    One walk-forward yields a SINGLE OOS path -- easy to get lucky on. CPCV splits
    the T x N matrix into ``n_blocks`` and, over every way to use half the blocks as
    IS, picks the IS-best strategy and records ITS OOS Sharpe. The spread of those
    OOS Sharpes is the honest forward band; ``selection_haircut`` = mean(IS Sharpe of
    the IS-best - its OOS Sharpe) is the degradation you pay for choosing on the
    backtest. ``embargo`` drops train rows within that many steps of any test block to
    stop serial-correlation leakage across the IS/OOS boundary. Complements
    ``pbo_cscv`` (PROBABILITY the IS-best is OOS-below-median) with the MAGNITUDE of
    the OOS decay -- the number you should actually expect forward."""
    R = pd.DataFrame(returns_matrix).dropna()
    M = R.to_numpy()
    T, N = M.shape
    if N < 2 or n_blocks * 2 > T:
        return {"oos_sharpe_mean": float("nan"), "n_splits": 0, "n_strategies": N}
    n_blocks -= n_blocks % 2
    edges = np.linspace(0, T, n_blocks + 1, dtype=int)
    blocks = [np.arange(edges[i], edges[i + 1]) for i in range(n_blocks)]
    half = n_blocks // 2
    combos = list(combinations(range(n_blocks), half))
    rng = np.random.default_rng(seed)
    if len(combos) > max_combos:
        combos = [combos[i] for i in rng.choice(len(combos), max_combos, replace=False)]
    sqrt_ann = math.sqrt(freq)
    is_srs, oos_srs = [], []
    for c in combos:
        oos_b = [i for i in range(n_blocks) if i not in c]
        is_rows = np.concatenate([blocks[i] for i in c])
        oos_rows = np.concatenate([blocks[i] for i in oos_b])
        if embargo > 0:                                   # purge train rows near a test edge
            bad = np.zeros(T, dtype=bool)
            for i in oos_b:
                bad[max(0, edges[i] - embargo):min(T, edges[i + 1] + embargo)] = True
            is_rows = is_rows[~bad[is_rows]]
        if len(is_rows) < 10 or len(oos_rows) < 10:
            continue
        is_sr = M[is_rows].mean(0) / (M[is_rows].std(0, ddof=1) + 1e-12)
        oos_sr = M[oos_rows].mean(0) / (M[oos_rows].std(0, ddof=1) + 1e-12)
        n_star = int(np.argmax(is_sr))
        is_srs.append(float(is_sr[n_star] * sqrt_ann))
        oos_srs.append(float(oos_sr[n_star] * sqrt_ann))
    if not oos_srs:
        return {"oos_sharpe_mean": float("nan"), "n_splits": 0, "n_strategies": N}
    oos = np.array(oos_srs)
    is_ = np.array(is_srs)
    return {
        "oos_sharpe_mean": float(oos.mean()),
        "oos_sharpe_median": float(np.median(oos)),
        "oos_sharpe_std": float(oos.std(ddof=1)) if len(oos) > 1 else 0.0,
        "oos_sharpe_p5": float(np.percentile(oos, 5)),
        "oos_sharpe_p95": float(np.percentile(oos, 95)),
        "is_sharpe_mean": float(is_.mean()),
        "selection_haircut": float(is_.mean() - oos.mean()),
        "frac_oos_positive": float((oos > 0).mean()),
        "n_splits": len(oos_srs),
        "n_strategies": N,
    }


def haircut_sharpe(sharpe_ann: float, n_obs: int, n_trials: int, freq: float = ANN) -> dict:
    """Harvey & Liu (2015) multiple-testing HAIRCUT of a reported Sharpe.

    Converts SR to a t-stat, applies a Bonferroni multiple-testing correction for
    ``n_trials`` tests, and reports the haircut Sharpe (the SR you can still defend
    after accounting for the search). Complements the deflated Sharpe with the FDR
    school: this is the 'reduce your headline number' view of the same problem."""
    yrs = n_obs / freq
    t = sharpe_ann * math.sqrt(max(yrs, 1e-9))
    p_single = 2.0 * (1.0 - norm.cdf(abs(t)))           # two-sided single-test p
    p_bonf = min(1.0, p_single * n_trials)
    # back out the haircut t-stat that corresponds to the adjusted p, two-sided
    t_adj = float(norm.ppf(1.0 - p_bonf / 2.0)) if p_bonf < 1.0 else 0.0
    haircut_sr = sharpe_ann * (t_adj / t) if t > 1e-9 else 0.0
    return {
        "sharpe_ann": sharpe_ann, "t_stat": t, "p_single": p_single,
        "p_bonferroni": p_bonf, "haircut_sharpe": haircut_sr,
        "haircut_pct": float(1.0 - (haircut_sr / sharpe_ann)) if sharpe_ann else float("nan"),
    }


def anomaly_decay(returns: pd.Series, *, n_subperiods: int = 6, freq: float = ANN) -> dict:
    """Split the track record into ``n_subperiods`` equal blocks and fit a linear
    trend to the per-block Sharpe. Negative slope = a decaying edge (McLean-Pontiff:
    anomalies fade ~58% after publication; crypto edges fade faster). Returns the
    sub-period Sharpes + slope."""
    r = pd.Series(returns).dropna().to_numpy()
    if len(r) < n_subperiods * 10:
        return {"subperiod_sharpe": [], "slope": float("nan")}
    sqrt_ann = math.sqrt(freq)
    chunks = np.array_split(r, n_subperiods)
    srs = [(_sr(c) * sqrt_ann) for c in chunks]
    x = np.arange(n_subperiods)
    slope = float(np.polyfit(x, srs, 1)[0])
    return {
        "subperiod_sharpe": [round(s, 2) for s in srs], "slope": slope,
        "first_half": float(np.mean(srs[: n_subperiods // 2])),
        "second_half": float(np.mean(srs[n_subperiods // 2:])),
    }


def capacity_curve(gross_ann_return: float, *, ann_turnover: float, n_positions: int,
                   median_adv_usd: float, aum_grid_usd, n_rebals_per_year: int = 52,
                   impact_coef: float = 0.1, impact_exp: float = 0.5,
                   base_cost_bps: float = 20.0) -> dict:
    """Capacity / market-impact -- the lever that kills small-cap-token 'winners'.
    Models net return DECAYING as AUM grows: at AUM A each of ``n_positions`` names
    holds ~A/n_positions; one rebalance trades ``ann_turnover/n_rebals`` of that, so
    the typical trade notional ~ (A/n_positions)*(ann_turnover/n_rebals). Market
    impact as a FRACTION of trade value = ``impact_coef``*(trade/ADV)**``impact_exp``
    (square-root law; impact_coef = slippage when one trade equals 100% of median
    daily ADV). Annual impact drag = ann_turnover*impact_fraction; net = gross -
    base_cost_drag - impact_drag. ``capacity_usd`` = largest AUM whose net still
    clears half its smallest-size net -- past it, scaling destroys the edge. Tiny
    ADV (long-tail tokens) -> capacity collapses toward zero, which is exactly why
    illiquid backtest winners are un-investable at any real size."""
    aum = np.asarray(list(aum_grid_usd), dtype=float)
    base_drag = ann_turnover * base_cost_bps / 1e4
    per_name = aum / max(1, n_positions)
    trade_notional = per_name * (ann_turnover / max(1, n_rebals_per_year))
    participation = trade_notional / max(1e-9, median_adv_usd)
    impact_fraction = impact_coef * np.power(np.clip(participation, 0.0, None), impact_exp)
    impact_drag = ann_turnover * impact_fraction
    net = gross_ann_return - base_drag - impact_drag
    net_small = float(net[0]) if len(net) else float("nan")
    thresh = max(0.0, 0.5 * net_small)
    ok = net >= thresh
    return {
        "aum_usd": [float(a) for a in aum],
        "net_ann_return": [float(x) for x in net],
        "impact_drag": [float(x) for x in impact_drag],
        "participation": [float(x) for x in participation],
        "capacity_usd": float(aum[ok].max()) if ok.any() else 0.0,
        "net_at_smallest": net_small,
        "capacity_thresh": thresh,
    }


def parameter_sensitivity(results: pd.DataFrame, param_cols: list[str], metric_col: str,
                          *, tol: float = 0.25) -> dict:
    """Robustness-over-peak. For the best config, walk +-1 step along each
    parameter's sorted unique values and measure the metric drop; also report the
    fraction of each parameter's range that stays within ``tol`` of the best. A
    sharp peak (neighbours collapse) = overfit; a broad plateau = (maybe) real.
    Heuristic: a good parameter holds over >= 25% of its range."""
    df = pd.DataFrame(results)
    best = df.loc[df[metric_col].idxmax()]
    best_val = float(best[metric_col])
    out: dict = {"best_metric": best_val, "per_param": {}}
    plateau_fracs = []
    for p in param_cols:
        vals = sorted(df[p].dropna().unique())
        if len(vals) < 2:
            continue
        bi = vals.index(best[p]) if best[p] in vals else 0
        neigh = []
        for j in (bi - 1, bi + 1):
            if 0 <= j < len(vals):
                # hold the OTHER params at the best, vary this one
                mask = pd.Series(True, index=df.index)
                for q in param_cols:
                    if q != p:
                        mask &= (df[q] == best[q])
                sub = df[mask & (df[p] == vals[j])]
                if len(sub):
                    neigh.append(float(sub[metric_col].max()))
        drop = (best_val - np.mean(neigh)) / abs(best_val) if neigh and best_val else float("nan")
        # plateau: fraction of this param's settings within tol of best (others = best)
        mask = pd.Series(True, index=df.index)
        for q in param_cols:
            if q != p:
                mask &= (df[q] == best[q])
        line = df[mask]
        frac = (float((line[metric_col] >= best_val * (1 - tol)).mean())
                if len(line) else float("nan"))
        plateau_fracs.append(frac)
        out["per_param"][p] = {"best": best[p], "neighbour_drop_pct": drop, "plateau_frac": frac}
    out["min_plateau_frac"] = float(np.nanmin(plateau_fracs)) if plateau_fracs else float("nan")
    out["robust"] = bool(out["min_plateau_frac"] >= tol) if plateau_fracs else False
    return out


def parameter_stability(returns: pd.Series, *, n_subperiods: int = 6,
                        min_sharpe: float = 0.0, stable_frac: float = 0.75,
                        max_cv: float = 1.5, freq: float = ANN) -> dict:
    """Temporal robustness -- the 'no drift over time' check (its sibling
    ``parameter_sensitivity`` is the 'holds over >=25% of the parameter range' half).
    Splits the track into ``n_subperiods`` equal blocks and asks whether the edge is
    CONSISTENT across time or carried by one lucky stretch: per-block annual Sharpe,
    dispersion (coefficient of variation), the worst block, and the fraction of blocks
    clearing ``min_sharpe``. 'stable' = profitable in >= ``stable_frac`` of blocks with
    CV <= ``max_cv``. Differs from ``anomaly_decay`` (which fits the fade SLOPE / a
    monotonic direction); this measures dispersion / consistency regardless of trend."""
    r = pd.Series(returns).dropna().to_numpy()
    if len(r) < n_subperiods * 10:
        return {"subperiod_sharpe": [], "stable": False, "cv": float("nan"),
                "frac_above_min": float("nan"), "worst": float("nan")}
    sqrt_ann = math.sqrt(freq)
    chunks = np.array_split(r, n_subperiods)
    srs = np.array([_sr(c) * sqrt_ann for c in chunks])
    mean = float(srs.mean())
    sd = float(srs.std(ddof=1)) if len(srs) > 1 else 0.0
    cv = float(sd / abs(mean)) if abs(mean) > 1e-9 else float("inf")
    frac = float((srs > min_sharpe).mean())
    return {
        "subperiod_sharpe": [round(float(s), 2) for s in srs],
        "mean": mean, "std": sd, "cv": cv,
        "worst": float(srs.min()), "best": float(srs.max()),
        "frac_above_min": frac,
        "stable": bool(frac >= stable_frac and cv <= max_cv),
    }


def causality_audit(stored: pd.Series, recomputed: pd.Series, *, tol: float = 1e-6) -> dict:
    """Compare a STORED (bulk-precomputed) feature against a STRICTLY-CAUSAL
    recomputation (data <= t only) on the same dates. Any material mismatch = a
    look-ahead leak baked into the panel — the class of bug that silently inflates
    every downstream backtest when features are computed in bulk over the whole
    panel."""
    a, b = stored.align(recomputed, join="inner")
    d = (a - b).abs()
    denom = a.abs().clip(lower=1e-9)
    rel = (d / denom).replace([np.inf, -np.inf], np.nan).dropna()
    n_mismatch = int((rel > tol).sum())
    return {
        "n_compared": int(len(rel)),
        "n_mismatch": n_mismatch,
        "frac_mismatch": float(n_mismatch / len(rel)) if len(rel) else float("nan"),
        "max_abs_diff": float(d.max()) if len(d) else float("nan"),
        "corr": float(a.corr(b)) if len(a) > 2 else float("nan"),
        "leak_suspected": bool(n_mismatch > 0.01 * max(1, len(rel))),
    }


__all__ = [
    "ANN", "ANN_CRYPTO_DAILY", "ANN_4H", "ANN_FUNDING", "ANN_EQUITY_DAILY",
    "probabilistic_sharpe_ratio",
    "expected_max_sharpe",
    "deflated_sharpe_ratio",
    "validate_strategy",
    "ValidationReport",
    "TrialLedger",
    "effective_n_trials",
    "min_backtest_length",
    "monte_carlo_null",
    "pbo_cscv",
    "cpcv_paths",
    "haircut_sharpe",
    "anomaly_decay",
    "capacity_curve",
    "parameter_sensitivity",
    "parameter_stability",
    "causality_audit",
]
