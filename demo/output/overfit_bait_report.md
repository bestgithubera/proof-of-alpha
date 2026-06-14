# Proof of Alpha — falsification report: `overfit_bait`
*Generated 2026-06-13 07:02 UTC*

## ❌ FAIL — indistinguishable from noise

**Summary.** Best variant `overfit_bait__seed=273` from a declared grid of 400 configs: Sharpe 0.85, CAGR +43.1%, MDD -60.1% over 1.48y. Verdict: **FAIL** — fails the effective-N selection gate (effective-N DSR >= 0.90; CPCV OOS mean > 0.5 & p5 >= -0.25; PBO <= 0.35; 2x-cost Sharpe > 0.5; bootstrap p(Sharpe<=0) <= 0.05).

**Hypothesis under test.** NONE — this is deliberately the best of many random portfolios on a short window. It exists to show that a clean engine plus a great in-sample Sharpe proves nothing; the gate must kill it.

## Report

### 1. Selection-bias deflation (Bailey & López de Prado)
- Cumulative trials ever run on this dataset: **503** (persistent ledger — every config ever evaluated counts)
- PSR P(SR>0): 0.850; **DSR: 0.022** vs required ≥ 0.95
- Selection bar: the best of 503 noise strategies is expected to show Sharpe ≈ 2.49 — the candidate must beat THAT
- Result: FAIL

### 2. Second school: FDR / effective-N / Bayes (triangulation)
- Skew/kurtosis-aware t-stat 1.04 vs HLZ hurdle 3.0: fail
- Effective independent trials (correlation-adjusted): 2.4; DSR at effective-N: 0.698 (fail)
- Bayesian posterior Sharpe 0.59, P(SR>0)=0.919 (fail)
- Alt-school verdict: **0/3 = FAIL**

### 3. Luck null (block bootstrap)
- Sharpe 0.85 ± 0.82 (95% CI [-0.69, 2.48])
- P(Sharpe ≤ 0 under resampling): 0.136

### 4. Did the SEARCH overfit? (PBO / CPCV / MinBTL)
- PBO: **0.50** (≈0.5 = picking on noise; ≤0.2 healthy)
- CPCV out-of-sample Sharpe of the would-be-selected variant: mean -0.63, 5th pct -2.05, selection haircut 2.26
- Minimum backtest length for N=503: 13.0y vs available 1.5y (NOT ENOUGH DATA)

### 5. Cost & capacity stress
- Sharpe at 1x / 2x / 4x costs: 0.85 / 0.25 / -0.15
- Median ADV of held names: $2,976,234; annual turnover 82.3x
- Capacity (net return holds ≥ half small-size net): **$0**

### 6. Regime robustness
- Sharpe by sub-period: [-0.91, 2.09, 1.76, -0.59, 0.62, 2.76] (stable: False)
- Decay slope: 0.33 per period (first half 0.98 → second half 0.93)
- Sharpe by Fear & Greed quartile: fear: 0.66, mid-fear: 0.67, mid-greed: 0.24, greed: 1.78

## Decision basis
- fails the effective-N selection gate (effective-N DSR >= 0.90; CPCV OOS mean > 0.5 & p5 >= -0.25; PBO <= 0.35; 2x-cost Sharpe > 0.5; bootstrap p(Sharpe<=0) <= 0.05)
- effective-N DSR 0.70 at effN 2.4; CPCV OOS mean -0.63; PBO 0.50
- conservative nominal-N lens (assumes independent trials): DSR 0.02 vs 0.95 at N=503 — a lower bound for a correlated universe, not the verdict

## Insights
- A FAIL does not mean the mechanism is false — it means THIS evidence does not distinguish the strategy from the best of the noise searched.

## Live CMC regime context
- Fear & Greed now: **19 (Extreme fear)** — source: cmc-rest
- Compare to the Fear & Greed quartile where this strategy earned (section 6). If today's regime is far from it, size down.

*Freshness: backtest data ends at the last cached bar; re-run `scripts/fetch_history.py` and the gate for a current verdict.*