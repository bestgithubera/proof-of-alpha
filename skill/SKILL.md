---
name: proof-of-alpha
description: >
  Generate crypto trading strategies from CoinMarketCap market data (prices,
  funding rates, Fear & Greed, derivatives positioning) AND falsify them before
  anyone trades them. Every strategy ships as a backtestable JSON spec plus a
  falsification report: deflated Sharpe vs the cumulative trial ledger,
  permutation/bootstrap nulls, PBO/CPCV, cost & capacity stress, regime splits.
  Use whenever a user asks for "a strategy", "is this edge real", "backtest
  this idea", or presents a suspiciously good crypto backtest. The skill REFUSES
  to present a strategy without its falsification verdict.
---

# Proof of Alpha — crypto strategy generation with a credibility grade

Turn CoinMarketCap data into a backtestable crypto trading strategy, and ship it
with an honest grade of how much to trust it. The deliverable is a PAIR: a
strategy spec (`docs/spec-format.md`) and its evidence report. The headline is
the GENERATED strategy and its backtest; the credibility grade (an effective-N
tiered gate: STRONG / DEFENSIBLE / FAIL) is what makes it a strategy you can
actually paper-trade rather than noise. Lead with the strategy and its numbers,
then the grade and caveats.

## Non-negotiable rules

1. **Hypothesis before search.** Write the falsifiable economic mechanism into
   `spec.hypothesis` BEFORE running anything. No mechanism = bait family only.
2. **Declare the whole grid.** Every parameter combination you intend to look at
   goes in `spec.params_grid`. Evaluating configs outside the declared grid and
   not ledgering them is lying to the deflated Sharpe.
3. **The ledger is forever.** `data/trial_ledger.json` accumulates every config
   ever evaluated on this dataset, across sessions. Never reset it, never start
   a "fresh" ledger to make a number pass. The gate reads the cumulative total.
4. **Costs are part of the strategy.** Default 10 bps fee + 5 bps slippage per
   side; carry books pay both legs. Never report gross-only numbers.
5. **Always present the strategy WITH its grade.** Lead with the generated
   strategy and its backtest numbers, then the credibility grade and the caveats
   the report lists. Never ship a strategy with no grade attached.

## Workflow

1. **Understand the request** — which mechanism family fits? Built-ins:
   `xs_momentum` (headline cross-sectional momentum), `xs_mom_voltarget`
   (vol-managed variant — same edge, ~half the drawdown), `momentum_rsi_macd_fng`
   (RSI + MACD + Fear&Greed entry/exit RULES), `funding_regime_switch`
   (derivatives-positioning regime), `sentiment_divergence` (momentum sign-flipped
   by the F&G regime), `funding_carry`, `fng_regime`, and `overfit_bait` (the
   villain, for demos). For a new idea, author a spec JSON per
   `docs/spec-format.md` with an honest grid. Portfolio types: `xs_topk`
   (optional `vol_target`/`regime_gate`), `funding_carry`, `entry_exit` (rules).
2. **Refresh data if stale** (daily bars; skip if cache is current):
   `python scripts/fetch_history.py`
3. **Generate + evaluate + falsify in one step:**
   `python skill/scripts/falsify_strategy.py --family xs_momentum --out demo/output`
   or for a custom spec:
   `python skill/scripts/falsify_strategy.py --spec path/to/spec.json --out demo/output`
4. **Read the report** (`<out>/<name>_report.md`). Present: the generated
   strategy + headline numbers → credibility grade (STRONG/DEFENSIBLE/FAIL) →
   WHY (decision basis) → capacity and cost lines → next steps (paper-trade if
   STRONG/DEFENSIBLE, sized to capacity; archive if FAIL).
5. **Live market context** (optional, CMC-native): pull current Fear & Greed and
   quotes from the CMC API / Agent Hub MCP (`find_skill` / `execute_skill`) to
   note whether TODAY's regime matches the regimes where the strategy earned.

## Interpreting the gate for users

The verdict is tiered and deflated by the **effective number of trials**
(correlation-adjusted) — the right denominator for a small crypto universe where
everything co-moves with BTC; counting every grid variant as independent would
veto every real edge. The nominal-N deflation is kept as a conservative lens.

- **STRONG** — clears all five: effective-N DSR ≥ 0.90, CPCV out-of-sample mean
  Sharpe > 0.5 (and 5th-pct ≥ −0.25), PBO ≤ 0.35, 2x-cost Sharpe > 0.5,
  bootstrap p(Sharpe≤0) ≤ 0.05.
- **DEFENSIBLE** — clears the three selection-bias conditions (effective-N DSR,
  CPCV-OOS, PBO) with a marginal cost/luck check, or a STRONG whose edge is
  concentrated in one Fear&Greed regime. This is the usual "real but caveated"
  PASS tier — paper-trade it, size to capacity.
- **FAIL** — fails the selection-bias core; indistinguishable from the best of
  the noise searched. The report names the failing condition.
- **PBO** — "how often would the in-sample winner be below-median out of
  sample?" ≈0.5 means the search picks noise.
- **Capacity** — the AUM where impact halves the net edge; size below it.

## Files

- `skill/manifest.json` — Agent-Hub-compatible skill manifest (evidence_pack)
- `skill/scripts/falsify_strategy.py` — the one-command pipeline
- `skill/scripts/generate_strategy.py` — emit a family spec JSON to edit
- `validation/` — the falsification toolkit (DSR, PBO/CPCV, nulls, capacity)
- `docs/spec-format.md` — the strategy-spec contract
