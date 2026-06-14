# Proof of Alpha — falsification report: `funding_carry`
*Generated 2026-06-13 06:20 UTC*

## ❌ FAIL — likely noise

**Summary.** Best variant `funding_carry__window=14_k=8_min_funding_daily=0.0` from a declared grid of 18 configs: Sharpe 0.83, CAGR +1.4%, MDD -4.1% over 3.0y. Verdict: **FAIL** — DSR 0.21 < 0.95 at cumulative N=38 (selection bar sr0=1.33 ann).

**Hypothesis under test.** Perp funding paid by levered longs is a persistent risk premium: a hedged short-perp/long-spot book on the highest-funding names earns it net of double-leg costs; refuted if net Sharpe dies under deflation or cost stress.

## Report

### 1. Selection-bias deflation (Bailey & López de Prado)
- Cumulative trials ever run on this dataset: **38** (persistent ledger — every config ever evaluated counts)
- PSR P(SR>0): 0.912; **DSR: 0.208** vs required ≥ 0.95
- Selection bar: the best of 38 noise strategies is expected to show Sharpe ≈ 1.33 — the candidate must beat THAT
- Result: FAIL

### 2. Second school: FDR / effective-N / Bayes (triangulation)
- Skew/kurtosis-aware t-stat 1.36 vs HLZ hurdle 3.0: fail
- Effective independent trials (correlation-adjusted): 1.4; DSR at effective-N: 0.798 (fail)
- Bayesian posterior Sharpe 0.63, P(SR>0)=0.949 (fail)
- Alt-school verdict: **0/3 = FAIL**

### 3. Luck null (block bootstrap)
- Sharpe 0.83 ± 0.80 (95% CI [-0.57, 2.49])
- P(Sharpe ≤ 0 under resampling): 0.154

### 4. Did the SEARCH overfit? (PBO / CPCV / MinBTL)
- PBO: **0.00** (≈0.5 = picking on noise; ≤0.2 healthy)
- CPCV out-of-sample Sharpe of the would-be-selected variant: mean 0.77, 5th pct -2.04, selection haircut 0.28
- Minimum backtest length for N=38: 6.8y vs available 3.0y (NOT ENOUGH DATA)

### 5. Cost & capacity stress
- Sharpe at 1x / 2x / 4x costs: 0.83 / -2.33 / -4.07
- Median ADV of held names: $3,196,540; annual turnover 27.1x
- Capacity (net return holds ≥ half small-size net): **$0**

### 6. Regime robustness
- Sharpe by sub-period: [0.0, 6.45, -1.52, -1.86, 0.73, 0.27] (stable: False)
- Decay slope: -0.46 per period (first half 1.64 → second half -0.29)
- Sharpe by Fear & Greed quartile: fear: -1.23, mid-fear: -0.10, mid-greed: -1.71, greed: 5.63

## Decision basis
- DSR 0.21 < 0.95 at cumulative N=38 (selection bar sr0=1.33 ann)
- edge dies at 2x costs
- history 3.0y < MinBTL 6.8y for N=38

## Insights
- A FAIL does not mean the mechanism is false — it means THIS evidence does not distinguish the strategy from the best of the noise searched.

## Live CMC regime context
- Fear & Greed now: **19 (Extreme fear)** — source: cmc-rest
- Compare to the Fear & Greed quartile where this strategy earned (section 6). If today's regime is far from it, size down.

*Freshness: backtest data ends at the last cached bar; re-run `scripts/fetch_history.py` and the gate for a current verdict.*