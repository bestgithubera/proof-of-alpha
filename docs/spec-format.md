# Strategy-spec format

A **backtestable, falsifiable** JSON document. The Skill emits these; the gate
consumes them. Design rules: (1) the hypothesis is a falsifiable sentence with a
mechanism, not a vibe; (2) `params_grid` declares the FULL searched space, so the
honest trial count feeds the deflated Sharpe — a spec that hides its grid is
lying about its evidence; (3) costs are part of the strategy, not an afterthought.

```json
{
  "name": "xs_momentum_topk",
  "version": 1,
  "hypothesis": "30-90d cross-sectional momentum persists among BNB-ecosystem tokens because attention and listings flows are autocorrelated; it should survive 15 bps/side costs and weekly rebalancing.",
  "universe": {"filter": "tradeable", "min_history_days": 200},
  "bar": "1d",
  "signals": [
    {"id": "mom90", "fn": "ts_momentum", "args": {"window": 90}},
    {"id": "fng",   "fn": "fear_greed",  "args": {}}
  ],
  "portfolio": {
    "type": "xs_topk",
    "score": "mom90",
    "k": 5,
    "direction": "long",
    "weighting": "equal",
    "rebalance": "W-MON",
    "regime_gate": {"signal": "fng", "min": 20, "max": 100}
  },
  "costs": {"fee_bps": 10, "slippage_bps": 5},
  "params_grid": {
    "signals.mom90.args.window": [30, 60, 90],
    "portfolio.k": [3, 5, 10]
  },
  "falsification": {"min_dsr": 0.95, "n_trials_policy": "cumulative_ledger"}
}
```

## Fields

- `hypothesis` — one falsifiable sentence: mechanism + what would refute it.
- `universe.filter` — `tradeable` (eligible ∩ Binance spot, ex-stables) is the
  only filter today; `min_history_days` drops young listings at each rebalance.
- `bar` — `1d` or `4h` (sets the annualisation calendar downstream).
- `signals` — DAG of registered signal functions, each producing a panel
  (time × asset) or a market-wide series. Registry: `ts_momentum`, `xs_rank`,
  `rsi`, `vol`, `funding_rate`, `fear_greed`.
- `portfolio.type`:
  - `xs_topk` — rank assets by `score` each `rebalance`, hold top-k
    (`direction: long`) or top-k minus bottom-k (`long_short`), equal or
    rank-weighted; optional `regime_gate` zeroes the book when a market-wide
    signal leaves `[min, max]`.
  - `funding_carry` — market-neutral: long spot / short perp on the k names with
    the highest trailing funding (`score` = `funding_rate` signal). Price legs
    cancel; the book earns funding. Costs are charged on BOTH legs (fee and
    slippage doubled by the compiler).
- `costs` — per-side bps; the engine charges them on turnover at execution.
- `params_grid` — dotted-path → list of values. The cross-product defines the
  searched space; EVERY evaluated cell is recorded in the trial ledger.
- `falsification` — gate thresholds; `n_trials_policy: cumulative_ledger` means
  the DSR uses the ledger's lifetime total, not just this grid.

## Execution semantics (engine contract)

Weights decided at bar t close execute at bar t+1 (no look-ahead, pinned by
tests). Rebalance dates between grid points forward-fill. Young assets
(< `min_history_days`) are excluded from ranking on that date.
