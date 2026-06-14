# Proof of Alpha — falsification report: `xs_mom_voltarget`
*Generated 2026-06-13 07:02 UTC*

## ❌ FAIL — indistinguishable from noise

**Summary.** Best variant `xs_mom_voltarget__window=14_k=3` from a declared grid of 20 configs: Sharpe 1.36, CAGR +64.0%, MDD -36.5% over 3.0y. Verdict: **FAIL** — fails the effective-N selection gate (PBO <= 0.35).

**Hypothesis under test.** Cross-sectional momentum among BNB-ecosystem tokens persists via attention/flow autocorrelation; a ~40%-annual-vol target delevers in turbulence to cap crash beta. Refuted if the managed book does not stay positive out-of-sample after cost stress and trial deflation.

## Report

### 1. Selection-bias deflation (Bailey & López de Prado)
- Cumulative trials ever run on this dataset: **40** (persistent ledger — every config ever evaluated counts)
- PSR P(SR>0): 0.993; **DSR: 0.600** vs required ≥ 0.95
- Selection bar: the best of 40 noise strategies is expected to show Sharpe ≈ 1.22 — the candidate must beat THAT
- Result: FAIL

### 2. Second school: FDR / effective-N / Bayes (triangulation)
- Skew/kurtosis-aware t-stat 2.44 vs HLZ hurdle 3.0: fail
- Effective independent trials (correlation-adjusted): 1.4; DSR at effective-N: 0.973 (pass)
- Bayesian posterior Sharpe 0.88, P(SR>0)=0.991 (pass)
- Alt-school verdict: **2/3 = DEFENSIBLE**

### 3. Luck null (block bootstrap)
- Sharpe 1.36 ± 0.57 (95% CI [0.20, 2.46])
- P(Sharpe ≤ 0 under resampling): 0.006

### 4. Did the SEARCH overfit? (PBO / CPCV / MinBTL)
- PBO: **0.36** (≈0.5 = picking on noise; ≤0.2 healthy)
- CPCV out-of-sample Sharpe of the would-be-selected variant: mean 0.87, 5th pct -0.24, selection haircut 0.65
- Minimum backtest length for N=40: 2.6y vs available 3.0y (ok)

### 5. Cost & capacity stress
- Sharpe at 1x / 2x / 4x costs: 1.36 / 1.26 / 1.07
- Median ADV of held names: $2,677,905; annual turnover 27.9x
- Capacity (net return holds ≥ half small-size net): **$100,000**

### 6. Regime robustness
- Sharpe by sub-period: [0.0, 1.4, 1.04, -0.19, 1.4, 3.54] (stable: False)
- Decay slope: 0.47 per period (first half 0.81 → second half 1.58)
- Sharpe by Fear & Greed quartile: fear: 2.30, mid-fear: 1.25, mid-greed: 1.05, greed: 0.78

## Decision basis
- fails the effective-N selection gate (PBO <= 0.35)
- effective-N DSR 0.97 at effN 1.4; CPCV OOS mean 0.87; PBO 0.36
- conservative nominal-N lens (assumes independent trials): DSR 0.60 vs 0.95 at N=40 — a lower bound for a correlated universe, not the verdict

## Insights
- The two schools DISAGREE: nominal-N deflation kills it, but the FDR/effective-N school finds it defensible. This is the honest grey zone — the difference is entirely the multiple-testing philosophy, and the only arbiter left is live out-of-sample track record.
- A FAIL does not mean the mechanism is false — it means THIS evidence does not distinguish the strategy from the best of the noise searched.

## Live CMC regime context
- Fear & Greed now: **19 (Extreme fear)** — source: cmc-rest
- Compare to the Fear & Greed quartile where this strategy earned (section 6). If today's regime is far from it, size down.

*Freshness: backtest data ends at the last cached bar; re-run `scripts/fetch_history.py` and the gate for a current verdict.*