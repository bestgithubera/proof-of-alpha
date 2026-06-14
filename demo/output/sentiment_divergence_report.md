# Proof of Alpha — falsification report: `sentiment_divergence`
*Generated 2026-06-13 07:02 UTC*

## ❌ FAIL — indistinguishable from noise

**Summary.** Best variant `sentiment_divergence__price_window=14_fng_pivot=60.0_k=3` from a declared grid of 27 configs: Sharpe 1.03, CAGR +71.1%, MDD -77.0% over 3.0y. Verdict: **FAIL** — fails the effective-N selection gate (CPCV OOS mean > 0.5 & p5 >= -0.25).

**Hypothesis under test.** Cross-sectional momentum pays in FEAR (genuine accumulation against the crowd) but reverses in GREED (late chasers unwind); a book that plays momentum in fear and goes contrarian in greed earns the divergence. Refuted if it does not beat plain momentum after cost stress and trial deflation.

## Report

### 1. Selection-bias deflation (Bailey & López de Prado)
- Cumulative trials ever run on this dataset: **85** (persistent ledger — every config ever evaluated counts)
- PSR P(SR>0): 0.966; **DSR: 0.259** vs required ≥ 0.95
- Selection bar: the best of 85 noise strategies is expected to show Sharpe ≈ 1.39 — the candidate must beat THAT
- Result: FAIL

### 2. Second school: FDR / effective-N / Bayes (triangulation)
- Skew/kurtosis-aware t-stat 1.83 vs HLZ hurdle 3.0: fail
- Effective independent trials (correlation-adjusted): 1.4; DSR at effective-N: 0.904 (fail)
- Bayesian posterior Sharpe 0.73, P(SR>0)=0.975 (pass)
- Alt-school verdict: **1/3 = WEAK**

### 3. Luck null (block bootstrap)
- Sharpe 1.03 ± 0.57 (95% CI [-0.01, 2.15])
- P(Sharpe ≤ 0 under resampling): 0.030

### 4. Did the SEARCH overfit? (PBO / CPCV / MinBTL)
- PBO: **0.24** (≈0.5 = picking on noise; ≤0.2 healthy)
- CPCV out-of-sample Sharpe of the would-be-selected variant: mean 0.52, 5th pct -0.63, selection haircut 0.67
- Minimum backtest length for N=85: 5.8y vs available 3.0y (NOT ENOUGH DATA)

### 5. Cost & capacity stress
- Sharpe at 1x / 2x / 4x costs: 1.03 / 0.94 / 0.75
- Median ADV of held names: $2,755,927; annual turnover 57.2x
- Capacity (net return holds ≥ half small-size net): **$10,000**

### 6. Regime robustness
- Sharpe by sub-period: [0.0, -0.08, 0.43, -0.9, 1.81, 3.46] (stable: False)
- Decay slope: 0.62 per period (first half 0.12 → second half 1.45)
- Sharpe by Fear & Greed quartile: fear: 1.98, mid-fear: 1.55, mid-greed: 0.66, greed: -0.71

## Decision basis
- fails the effective-N selection gate (CPCV OOS mean > 0.5 & p5 >= -0.25)
- effective-N DSR 0.90 at effN 1.4; CPCV OOS mean 0.52; PBO 0.24
- conservative nominal-N lens (assumes independent trials): DSR 0.26 vs 0.95 at N=85 — a lower bound for a correlated universe, not the verdict

## Insights
- A FAIL does not mean the mechanism is false — it means THIS evidence does not distinguish the strategy from the best of the noise searched.

## Live CMC regime context
- Fear & Greed now: **19 (Extreme fear)** — source: cmc-rest
- Compare to the Fear & Greed quartile where this strategy earned (section 6). If today's regime is far from it, size down.

*Freshness: backtest data ends at the last cached bar; re-run `scripts/fetch_history.py` and the gate for a current verdict.*