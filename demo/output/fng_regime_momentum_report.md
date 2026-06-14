# Proof of Alpha — falsification report: `fng_regime_momentum`
*Generated 2026-06-13 06:20 UTC*

## ❌ FAIL — likely noise

**Summary.** Best variant `fng_regime_momentum__window=30_k=5_min=15` from a declared grid of 24 configs: Sharpe 0.78, CAGR +35.7%, MDD -66.9% over 3.0y. Verdict: **FAIL** — DSR 0.16 < 0.95 at cumulative N=62 (selection bar sr0=1.35 ann).

**Hypothesis under test.** Momentum among BNB-ecosystem tokens pays only in non-fear regimes; gating the book on the Fear & Greed index avoids crash beta. Refuted if the gated book does not beat the ungated one after deflation for the threshold search.

## Report

### 1. Selection-bias deflation (Bailey & López de Prado)
- Cumulative trials ever run on this dataset: **62** (persistent ledger — every config ever evaluated counts)
- PSR P(SR>0): 0.913; **DSR: 0.159** vs required ≥ 0.95
- Selection bar: the best of 62 noise strategies is expected to show Sharpe ≈ 1.35 — the candidate must beat THAT
- Result: FAIL

### 2. Second school: FDR / effective-N / Bayes (triangulation)
- Skew/kurtosis-aware t-stat 1.36 vs HLZ hurdle 3.0: fail
- Effective independent trials (correlation-adjusted): 1.3; DSR at effective-N: 0.799 (fail)
- Bayesian posterior Sharpe 0.62, P(SR>0)=0.950 (pass)
- Alt-school verdict: **1/3 = WEAK**

### 3. Luck null (block bootstrap)
- Sharpe 0.78 ± 0.57 (95% CI [-0.35, 1.84])
- P(Sharpe ≤ 0 under resampling): 0.082

### 4. Did the SEARCH overfit? (PBO / CPCV / MinBTL)
- PBO: **0.44** (≈0.5 = picking on noise; ≤0.2 healthy)
- CPCV out-of-sample Sharpe of the would-be-selected variant: mean 0.37, 5th pct -0.61, selection haircut 0.64
- Minimum backtest length for N=62: 9.2y vs available 3.0y (NOT ENOUGH DATA)

### 5. Cost & capacity stress
- Sharpe at 1x / 2x / 4x costs: 0.78 / 0.71 / 0.57
- Median ADV of held names: $2,755,927; annual turnover 35.9x
- Capacity (net return holds ≥ half small-size net): **$10,000**

### 6. Regime robustness
- Sharpe by sub-period: [0.0, 1.12, 1.88, -1.6, 0.54, 2.62] (stable: False)
- Decay slope: 0.23 per period (first half 1.00 → second half 0.52)
- Sharpe by Fear & Greed quartile: fear: 0.56, mid-fear: 1.53, mid-greed: 0.75, greed: 0.34

## Decision basis
- DSR 0.16 < 0.95 at cumulative N=62 (selection bar sr0=1.35 ann)
- history 3.0y < MinBTL 9.2y for N=62

## Insights
- A FAIL does not mean the mechanism is false — it means THIS evidence does not distinguish the strategy from the best of the noise searched.

## Live CMC regime context
- Fear & Greed now: **19 (Extreme fear)** — source: cmc-rest
- Compare to the Fear & Greed quartile where this strategy earned (section 6). If today's regime is far from it, size down.

*Freshness: backtest data ends at the last cached bar; re-run `scripts/fetch_history.py` and the gate for a current verdict.*