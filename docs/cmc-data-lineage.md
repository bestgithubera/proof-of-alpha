# CMC data lineage

Every signal traces to a named data field. CoinMarketCap is the heart of the
live/as-of layer and the sentiment signal; Binance public history backfills
*backtest* prices because CMC Basic tier has no historical price API (verified
2026-06-12). This split is stated honestly rather than hidden.

- **fear_greed / fng_regime** — Fear & Greed index.
  Backtest: alternative.me 2018→ (CMC-equivalent index). Live/as-of: CMC
  `/v3/fear-and-greed/latest`.
- **fng_divergence** — F&G trend vs cross-sectional price strength.
  Backtest: F&G history + Binance close. Live/as-of: CMC F&G + CMC listings.
- **funding_rate / funding_carry** — perp funding (derivatives positioning).
  Backtest: Binance funding. (CMC Basic has no funding history.)
- **regime_context overlay** — live F&G + top-by-volume snapshot.
  Live/as-of only: CMC `/v3/fear-and-greed/latest` + `/v1/cryptocurrency/listings/latest`,
  or the Agent Hub MCP `execute_skill` market-data path.
- **capacity** — ADV (USD volume).
  Backtest: Binance quote volume. Live/as-of: CMC live volume.

## Agent Hub path

The CMC AI Agent Hub MCP (`cmc-skill-hub`) is the preferred live path: an agent
calls `find_skill` to discover a market-data skill, then `execute_skill` to pull
the current regime. `skill/scripts/regime_context.py` implements the headless
fallback to CMC Pro REST when no MCP session is available, so the overlay works
both inside an Agent Hub conversation and from the command line.

## Basic-tier limits (verified 2026-06-12)

10k credits/month, 30 req/min, **no historical price data**. Backtests therefore
run on Binance public history; CMC powers the live signal, the sentiment-divergence
signal, and the regime overlay. Nothing in the backtest claims CMC history it does
not have.
