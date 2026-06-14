# Proof of Alpha — falsification report: `momentum_rsi_macd_fng`
*Generated 2026-06-13 07:02 UTC*

## ❌ FAIL — indistinguishable from noise

**Summary.** Best variant `momentum_rsi_macd_fng__window=21_value=80_value=75` from a declared grid of 18 configs: Sharpe 0.65, CAGR +23.9%, MDD -57.2% over 3.0y. Verdict: **FAIL** — fails the effective-N selection gate (effective-N DSR >= 0.90; CPCV OOS mean > 0.5 & p5 >= -0.25; 2x-cost Sharpe > 0.5; bootstrap p(Sharpe<=0) <= 0.05).

**Hypothesis under test.** A long book that ENTERS tokens when MACD turns up (histogram > 0) and the market is not greedy (Fear & Greed <= 65), and EXITS on RSI overbought (> 70) or MACD rolling over, harvests trend while sidestepping late-greed reversals. Refuted if it does not beat buy-and-hold net of costs after trial deflation.

## Report

### 1. Selection-bias deflation (Bailey & López de Prado)
- Cumulative trials ever run on this dataset: **58** (persistent ledger — every config ever evaluated counts)
- PSR P(SR>0): 0.874; **DSR: 0.117** vs required ≥ 0.95
- Selection bar: the best of 58 noise strategies is expected to show Sharpe ≈ 1.32 — the candidate must beat THAT
- Result: FAIL

### 2. Second school: FDR / effective-N / Bayes (triangulation)
- Skew/kurtosis-aware t-stat 1.14 vs HLZ hurdle 3.0: fail
- Effective independent trials (correlation-adjusted): 1.3; DSR at effective-N: 0.734 (fail)
- Bayesian posterior Sharpe 0.57, P(SR>0)=0.934 (fail)
- Alt-school verdict: **0/3 = FAIL**

### 3. Luck null (block bootstrap)
- Sharpe 0.65 ± 0.53 (95% CI [-0.38, 1.68])
- P(Sharpe ≤ 0 under resampling): 0.114

### 4. Did the SEARCH overfit? (PBO / CPCV / MinBTL)
- PBO: **0.27** (≈0.5 = picking on noise; ≤0.2 healthy)
- CPCV out-of-sample Sharpe of the would-be-selected variant: mean 0.36, 5th pct -0.63, selection haircut 0.39
- Minimum backtest length for N=58: 12.9y vs available 3.0y (NOT ENOUGH DATA)

### 5. Cost & capacity stress
- Sharpe at 1x / 2x / 4x costs: 0.65 / 0.40 / -0.11
- Median ADV of held names: $2,976,234; annual turnover 120.0x
- Capacity (net return holds ≥ half small-size net): **$0**

### 6. Regime robustness
- Sharpe by sub-period: [0.0, 1.01, 1.33, 0.04, 1.1, 0.09] (stable: True)
- Decay slope: -0.02 per period (first half 0.78 → second half 0.41)
- Sharpe by Fear & Greed quartile: fear: 1.03, mid-fear: 0.01, mid-greed: 0.35, greed: 1.18

## Decision basis
- fails the effective-N selection gate (effective-N DSR >= 0.90; CPCV OOS mean > 0.5 & p5 >= -0.25; 2x-cost Sharpe > 0.5; bootstrap p(Sharpe<=0) <= 0.05)
- effective-N DSR 0.73 at effN 1.3; CPCV OOS mean 0.36; PBO 0.27
- conservative nominal-N lens (assumes independent trials): DSR 0.12 vs 0.95 at N=58 — a lower bound for a correlated universe, not the verdict

## Insights
- A FAIL does not mean the mechanism is false — it means THIS evidence does not distinguish the strategy from the best of the noise searched.

## Live CMC regime context
- Fear & Greed now: **19 (Extreme fear)** — source: cmc-rest
- Compare to the Fear & Greed quartile where this strategy earned (section 6). If today's regime is far from it, size down.

*Freshness: backtest data ends at the last cached bar; re-run `scripts/fetch_history.py` and the gate for a current verdict.*