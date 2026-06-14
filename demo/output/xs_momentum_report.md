# Proof of Alpha — falsification report: `xs_momentum`
*Generated 2026-06-13 07:01 UTC*

## 🟡 DEFENSIBLE — a real but caveated edge

**Summary.** Best variant `xs_momentum__window=14_k=3` from a declared grid of 20 configs: Sharpe 1.37, CAGR +142.9%, MDD -64.8% over 3.0y. Verdict: **DEFENSIBLE** — DEFENSIBLE: clears the effective-N selection gate (DSR_eff 0.97 at effN 1.3, PBO 0.11, CPCV OOS mean 1.05).

**Hypothesis under test.** Cross-sectional 14-120d momentum persists among BNB-ecosystem tokens because attention, listing and flow shocks are autocorrelated; refuted if the edge does not survive cost stress and trial deflation.

## Report

### 1. Selection-bias deflation (Bailey & López de Prado)
- Cumulative trials ever run on this dataset: **20** (persistent ledger — every config ever evaluated counts)
- PSR P(SR>0): 0.993; **DSR: 0.713** vs required ≥ 0.95
- Selection bar: the best of 20 noise strategies is expected to show Sharpe ≈ 1.06 — the candidate must beat THAT
- Result: FAIL

### 2. Second school: FDR / effective-N / Bayes (triangulation)
- Skew/kurtosis-aware t-stat 2.46 vs HLZ hurdle 3.0: fail
- Effective independent trials (correlation-adjusted): 1.3; DSR at effective-N: 0.974 (pass)
- Bayesian posterior Sharpe 0.89, P(SR>0)=0.992 (pass)
- Alt-school verdict: **2/3 = DEFENSIBLE**

### 3. Luck null (block bootstrap)
- Sharpe 1.37 ± 0.55 (95% CI [0.26, 2.47])
- P(Sharpe ≤ 0 under resampling): 0.008

### 4. Did the SEARCH overfit? (PBO / CPCV / MinBTL)
- PBO: **0.11** (≈0.5 = picking on noise; ≤0.2 healthy)
- CPCV out-of-sample Sharpe of the would-be-selected variant: mean 1.05, 5th pct -0.01, selection haircut 0.40
- Minimum backtest length for N=20: 1.9y vs available 3.0y (ok)

### 5. Cost & capacity stress
- Sharpe at 1x / 2x / 4x costs: 1.37 / 1.30 / 1.15
- Median ADV of held names: $2,677,905; annual turnover 48.6x
- Capacity (net return holds ≥ half small-size net): **$100,000**

### 6. Regime robustness
- Sharpe by sub-period: [0.0, 0.77, 1.72, -0.38, 1.61, 3.46] (stable: False)
- Decay slope: 0.51 per period (first half 0.83 → second half 1.56)
- Sharpe by Fear & Greed quartile: fear: 2.05, mid-fear: 1.62, mid-greed: 1.15, greed: 0.49

## Decision basis
- DEFENSIBLE: clears the effective-N selection gate (DSR_eff 0.97 at effN 1.3, PBO 0.11, CPCV OOS mean 1.05)
- downgraded STRONG->DEFENSIBLE: edge is regime-concentrated or unstable across sub-periods
- conservative nominal-N lens (assumes independent trials): DSR 0.71 vs 0.95 at N=20 — a lower bound for a correlated universe, not the verdict

## Insights
- DEFENSIBLE means it cleared the effective-N gate (deflated for a correlated crypto universe), not guaranteed-alpha: paper-trade before capital, size to the capacity figure, monitor decay.

## Live CMC regime context
- Fear & Greed now: **19 (Extreme fear)** — source: cmc-rest
- Compare to the Fear & Greed quartile where this strategy earned (section 6). If today's regime is far from it, size down.

*Freshness: backtest data ends at the last cached bar; re-run `scripts/fetch_history.py` and the gate for a current verdict.*