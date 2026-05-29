"""FRED macro series and Stooq backup prices for cross-source checks.

FRED uses the official ``fredapi`` client when ``FRED_API_KEY`` is set (which also
unlocks ALFRED point-in-time vintages, spec §5.3), and falls back to the keyless
fredgraph.csv export otherwise. Stooq's free CSV endpoint is now captcha/API-key
gated, so it is opt-in via ``STOOQ_APIKEY`` and degrades to an empty frame without
one. Stooq is only an independent close-price source for the cross-source quality
check (spec §5.1), never a full OHLCV source.
"""

from __future__ import annotations

import io
import os
from datetime import date

import certifi
import pandas as pd
import requests

from jp_quant.config import EquitySeries, MacroSeries, Source
from jp_quant.ingestion.schema import MACRO_COLUMNS, empty_macro_frame

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
STOOQ_CSV_URL = "https://stooq.com/q/d/l/?s={ticker}&i=d"

STOOQ_CLOSE_COLUMNS: list[str] = ["date", "symbol", "source", "close", "vintage"]


def _empty_stooq_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=STOOQ_CLOSE_COLUMNS)


def parse_fred_csv(text: str, *, series_id: str, vintage: date) -> pd.DataFrame:
    """Parse a fredgraph.csv payload. Missing values are encoded as ``.`` by FRED."""
    raw = pd.read_csv(io.StringIO(text))
    if raw.empty:
        return empty_macro_frame()
    date_col = str(raw.columns[0])
    value_col = series_id if series_id in raw.columns else str(raw.columns[1])
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(raw[date_col]).dt.normalize(),
            "series_id": series_id,
            "source": Source.FRED.value,
            "value": pd.to_numeric(raw[value_col], errors="coerce"),
            "vintage": vintage,
        }
    )
    return out[MACRO_COLUMNS].reset_index(drop=True)


def parse_stooq_csv(text: str, *, symbol: str, vintage: date) -> pd.DataFrame:
    """Parse a Stooq daily CSV (``Date,Open,High,Low,Close,Volume``) into close prices.

    Returns an empty frame for gated/error payloads (e.g. the "Get your apikey" message).
    """
    header = text.splitlines()[0].lower() if text.strip() else ""
    if "," not in header or "date" not in header:
        return _empty_stooq_frame()
    raw = pd.read_csv(io.StringIO(text))
    cols = {c.lower(): c for c in raw.columns}
    if "date" not in cols or "close" not in cols:
        return _empty_stooq_frame()
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(raw[cols["date"]]).dt.normalize(),
            "symbol": symbol,
            "source": Source.STOOQ.value,
            "close": pd.to_numeric(raw[cols["close"]], errors="coerce"),
            "vintage": vintage,
        }
    )
    return out[STOOQ_CLOSE_COLUMNS].reset_index(drop=True)


def _get(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def _fetch_fred_api(series: MacroSeries, api_key: str, *, vintage: date) -> pd.DataFrame:
    # fredapi uses urllib, which needs a CA bundle; framework Pythons often lack one.
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    from fredapi import Fred

    s = Fred(api_key=api_key).get_series(series.series_id)
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(s.index).normalize(),
            "series_id": series.series_id,
            "source": Source.FRED.value,
            "value": pd.to_numeric(s.to_numpy(), errors="coerce"),
            "vintage": vintage,
        }
    )
    return out[MACRO_COLUMNS].reset_index(drop=True)


def fetch_fred(series: MacroSeries, *, vintage: date) -> pd.DataFrame:
    """Fetch one FRED series via fredapi (if ``FRED_API_KEY`` set) else keyless CSV."""
    api_key = os.environ.get("FRED_API_KEY")
    if api_key:
        return _fetch_fred_api(series, api_key, vintage=vintage)
    return parse_fred_csv(
        _get(FRED_CSV_URL.format(series_id=series.series_id)),
        series_id=series.series_id,
        vintage=vintage,
    )


def fetch_stooq(series: EquitySeries, *, vintage: date) -> pd.DataFrame:
    """Fetch Stooq close prices for cross-source validation (network call).

    Appends ``STOOQ_APIKEY`` when set; without it the endpoint is gated and this
    returns an empty frame.
    """
    if series.stooq_ticker is None:
        return _empty_stooq_frame()
    url = STOOQ_CSV_URL.format(ticker=series.stooq_ticker)
    apikey = os.environ.get("STOOQ_APIKEY")
    if apikey:
        url = f"{url}&apikey={apikey}"
    return parse_stooq_csv(_get(url), symbol=series.symbol, vintage=vintage)
