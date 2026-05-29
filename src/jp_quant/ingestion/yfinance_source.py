"""yfinance equity ingestion.

The network fetch is a thin wrapper; the normalization in :func:`to_raw_equity_frame`
is pure and unit-tested offline. We deliberately fetch with ``auto_adjust=False`` so
we keep *raw* OHLCV plus a derived ``adj_factor`` (= adjusted close / raw close),
letting downstream re-derive the adjusted series deterministically (spec §5.2/§5.3).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from jp_quant.config import EquitySeries, Source
from jp_quant.ingestion.schema import EQUITY_COLUMNS, empty_equity_frame

_RENAME: dict[str, str] = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "splits",
}


def to_raw_equity_frame(history: pd.DataFrame, *, symbol: str, vintage: date) -> pd.DataFrame:
    """Normalize a yfinance ``Ticker.history`` frame into the warehouse schema."""
    if history.empty:
        return empty_equity_frame()

    df = history.rename(columns=_RENAME).reset_index()
    date_col = "Date" if "Date" in df.columns else str(df.columns[0])
    dates = pd.to_datetime(df[date_col])
    if dates.dt.tz is not None:
        dates = dates.dt.tz_localize(None)

    out = pd.DataFrame({"date": dates.dt.normalize()})
    out["symbol"] = symbol
    out["source"] = Source.YFINANCE.value
    for col in ("open", "high", "low", "close", "volume", "dividends", "splits", "adj_close"):
        out[col] = pd.to_numeric(df[col], errors="coerce") if col in df.columns else np.nan

    close = out["close"]
    adjustable = (close > 0) & out["adj_close"].notna()
    out["adj_factor"] = np.where(adjustable, out["adj_close"] / close, 1.0)
    out["vintage"] = vintage
    return out[EQUITY_COLUMNS].reset_index(drop=True)


def fetch_equity(series: EquitySeries, *, vintage: date, period: str = "max") -> pd.DataFrame:
    """Fetch one equity series from yfinance and normalize it (network call)."""
    import yfinance as yf

    history: pd.DataFrame = yf.Ticker(series.yf_ticker).history(
        period=period, auto_adjust=False, actions=True
    )
    return to_raw_equity_frame(history, symbol=series.symbol, vintage=vintage)
