"""Strategy spec: dataclass, (de)serialisation, grid expansion, and the compiler
from spec -> weight frames the backtest engine consumes.

See docs/spec-format.md for the contract. The compiler is deterministic and
side-effect free: (spec, market data) -> CompiledStrategy.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- spec


@dataclass
class StrategySpec:
    name: str
    hypothesis: str
    signals: list[dict]
    portfolio: dict
    universe: dict = field(default_factory=lambda: {"filter": "tradeable",
                                                    "min_history_days": 200})
    bar: str = "1d"
    costs: dict = field(default_factory=lambda: {"fee_bps": 10.0, "slippage_bps": 5.0})
    params_grid: dict = field(default_factory=dict)
    falsification: dict = field(default_factory=lambda: {
        "min_dsr": 0.95, "n_trials_policy": "cumulative_ledger"})
    version: int = 1

    def to_json(self, path: str | Path | None = None) -> str:
        s = json.dumps(self.__dict__, indent=2, ensure_ascii=False)
        if path is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(s)
        return s

    @classmethod
    def from_json(cls, src: str | Path) -> "StrategySpec":
        text = Path(src).read_text() if isinstance(src, Path) or (
            isinstance(src, str) and src.lstrip()[:1] != "{") else src
        d = json.loads(text)
        return cls(**d)

    def validate(self) -> None:
        if not self.hypothesis or len(self.hypothesis) < 20:
            raise ValueError("hypothesis must be a falsifiable sentence, not a stub")
        ids = [s["id"] for s in self.signals]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate signal ids")
        for s in self.signals:
            if s["fn"] not in SIGNAL_REGISTRY:
                raise ValueError(f"unknown signal fn '{s['fn']}'")
        ptype = self.portfolio.get("type")
        if ptype not in ("xs_topk", "funding_carry", "entry_exit"):
            raise ValueError(f"unknown portfolio type '{ptype}'")
        score = self.portfolio.get("score")
        if ptype == "xs_topk" and score not in ids:
            raise ValueError(f"portfolio.score '{score}' is not a declared signal")
        if ptype == "entry_exit":
            for grp_key in ("entry", "exit"):
                grp = self.portfolio.get(grp_key, {})
                conds = grp.get("all", []) + grp.get("any", [])
                if not conds:
                    raise ValueError(f"entry_exit portfolio needs '{grp_key}' conditions")
                for c in conds:
                    if c.get("signal") not in ids:
                        raise ValueError(
                            f"entry_exit {grp_key} condition references undeclared "
                            f"signal '{c.get('signal')}'")


def _step(cur, key):
    """Descend one path segment, supporting list indices ('any.0.value')."""
    return cur[int(key)] if isinstance(cur, list) else cur[key]


def _assign(cur, key, value) -> None:
    if isinstance(cur, list):
        cur[int(key)] = value
    else:
        cur[key] = value


def _set_dotted(d: dict, path: str, value) -> None:
    """Set a dotted path like 'portfolio.k', 'signals.mom90.args.window', or a
    list index like 'portfolio.exit.any.0.value'. The 'signals.<id>' segment
    addresses the signal list by id."""
    parts = path.split(".")
    cur: dict | list = d
    for i, p in enumerate(parts[:-1]):
        if p == "signals":
            cur = next(s for s in d["signals"] if s["id"] == parts[i + 1])
            for q in parts[i + 2:-1]:
                cur = _step(cur, q)
            _assign(cur, parts[-1], value)
            return
        cur = _step(cur, p)
    _assign(cur, parts[-1], value)


def expand_grid(spec: StrategySpec) -> list[StrategySpec]:
    """Cross-product of params_grid -> concrete spec variants (the searched
    space). The base spec's own values are replaced; n_variants = grid size."""
    if not spec.params_grid:
        return [spec]
    keys = list(spec.params_grid)
    out: list[StrategySpec] = []
    for combo in product(*(spec.params_grid[k] for k in keys)):
        d = deepcopy(spec.__dict__)
        d["params_grid"] = {}
        for k, v in zip(keys, combo):
            _set_dotted(d, k, v)
        d["name"] = spec.name + "__" + "_".join(
            f"{k.split('.')[-1]}={v}" for k, v in zip(keys, combo))
        out.append(StrategySpec(**d))
    return out


# ------------------------------------------------------------------------ signals

def sig_ts_momentum(close: pd.DataFrame, *, window: int = 90, **_) -> pd.DataFrame:
    return close.pct_change(window, fill_method=None)


def sig_vol(close: pd.DataFrame, *, window: int = 30, **_) -> pd.DataFrame:
    return close.pct_change(fill_method=None).rolling(window).std()


def sig_rsi(close: pd.DataFrame, *, window: int = 14, **_) -> pd.DataFrame:
    delta = close.diff()
    up = delta.clip(lower=0).rolling(window).mean()
    dn = (-delta.clip(upper=0)).rolling(window).mean()
    rs = up / dn.replace(0.0, np.nan)
    return 100.0 - 100.0 / (1.0 + rs)


def sig_funding_rate(close: pd.DataFrame, *, funding: pd.DataFrame | None = None,
                     window: int = 7, **_) -> pd.DataFrame:
    """Trailing mean DAILY-AGGREGATED funding rate, aligned to the close grid."""
    if funding is None:
        return pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    f = funding.reindex(columns=close.columns)
    return f.rolling(window).mean().reindex(close.index).ffill()


def sig_fear_greed(close: pd.DataFrame, *, fng: pd.Series | None = None, **_) -> pd.Series:
    """Market-wide series broadcast later by the gate."""
    if fng is None:
        return pd.Series(np.nan, index=close.index)
    return fng.reindex(close.index).ffill()


def sig_fng_divergence(close: pd.DataFrame, *, fng: pd.Series | None = None,
                       price_window: int = 30, fng_pivot: float = 50.0,
                       **_) -> pd.DataFrame:
    """CMC-native sentiment-divergence: cross-sectional momentum, SIGN-FLIPPED by
    the Fear & Greed regime. The F&G factor ``(pivot - fng)/50`` is positive in
    fear (play momentum — genuine accumulation against the crowd) and negative in
    greed (go contrarian — fade the late chasers). Because the factor can flip
    sign, F&G genuinely changes which names the top-k book holds — it does NOT
    collapse to plain momentum (a market-wide scalar would).

    Backtestable from CMC Fear & Greed history plus the price panel; no
    look-ahead (trailing momentum, contemporaneous regime, next-bar execution)."""
    if fng is None:
        return pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    mom = close.pct_change(price_window, fill_method=None)
    mu = mom.mean(axis=1)
    sd = mom.std(axis=1).replace(0.0, np.nan)
    momz = mom.sub(mu, axis=0).div(sd, axis=0)              # cross-sectional z
    f = fng.reindex(close.index).ffill()
    factor = (fng_pivot - f) / 50.0                         # +fear / -greed
    return momz.mul(factor, axis=0)


def sig_macd(close: pd.DataFrame, *, fast: int = 12, slow: int = 26,
             signal: int = 9, **_) -> pd.DataFrame:
    """MACD histogram (MACD line − signal line). Sign is the trend trigger:
    > 0 bullish (fast EMA pulling above its signal), < 0 bearish. Scale-free
    threshold rules use ``value: 0.0``."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


def sig_funding_market(close: pd.DataFrame, *, funding: pd.DataFrame | None = None,
                       window: int = 7, **_) -> pd.Series:
    """Market-wide aggregate perp funding (derivatives positioning) — the mean
    daily funding across names, smoothed. A market-wide series the regime gate
    broadcasts, like ``fear_greed``."""
    if funding is None:
        return pd.Series(np.nan, index=close.index)
    f = funding.reindex(columns=close.columns).mean(axis=1)
    return f.rolling(window).mean().reindex(close.index).ffill()


SIGNAL_REGISTRY: dict[str, Callable] = {
    "ts_momentum": sig_ts_momentum,
    "vol": sig_vol,
    "rsi": sig_rsi,
    "funding_rate": sig_funding_rate,
    "fear_greed": sig_fear_greed,
    "fng_divergence": sig_fng_divergence,
    "macd": sig_macd,
    "funding_market": sig_funding_market,
}


# ----------------------------------------------------------------------- compiler

@dataclass
class CompiledStrategy:
    weights: pd.DataFrame                  # price-exposure weights for the engine
    funding_weights: pd.DataFrame | None   # separate funding-leg weights (carry)
    fee_bps: float
    slippage_bps: float


def compile_strategy(
    spec: StrategySpec,
    close: pd.DataFrame,
    *,
    funding: pd.DataFrame | None = None,
    fng: pd.Series | None = None,
) -> CompiledStrategy:
    spec.validate()
    aux = {"funding": funding, "fng": fng}
    computed: dict[str, pd.DataFrame | pd.Series] = {}
    for s in spec.signals:
        fn = SIGNAL_REGISTRY[s["fn"]]
        computed[s["id"]] = fn(close, **{**s.get("args", {}), **aux})

    port = spec.portfolio
    min_hist = int(spec.universe.get("min_history_days", 0))
    valid = close.notna().rolling(max(min_hist, 1)).count() >= max(min_hist, 1)

    if port["type"] == "xs_topk":
        score = computed[port["score"]]
        w = _xs_topk_weights(
            score.where(valid), k=int(port.get("k", 5)),
            direction=port.get("direction", "long"),
            rebalance=port.get("rebalance", "W-MON"),
        )
        gate = port.get("regime_gate")
        if gate:
            g = computed[gate["signal"]]
            ok = (g >= gate.get("min", -np.inf)) & (g <= gate.get("max", np.inf))
            w = w.mul(ok.astype(float), axis=0)
        vt = port.get("vol_target")
        if vt:
            w = _apply_vol_target(w, close, target_ann_vol=float(vt),
                                  lookback=int(port.get("vol_lookback", 20)),
                                  max_leverage=float(port.get("max_leverage", 3.0)))
        return CompiledStrategy(
            weights=w, funding_weights=None,
            fee_bps=float(spec.costs.get("fee_bps", 10.0)),
            slippage_bps=float(spec.costs.get("slippage_bps", 5.0)),
        )

    if port["type"] == "entry_exit":
        entry_b = _group_bool(port["entry"], computed, close) & valid
        exit_b = _group_bool(port["exit"], computed, close)
        # stateful hold: set on entry, reset on exit (exit overrides on a tie)
        held = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
        held = held.mask(entry_b, 1.0).mask(exit_b, 0.0).ffill().fillna(0.0)
        w = _entry_exit_weights(held, max_positions=int(port.get("max_positions", 10)))
        return CompiledStrategy(
            weights=w, funding_weights=None,
            fee_bps=float(spec.costs.get("fee_bps", 10.0)),
            slippage_bps=float(spec.costs.get("slippage_bps", 5.0)),
        )

    if port["type"] == "funding_carry":
        score = computed[port["score"]]
        min_f = float(port.get("min_funding_daily", 0.0))
        sel = _xs_topk_weights(
            score.where(valid).where(score > min_f),
            k=int(port.get("k", 5)), direction="long",
            rebalance=port.get("rebalance", "W-MON"),
        )
        # long spot + short perp on the same names: price legs cancel ->
        # zero price-exposure weights, funding earned on the SHORT perp leg.
        zero = sel * 0.0
        # both legs trade: charge costs twice via doubled bps on the perp leg's
        # turnover (engine charges on |Δweights| of the funding frame too)
        return CompiledStrategy(
            weights=zero, funding_weights=-sel,
            fee_bps=2.0 * float(spec.costs.get("fee_bps", 10.0)),
            slippage_bps=2.0 * float(spec.costs.get("slippage_bps", 5.0)),
        )

    raise ValueError(f"unhandled portfolio type {port['type']}")


def _apply_vol_target(weights: pd.DataFrame, close: pd.DataFrame, *,
                      target_ann_vol: float, lookback: int = 20,
                      max_leverage: float = 3.0,
                      freq: float = 365.0) -> pd.DataFrame:
    """Scale a weight book to a target annualised volatility. Leverage =
    clip(target / realised_book_vol, 0, max), lagged one bar so sizing uses only
    past information (no look-ahead). Delevers in turbulent regimes — the lever
    that turns raw momentum's deep drawdowns into a managed book."""
    rets = close.pct_change(fill_method=None)
    book = (weights.shift(1) * rets).sum(axis=1)
    realised = book.rolling(lookback).std() * np.sqrt(freq)
    lev = (target_ann_vol / realised.replace(0.0, np.nan)).clip(0.0, max_leverage)
    lev = lev.shift(1).fillna(0.0)
    return weights.mul(lev, axis=0)


_OPS = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


def _cond_bool(cond: dict, computed: dict, close: pd.DataFrame) -> pd.DataFrame:
    """Evaluate one {signal, op, value} condition to a T×N boolean panel.
    Market-wide Series signals (e.g. fear_greed) broadcast across all columns."""
    sig = computed[cond["signal"]]
    if isinstance(sig, pd.Series):
        sig = pd.DataFrame({c: sig for c in close.columns})
    sig = sig.reindex(index=close.index, columns=close.columns)
    return _OPS[cond["op"]](sig, cond["value"]).fillna(False)


def _group_bool(group: dict, computed: dict, close: pd.DataFrame) -> pd.DataFrame:
    """Combine a condition group: 'all' = AND, 'any' = OR (elementwise)."""
    if "all" in group:
        conds = [_cond_bool(c, computed, close) for c in group["all"]]
        out = conds[0]
        for c in conds[1:]:
            out = out & c
        return out
    conds = [_cond_bool(c, computed, close) for c in group["any"]]
    out = conds[0]
    for c in conds[1:]:
        out = out | c
    return out


def _entry_exit_weights(held: pd.DataFrame, *, max_positions: int) -> pd.DataFrame:
    """Equal-weight the currently-held set, capped at max_positions per bar
    (deterministic column-order tiebreak), normalised to a long-only book."""
    capped = held.where(held > 0, 0.0)
    cnt = capped.sum(axis=1)
    for t in cnt[cnt > max_positions].index:
        row = capped.loc[t]
        keep = row[row > 0].index[:max_positions]
        capped.loc[t] = 0.0
        capped.loc[t, keep] = 1.0
    denom = capped.sum(axis=1).replace(0.0, np.nan)
    return capped.div(denom, axis=0).fillna(0.0)


def _xs_topk_weights(score: pd.DataFrame, *, k: int, direction: str,
                     rebalance: str) -> pd.DataFrame:
    """Rank cross-sectionally at rebalance dates, equal-weight top k (and short
    bottom k for long_short), forward-fill between rebalances."""
    rebal_dates = pd.Series(1, index=score.index).resample(rebalance).first().index
    rebal_mask = score.index.isin(rebal_dates) if len(rebal_dates) else \
        pd.Series(True, index=score.index)
    w = pd.DataFrame(np.nan, index=score.index, columns=score.columns)
    for t in score.index[rebal_mask]:
        row = score.loc[t].dropna()
        if len(row) < max(2, k):
            w.loc[t] = 0.0
            continue
        top = row.nlargest(k).index
        wt = pd.Series(0.0, index=score.columns)
        wt[top] = 1.0 / k
        if direction == "long_short":
            bot = row.nsmallest(k).index
            wt[bot] -= 1.0 / k
        w.loc[t] = wt
    return w.ffill().fillna(0.0)
