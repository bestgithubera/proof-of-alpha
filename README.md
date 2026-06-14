# Proof of Alpha

Generate a crypto strategy from market data (prices, perp funding, Fear & Greed),
backtest it net of costs, and run it through an anti-overfitting validation gate
that deflates the in-sample Sharpe and discriminates real edges from noise.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
cp .env.example .env                      # CMC_API_KEY (+ WALLET_PASSWORD for on-chain)
.venv/bin/python scripts/fetch_history.py # ~20 min: Binance history + Fear & Greed
.venv/bin/python demo/run_demo.py         # generate + grade the curated set
.venv/bin/pytest
```

Single strategy / custom spec:

```bash
.venv/bin/python skill/scripts/falsify_strategy.py --family xs_momentum --out demo/output
.venv/bin/python skill/scripts/falsify_strategy.py --spec specs/my_idea.json --out demo/output
```

On-chain identity + commerce demo (testnet, no real capital):

```bash
.venv/bin/python scripts/register_agent.py
.venv/bin/python bnbagent_demo/erc8183_provider.py --evidence demo/output/xs_momentum_report.json
```

Reproducible demo and committed outputs: [DEMO.md](DEMO.md).

## How it works

Each strategy ships as a pair: a backtestable spec (JSON — hypothesis, signals,
rules, costs, and the full searched parameter grid; see `docs/spec-format.md`)
and an evidence report with a credibility grade.

The grade deflates the in-sample Sharpe by the **correlation-adjusted effective
number of trials** (the eligible universe is small and co-moves), then stacks
PBO/CSCV, combinatorial-purged cross-validation, cost stress and a capacity
curve. Tiers: **STRONG / DEFENSIBLE / FAIL** — the nominal-N deflated Sharpe is
kept as a conservative lens, not the verdict.

Two portfolio shapes: cross-sectional ranking (`xs_topk`, optional
volatility-targeting / regime gates) and threshold entry/exit rules
(`entry_exit`).

## Architecture

- `skill/` — `SKILL.md`, `manifest.json` (`resultType: evidence_pack`), CLI
  scripts incl. `regime_context.py` (live regime overlay)
- `strategies/` — spec format + compiler (`spec.py`); families + ledgered
  evaluator (`families.py`)
- `validation/` — `core.py` (effective-N, CPCV, PBO/CSCV, bootstrap nulls,
  capacity, decay, stability, DSR), `alt.py` (FDR / effective-N / Bayes),
  `gate.py` (the effective-N tiered verdict), `report_md.py`
- `backtest/` — vectorized cost-aware engine (next-bar execution, funding leg)
- `data_layer/` — Binance public history, CMC client (+ Fear & Greed backbone,
  live regime context), eligible-token universe, parquet cache
- `bnbagent_demo/` — ERC-8004 identity + ERC-8183 commerce demo

Crypto calendars are explicit everywhere (365d / 4h / 8h-funding); the
annualization factors are pinned by tests — mixing them up is a silent 4–16×
Sharpe inflation, the deadliest bug class in this domain.
