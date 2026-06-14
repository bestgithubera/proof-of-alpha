"""Binance public REST client — historical klines + perp funding rates.

No API key required. This is the BACKTEST history source (the CMC Basic tier has
no historical data); the live Skill path uses CMC. Polite pacing: Binance allows
generous public weights, but we sleep on 429/418 and keep a small fixed delay.
"""

from __future__ import annotations

import time

import pandas as pd
import requests

SPOT_BASE = "https://api.binance.com"
FUT_BASE = "https://fapi.binance.com"
_KLINE_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "n_trades",
    "taker_buy_base", "taker_buy_quote", "ignore",
]


class BinanceClient:
    def __init__(self, pause_s: float = 0.15, session: requests.Session | None = None):
        self.pause_s = pause_s
        self.session = session or requests.Session()

    def _get(self, url: str, params: dict) -> list | dict:
        for attempt in range(5):
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code in (418, 429):
                wait = int(resp.headers.get("Retry-After", 30))
                time.sleep(max(wait, 5))
                continue
            resp.raise_for_status()
            time.sleep(self.pause_s)
            return resp.json()
        raise RuntimeError(f"rate-limited 5x on {url}")

    def get_klines(
        self, symbol: str, interval: str, start_ms: int, end_ms: int | None = None,
        futures: bool = False,
    ) -> pd.DataFrame:
        """All klines for [start_ms, end_ms) paginated 1000/call. UTC index."""
        base = FUT_BASE + "/fapi/v1/klines" if futures else SPOT_BASE + "/api/v3/klines"
        frames: list[pd.DataFrame] = []
        cursor = start_ms
        while True:
            params = {"symbol": symbol, "interval": interval,
                      "startTime": cursor, "limit": 1000}
            if end_ms is not None:
                params["endTime"] = end_ms
            raw = self._get(base, params)
            if not raw:
                break
            frames.append(parse_klines(raw))
            last_open = raw[-1][0]
            if len(raw) < 1000:
                break
            cursor = last_open + 1
        if not frames:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume",
                                         "quote_volume", "n_trades"])
        df = pd.concat(frames)
        return df[~df.index.duplicated(keep="first")].sort_index()

    def get_funding_history(self, symbol: str, start_ms: int | None = None) -> pd.DataFrame:
        """Full perp funding-rate history (8h stamps), paginated 1000/call."""
        frames: list[pd.DataFrame] = []
        cursor = start_ms or 0
        while True:
            params = {"symbol": symbol, "startTime": cursor, "limit": 1000}
            raw = self._get(FUT_BASE + "/fapi/v1/fundingRate", params)
            if not raw:
                break
            frames.append(parse_funding(raw))
            last = raw[-1]["fundingTime"]
            if len(raw) < 1000:
                break
            cursor = last + 1
        if not frames:
            return pd.DataFrame(columns=["funding_rate", "mark_price"])
        df = pd.concat(frames)
        return df[~df.index.duplicated(keep="first")].sort_index()

    def get_exchange_symbols(self, futures: bool = False) -> set[str]:
        """TRADING-status symbols on spot or USDT-margined futures."""
        url = (FUT_BASE + "/fapi/v1/exchangeInfo") if futures else (SPOT_BASE + "/api/v3/exchangeInfo")
        info = self._get(url, {})
        return {s["symbol"] for s in info["symbols"] if s["status"] == "TRADING"}


def parse_klines(raw: list[list]) -> pd.DataFrame:
    """Raw kline rows -> tidy float frame indexed by UTC open time."""
    df = pd.DataFrame(raw, columns=_KLINE_COLS)
    idx = pd.to_datetime(df["open_time"].astype("int64"), unit="ms", utc=True)
    out = df[["open", "high", "low", "close", "volume", "quote_volume"]].astype(float)
    out["n_trades"] = df["n_trades"].astype(int)
    out.index = idx
    out.index.name = "time"
    return out


def parse_funding(raw: list[dict]) -> pd.DataFrame:
    """Raw funding rows -> frame indexed by UTC funding time."""
    df = pd.DataFrame(raw)
    idx = pd.to_datetime(df["fundingTime"].astype("int64"), unit="ms", utc=True)
    out = pd.DataFrame({
        "funding_rate": df["fundingRate"].astype(float).to_numpy(),
        # markPrice is occasionally empty string on old rows
        "mark_price": pd.to_numeric(df.get("markPrice"), errors="coerce").to_numpy(),
    }, index=pd.DatetimeIndex(idx))
    out.index.name = "time"
    return out
