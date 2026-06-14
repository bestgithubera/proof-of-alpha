"""Data-layer tests — pure functions on fixtures, NO network in pytest."""
import pandas as pd

from data_layer.binance_client import parse_funding, parse_klines
from data_layer.store import load_or_fetch, save
from data_layer.universe import build_universe, load_eligible

KLINE_FIXTURE = [
    [1781136000000, "586.51", "607.33", "586.51", "605.76", "115805.929",
     1781222399999, "69397543.63", 594193, "63411.62", "37996712.58", "0"],
    [1781222400000, "605.77", "613.39", "596.58", "602.43", "99899.642",
     1781308799999, "60495539.88", 512345, "50000.0", "30000000.0", "0"],
]
FUNDING_FIXTURE = [
    {"symbol": "BNBUSDT", "fundingTime": 1781251200000, "fundingRate": "0.00000000",
     "markPrice": "600.12865016"},
    {"symbol": "BNBUSDT", "fundingTime": 1781280000000, "fundingRate": "0.00006548",
     "markPrice": "605.52299741"},
]


def test_parse_klines_tidy_utc_floats():
    df = parse_klines(KLINE_FIXTURE)
    assert list(df.columns) == ["open", "high", "low", "close", "volume",
                                "quote_volume", "n_trades"]
    assert df.index.tz is not None                       # UTC-aware
    assert df["close"].iloc[0] == 605.76
    assert df["n_trades"].dtype.kind == "i"
    assert df.index.is_monotonic_increasing


def test_parse_funding():
    df = parse_funding(FUNDING_FIXTURE)
    assert df["funding_rate"].iloc[1] == 0.00006548
    assert df["mark_price"].iloc[0] == 600.12865016
    assert df.index.tz is not None


def test_universe_intersection_and_flags(tmp_path):
    f = tmp_path / "eligible.txt"
    f.write_text("# comment\nETH\nUSDT\nCAKE\nNOPE\nSHIB\n")
    eligible = load_eligible(f)
    assert eligible == ["ETH", "USDT", "CAKE", "NOPE", "SHIB"]

    spot = {"ETHUSDT", "USDTTRY", "CAKEUSDT", "SHIBUSDT"}
    perp = {"ETHUSDT", "1000SHIBUSDT"}
    rows = {r["symbol"]: r for r in build_universe(eligible, spot, perp)}

    assert rows["ETH"]["tradeable"] and rows["ETH"]["binance_perp"] == "ETHUSDT"
    assert rows["USDT"]["is_stable_or_pegged"] and not rows["USDT"]["tradeable"]
    assert rows["NOPE"]["binance_spot"] is None and not rows["NOPE"]["tradeable"]
    assert rows["SHIB"]["binance_perp"] == "1000SHIBUSDT"  # 1000-prefixed perp found


def test_store_load_or_fetch_idempotent(tmp_path):
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return pd.DataFrame({"x": [1, 2, 3]})

    a = load_or_fetch("src", "name", fetch, root=tmp_path)
    b = load_or_fetch("src", "name", fetch, root=tmp_path)
    assert calls["n"] == 1                # second call served from cache
    assert a.equals(b)

    save(pd.DataFrame({"x": [9]}), "src", "name", root=tmp_path)
    c = load_or_fetch("src", "name", fetch, root=tmp_path)
    assert c["x"].tolist() == [9]


def test_cmc_regime_context_shape():
    from data_layer.cmc_client import CmcClient

    class FakeResp:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): pass
        def json(self): return self._p

    class FakeSession:
        def get(self, url, params=None, headers=None, timeout=None):
            if "fear-and-greed" in url:
                return FakeResp({"status": {"error_code": 0},
                                 "data": {"value": 72, "value_classification": "Greed"}})
            return FakeResp({"status": {"error_code": 0}, "data": [
                {"symbol": "BNB", "name": "BNB", "cmc_rank": 4,
                 "quote": {"USD": {"price": 600, "volume_24h": 1e9,
                                   "market_cap": 9e10, "percent_change_24h": 1.2}}}]})

    c = CmcClient(api_key="x", session=FakeSession())
    ctx = c.regime_context(top=1)
    assert ctx["fear_greed"]["value"] == 72
    assert ctx["fear_greed"]["classification"] == "Greed"
    assert ctx["top_by_volume"][0]["symbol"] == "BNB"
    assert ctx["source"] == "cmc-rest"


def test_fng_frame_values_survive_datetime_index():
    from data_layer.cmc_client import _fng_frame
    rows = [
        {"timestamp": "1781136000", "value": 16, "value_classification": "Extreme fear"},
        {"timestamp": "1781049600", "value": 14, "value_classification": "Extreme fear"},
    ]
    df = _fng_frame(rows)
    assert df["fng"].notna().all()                 # the realignment-bug class
    assert df["fng"].tolist() == [14, 16]          # sorted ascending by date
    assert df.index.tz is not None
