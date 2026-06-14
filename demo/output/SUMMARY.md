# Proof of Alpha — demo verdicts

- **xs_momentum** → **DEFENSIBLE** — DEFENSIBLE: clears the effective-N selection gate (DSR_eff 0.97 at effN 1.3, PBO 0.11, CPCV OOS mean 1.05) (alt-school: DEFENSIBLE)
- **xs_mom_voltarget** → **FAIL** — fails the effective-N selection gate (PBO <= 0.35) (alt-school: DEFENSIBLE)
- **momentum_rsi_macd_fng** → **FAIL** — fails the effective-N selection gate (effective-N DSR >= 0.90; CPCV OOS mean > 0.5 & p5 >= -0.25; 2x-cost Sharpe > 0.5; bootstrap p(Sharpe<=0) <= 0.05) (alt-school: FAIL)
- **sentiment_divergence** → **FAIL** — fails the effective-N selection gate (CPCV OOS mean > 0.5 & p5 >= -0.25) (alt-school: WEAK)
- **funding_regime_switch** → **FAIL** — fails the effective-N selection gate (PBO <= 0.35) (alt-school: DEFENSIBLE)
- **overfit_bait** → **FAIL** — fails the effective-N selection gate (effective-N DSR >= 0.90; CPCV OOS mean > 0.5 & p5 >= -0.25; PBO <= 0.35; 2x-cost Sharpe > 0.5; bootstrap p(Sharpe<=0) <= 0.05) (alt-school: FAIL)

## On-chain proof (BNB AI Agent SDK)
- ERC-8004 identity: agentId 1379 (BSC testnet)
- evidence keccak256: `f3c68405f338ec68677bb5a9ee074581c76454234cefc7ef48fab603dc2d9f18`
- ERC-8183 escrow loop: needs_funding (awaits testnet faucet funding)
