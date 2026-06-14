# Proof of Alpha — reproducible demo

No video needed: everything below reproduces from this public repo, and the
committed artifacts (`demo/output/`) let you see the result without running
anything.

## One-command demo

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
cp .env.example .env                       # add CMC_API_KEY (+ WALLET_PASSWORD for the on-chain step)
.venv/bin/python scripts/fetch_history.py  # ~20 min: Binance history + CMC Fear & Greed
.venv/bin/python demo/run_demo.py          # generate 6 strategies, grade each, build the chart
.venv/bin/pytest                           # 61 tests
```

Output lands in `demo/output/`: a `*_report.md` evidence pack per strategy,
`equity_curves.png`, and `SUMMARY.md`.

## What you get (committed output — viewable on GitHub now)

The Skill **generates** six strategies from CoinMarketCap data and **grades**
each with the effective-N tiered gate. See
[`demo/output/SUMMARY.md`](demo/output/SUMMARY.md) and
[`demo/output/equity_curves.png`](demo/output/equity_curves.png):

- **`xs_momentum` → DEFENSIBLE** — Sharpe **1.37**, CAGR +143%, MDD −65%
  (DSR_eff 0.97 at effN 1.3, PBO 0.11, CPCV-OOS 1.05). **This is the strategy you
  get**: a real, paper-tradeable edge with honest caveats.
  → [`demo/output/xs_momentum_report.md`](demo/output/xs_momentum_report.md)
- **`xs_mom_voltarget` → FAIL** — Sharpe 1.36, MDD **−37%** (vs −65% raw): the
  vol-managed variant nearly halves drawdown, but the gate flags its selection as
  borderline (PBO 0.36 ≈ threshold). An honest near-miss, not dressed up.
- **`momentum_rsi_macd_fng` → FAIL** — RSI + MACD + Fear&Greed **entry/exit
  rules** (organizer example build #1).
- **`sentiment_divergence` → FAIL** — momentum sign-flipped by the F&G regime
  (example build #2).
- **`funding_regime_switch` → FAIL** — perp-funding / derivatives-positioning
  regime (example build #3).
- **`overfit_bait` → FAIL** — the villain: best of 400 random portfolios, killed
  on every condition.

One strategy clears the gate, the rest don't — the grade **discriminates**.
That's the point: you get a strategy *and* the truth about it.

## Try a single strategy / your own idea

```bash
.venv/bin/python skill/scripts/falsify_strategy.py --family xs_momentum --out demo/output
.venv/bin/python skill/scripts/falsify_strategy.py --family momentum_rsi_macd_fng --out demo/output
.venv/bin/python skill/scripts/falsify_strategy.py --spec specs/my_idea.json --out demo/output
```

## On-chain proof

ERC-8004 agent identity registered live on BSC testnet — **agentId 1379**,
gas-free via the MegaFuel paymaster:

- Registration tx: [`0x697ebe…66a0`](https://testnet.bscscan.com/tx/0x697ebe4e9b965d367d7ee2b62fb4cb165dd46c46a6402cb7713f611dfe6566a0)
- Agent wallet: `0xe541340f0372079bEB3aead9379A820EEc09EE81`

The Skill is also an ERC-8183 provider agent: the credibility verdict is the
tradeable on-chain good and the evidence pack's keccak256 is anchored on-chain.
See [`bnbagent_demo/`](bnbagent_demo/README.md).

```bash
.venv/bin/python scripts/register_agent.py                 # ERC-8004 identity (gas-free)
.venv/bin/python bnbagent_demo/erc8183_provider.py \
    --evidence demo/output/xs_momentum_report.json         # anchors the verdict on-chain
```

## Compliance

No token launches, no fundraising, no real capital — the on-chain pieces run on
BSC testnet.
