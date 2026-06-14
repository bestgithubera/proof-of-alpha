# Proof of Alpha — falsification report: `funding_regime_switch`
*Generated 2026-06-13 07:02 UTC*

## ❌ FAIL — indistinguishable from noise

**Summary.** Best variant `funding_regime_switch__window=60_k=5_max=5e-05` from a declared grid of 18 configs: Sharpe 1.37, CAGR +85.4%, MDD -45.2% over 3.0y. Verdict: **FAIL** — fails the effective-N selection gate (PBO <= 0.35).

**Hypothesis under test.** Aggregate perp funding measures crowd leverage/positioning: when market-wide funding is rich (longs crowded) the tape is froth-prone, so stand aside; run cross-sectional momentum only when funding is neutral/negative. Refuted if the funding-gated book does not beat the ungated one after deflation.

## Report

### 1. Selection-bias deflation (Bailey & López de Prado)
- Cumulative trials ever run on this dataset: **103** (persistent ledger — every config ever evaluated counts)
- PSR P(SR>0): 0.992; **DSR: 0.452** vs required ≥ 0.95
- Selection bar: the best of 103 noise strategies is expected to show Sharpe ≈ 1.44 — the candidate must beat THAT
- Result: FAIL

### 2. Second school: FDR / effective-N / Bayes (triangulation)
- Skew/kurtosis-aware t-stat 2.42 vs HLZ hurdle 3.0: fail
- Effective independent trials (correlation-adjusted): 1.4; DSR at effective-N: 0.971 (pass)
- Bayesian posterior Sharpe 0.88, P(SR>0)=0.991 (pass)
- Alt-school verdict: **2/3 = DEFENSIBLE**

### 3. Luck null (block bootstrap)
- Sharpe 1.37 ± 0.54 (95% CI [0.37, 2.38])
- P(Sharpe ≤ 0 under resampling): 0.008

### 4. Did the SEARCH overfit? (PBO / CPCV / MinBTL)
- PBO: **0.37** (≈0.5 = picking on noise; ≤0.2 healthy)
- CPCV out-of-sample Sharpe of the would-be-selected variant: mean 1.03, 5th pct 0.06, selection haircut 0.45
- Minimum backtest length for N=103: 3.4y vs available 3.0y (NOT ENOUGH DATA)

### 5. Cost & capacity stress
- Sharpe at 1x / 2x / 4x costs: 1.37 / 1.32 / 1.21
- Median ADV of held names: $3,963,610; annual turnover 19.9x
- Capacity (net return holds ≥ half small-size net): **$1,000,000**

### 6. Regime robustness
- Sharpe by sub-period: [0.0, -1.53, 2.08, 0.18, 1.3, 3.7] (stable: False)
- Decay slope: 0.72 per period (first half 0.18 → second half 1.73)
- Sharpe by Fear & Greed quartile: fear: 1.38, mid-fear: 2.12, mid-greed: 1.31, greed: -0.10

## Decision basis
- fails the effective-N selection gate (PBO <= 0.35)
- effective-N DSR 0.97 at effN 1.4; CPCV OOS mean 1.03; PBO 0.37
- conservative nominal-N lens (assumes independent trials): DSR 0.45 vs 0.95 at N=103 — a lower bound for a correlated universe, not the verdict

## Insights
- The two schools DISAGREE: nominal-N deflation kills it, but the FDR/effective-N school finds it defensible. This is the honest grey zone — the difference is entirely the multiple-testing philosophy, and the only arbiter left is live out-of-sample track record.
- A FAIL does not mean the mechanism is false — it means THIS evidence does not distinguish the strategy from the best of the noise searched.

## Live CMC regime context
- Fear & Greed now: **19 (Extreme fear)** — source: cmc-rest
- Compare to the Fear & Greed quartile where this strategy earned (section 6). If today's regime is far from it, size down.

*Freshness: backtest data ends at the last cached bar; re-run `scripts/fetch_history.py` and the gate for a current verdict.*