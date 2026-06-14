"""Candidate strategy families + the honest evaluator.

Each family is a BASE SPEC with a declared params_grid (the full searched
space). ``evaluate_family`` expands the grid, backtests every variant, records
the WHOLE batch in the trial ledger (Rule 1: every evaluated config counts,
forever), and returns the per-variant results plus the T x N net-returns matrix
the falsification gate needs (PBO/CPCV/effective-N all operate on that matrix).

The fourth family, ``overfit_bait``, is the demo villain: best-of-N RANDOM
portfolios on a short window. It has no mechanism and its hypothesis says so —
the gate must kill it, and the trial ledger is exactly the instrument that does.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtest.engine import backtest
from backtest.metrics import summary
from strategies.spec import SIGNAL_REGISTRY, StrategySpec, compile_strategy, expand_grid
from validation.core import ANN_CRYPTO_DAILY, TrialLedger


def sig_random_score(close: pd.DataFrame, *, seed: int = 0, **_) -> pd.DataFrame:
    """Pure-noise ranking score — exists ONLY for the overfit-bait family."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.standard_normal(close.shape),
                        index=close.index, columns=close.columns)


SIGNAL_REGISTRY.setdefault("random_score", sig_random_score)


def family_xs_momentum() -> StrategySpec:
    return StrategySpec(
        name="xs_momentum",
        hypothesis=(
            "Cross-sectional 14-120d momentum persists among BNB-ecosystem tokens "
            "because attention, listing and flow shocks are autocorrelated; refuted "
            "if the edge does not survive cost stress and trial deflation."),
        signals=[{"id": "mom", "fn": "ts_momentum", "args": {"window": 60}}],
        portfolio={"type": "xs_topk", "score": "mom", "k": 5,
                   "direction": "long", "rebalance": "W-MON"},
        params_grid={"signals.mom.args.window": [14, 30, 60, 90, 120],
                     "portfolio.k": [3, 5, 8, 10]},
    )


def family_funding_carry() -> StrategySpec:
    return StrategySpec(
        name="funding_carry",
        hypothesis=(
            "Perp funding paid by levered longs is a persistent risk premium: a "
            "hedged short-perp/long-spot book on the highest-funding names earns "
            "it net of double-leg costs; refuted if net Sharpe dies under deflation "
            "or cost stress."),
        signals=[{"id": "f", "fn": "funding_rate", "args": {"window": 7}}],
        portfolio={"type": "funding_carry", "score": "f", "k": 5,
                   "rebalance": "W-MON", "min_funding_daily": 0.0},
        params_grid={"signals.f.args.window": [3, 7, 14],
                     "portfolio.k": [3, 5, 8],
                     "portfolio.min_funding_daily": [0.0, 0.0001]},
    )


def family_fng_regime() -> StrategySpec:
    return StrategySpec(
        name="fng_regime_momentum",
        hypothesis=(
            "Momentum among BNB-ecosystem tokens pays only in non-fear regimes; "
            "gating the book on the Fear & Greed index avoids crash beta. Refuted "
            "if the gated book does not beat the ungated one after deflation for "
            "the threshold search."),
        signals=[{"id": "mom", "fn": "ts_momentum", "args": {"window": 60}},
                 {"id": "fng", "fn": "fear_greed", "args": {}}],
        portfolio={"type": "xs_topk", "score": "mom", "k": 5,
                   "direction": "long", "rebalance": "W-MON",
                   "regime_gate": {"signal": "fng", "min": 25, "max": 100}},
        params_grid={"signals.mom.args.window": [30, 60, 90],
                     "portfolio.k": [5, 8],
                     "portfolio.regime_gate.min": [15, 25, 35, 45]},
    )


def family_sentiment_divergence() -> StrategySpec:
    return StrategySpec(
        name="sentiment_divergence",
        hypothesis=(
            "Cross-sectional momentum pays in FEAR (genuine accumulation against "
            "the crowd) but reverses in GREED (late chasers unwind); a book that "
            "plays momentum in fear and goes contrarian in greed earns the "
            "divergence. Refuted if it does not beat plain momentum after cost "
            "stress and trial deflation."),
        signals=[{"id": "div", "fn": "fng_divergence",
                  "args": {"price_window": 30, "fng_pivot": 50.0}}],
        portfolio={"type": "xs_topk", "score": "div", "k": 5,
                   "direction": "long", "rebalance": "W-MON"},
        params_grid={"signals.div.args.price_window": [14, 30, 60],
                     "signals.div.args.fng_pivot": [40.0, 50.0, 60.0],
                     "portfolio.k": [3, 5, 8]},
    )


def family_xs_mom_voltarget() -> StrategySpec:
    return StrategySpec(
        name="xs_mom_voltarget",
        hypothesis=(
            "Cross-sectional momentum among BNB-ecosystem tokens persists via "
            "attention/flow autocorrelation; a ~40%-annual-vol target delevers in "
            "turbulence to cap crash beta. Refuted if the managed book does not "
            "stay positive out-of-sample after cost stress and trial deflation."),
        signals=[{"id": "mom", "fn": "ts_momentum", "args": {"window": 90}}],
        portfolio={"type": "xs_topk", "score": "mom", "k": 5, "direction": "long",
                   "rebalance": "W-MON", "vol_target": 0.40, "vol_lookback": 20,
                   "max_leverage": 3.0},
        # vol_target fixed at a standard 40% ann (an a-priori risk choice, NOT
        # searched) — only the momentum window and book size are the search axes,
        # so selection bias stays comparable to plain momentum.
        params_grid={"signals.mom.args.window": [14, 30, 60, 90, 120],
                     "portfolio.k": [3, 5, 8, 10]},
    )


def family_momentum_rsi_macd_fng() -> StrategySpec:
    return StrategySpec(
        name="momentum_rsi_macd_fng",
        hypothesis=(
            "A long book that ENTERS tokens when MACD turns up (histogram > 0) "
            "and the market is not greedy (Fear & Greed <= 65), and EXITS on RSI "
            "overbought (> 70) or MACD rolling over, harvests trend while "
            "sidestepping late-greed reversals. Refuted if it does not beat "
            "buy-and-hold net of costs after trial deflation."),
        signals=[{"id": "macd", "fn": "macd", "args": {"fast": 12, "slow": 26, "signal": 9}},
                 {"id": "rsi", "fn": "rsi", "args": {"window": 14}},
                 {"id": "fng", "fn": "fear_greed", "args": {}}],
        portfolio={"type": "entry_exit",
                   "entry": {"all": [{"signal": "macd", "op": ">", "value": 0.0},
                                     {"signal": "fng", "op": "<=", "value": 65}]},
                   "exit": {"any": [{"signal": "rsi", "op": ">", "value": 70},
                                    {"signal": "macd", "op": "<", "value": 0.0}]},
                   "sizing": "equal", "max_positions": 8, "rebalance": "1d"},
        params_grid={"signals.rsi.args.window": [14, 21],
                     "portfolio.exit.any.0.value": [70, 75, 80],
                     "portfolio.entry.all.1.value": [55, 65, 75]},
    )


def family_funding_regime_switch() -> StrategySpec:
    return StrategySpec(
        name="funding_regime_switch",
        hypothesis=(
            "Aggregate perp funding measures crowd leverage/positioning: when "
            "market-wide funding is rich (longs crowded) the tape is froth-prone, "
            "so stand aside; run cross-sectional momentum only when funding is "
            "neutral/negative. Refuted if the funding-gated book does not beat the "
            "ungated one after deflation."),
        signals=[{"id": "mom", "fn": "ts_momentum", "args": {"window": 60}},
                 {"id": "fmkt", "fn": "funding_market", "args": {"window": 7}}],
        portfolio={"type": "xs_topk", "score": "mom", "k": 5, "direction": "long",
                   "rebalance": "W-MON",
                   "regime_gate": {"signal": "fmkt", "min": -1.0, "max": 0.0001}},
        params_grid={"signals.mom.args.window": [30, 60, 90],
                     "portfolio.k": [5, 8],
                     "portfolio.regime_gate.max": [0.00005, 0.0001, 0.0002]},
    )


def family_overfit_bait(n_seeds: int = 400) -> StrategySpec:
    return StrategySpec(
        name="overfit_bait",
        hypothesis=(
            "NONE — this is deliberately the best of many random portfolios on a "
            "short window. It exists to show that a clean engine plus a great "
            "in-sample Sharpe proves nothing; the gate must kill it."),
        signals=[{"id": "lucky", "fn": "random_score", "args": {"seed": 0}}],
        portfolio={"type": "xs_topk", "score": "lucky", "k": 3,
                   "direction": "long", "rebalance": "W-MON"},
        params_grid={"signals.lucky.args.seed": list(range(n_seeds))},
    )


FAMILIES = {
    "xs_momentum": family_xs_momentum,
    "xs_mom_voltarget": family_xs_mom_voltarget,
    "funding_carry": family_funding_carry,
    "fng_regime": family_fng_regime,
    "sentiment_divergence": family_sentiment_divergence,
    "momentum_rsi_macd_fng": family_momentum_rsi_macd_fng,
    "funding_regime_switch": family_funding_regime_switch,
    "overfit_bait": family_overfit_bait,
}


@dataclass
class FamilyEvaluation:
    base: StrategySpec
    results: pd.DataFrame          # one row per variant: params + metrics
    returns_matrix: pd.DataFrame   # T x N net per-bar returns (gate input)
    best_name: str
    best_spec: StrategySpec
    best_returns: pd.Series
    ledger_total: int


def evaluate_family(
    base: StrategySpec,
    close: pd.DataFrame,
    *,
    funding: pd.DataFrame | None = None,
    fng: pd.Series | None = None,
    ledger: TrialLedger,
    stamp: str,
    freq: float = ANN_CRYPTO_DAILY,
    window: slice | None = None,
) -> FamilyEvaluation:
    """Backtest every grid variant, ledger the batch, return matrix + best.

    ``window`` optionally restricts the EVALUATION window (the bait family uses
    a short recent slice — short windows make luck cheap)."""
    variants = expand_grid(base)
    rows, rets = [], {}
    specs = {}
    for v in variants:
        cs = compile_strategy(v, close, funding=funding, fng=fng)
        res = backtest(close, cs.weights, fee_bps=cs.fee_bps,
                       slippage_bps=cs.slippage_bps, funding_daily=funding,
                       funding_weights=cs.funding_weights)
        r = res.returns if window is None else res.returns.iloc[window]
        eq = res.equity if window is None else (1.0 + r).cumprod()
        m = summary(r, eq, res.turnover, freq=freq)
        rows.append({"name": v.name, **_grid_values(base, v), **m})
        rets[v.name] = r
        specs[v.name] = v

    results = pd.DataFrame(rows)
    matrix = pd.DataFrame(rets)
    total = ledger.record(
        base.name, len(variants), hypothesis=base.hypothesis,
        mechanism=base.portfolio.get("type", ""), stamp=stamp)
    best_name = results.loc[results["sharpe_ann"].idxmax(), "name"]
    return FamilyEvaluation(
        base=base, results=results, returns_matrix=matrix,
        best_name=best_name, best_spec=specs[best_name],
        best_returns=matrix[best_name], ledger_total=total,
    )


def _grid_values(base: StrategySpec, variant: StrategySpec) -> dict:
    """Extract the grid coordinates of a variant from its generated name."""
    out = {}
    if "__" in variant.name:
        for part in variant.name.split("__", 1)[1].split("_"):
            if "=" in part:
                k, v = part.split("=", 1)
                try:
                    out[k] = float(v) if "." in v else int(v)
                except ValueError:
                    out[k] = v
    return out
