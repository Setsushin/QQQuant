"""Asset universe, storage layout, and data-vintage configuration.

A *vintage* is the snapshot date of an ingestion run. Because yfinance returns
prices that are re-adjusted whenever a new dividend/split occurs, the same
historical date can have different adjusted values across vintages. Storing raw
OHLCV + the adjustment factor and stamping every row with its vintage is what
makes a backtest reproducible (spec §5.3).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path


class Source(StrEnum):
    YFINANCE = "yfinance"
    FRED = "fred"
    STOOQ = "stooq"


@dataclass(frozen=True)
class EquitySeries:
    """An equity/ETF series and its per-source tickers."""

    symbol: str
    """Canonical symbol used across the warehouse, e.g. ``QQQ``."""
    yf_ticker: str
    """yfinance ticker, e.g. ``QQQ`` or ``^VIX``."""
    stooq_ticker: str | None
    """Stooq ticker for cross-source validation, e.g. ``qqq.us`` (None if unavailable)."""
    history_start: str
    """Earliest expected real data; informational, also the synthesis cut-over (spec §7)."""


# Week-1 minimum is QQQ/TQQQ/QLD/VIX; SGOV/IEF round out the backtest universe (spec §8 F2).
EQUITY_UNIVERSE: tuple[EquitySeries, ...] = (
    EquitySeries("QQQ", "QQQ", "qqq.us", "1999-03-10"),
    EquitySeries("TQQQ", "TQQQ", "tqqq.us", "2010-02-11"),
    EquitySeries("QLD", "QLD", "qld.us", "2006-06-21"),
    EquitySeries("VIX", "^VIX", None, "1990-01-02"),
    EquitySeries("SGOV", "SGOV", "sgov.us", "2020-05-26"),
    EquitySeries("IEF", "IEF", "ief.us", "2002-07-26"),
)


@dataclass(frozen=True)
class MacroSeries:
    """A FRED macro series."""

    series_id: str
    description: str


MACRO_UNIVERSE: tuple[MacroSeries, ...] = (
    MacroSeries("DTB3", "3-Month Treasury Bill secondary-market rate (borrow-cost proxy)"),
    MacroSeries("DEXJPUS", "USD/JPY spot exchange rate"),
    MacroSeries("CPIAUCSL", "US CPI, all urban consumers"),
    MacroSeries("JPNCPIALLMINMEI", "Japan CPI, all items"),
)


@dataclass(frozen=True)
class Paths:
    data_dir: Path

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "jp_quant.duckdb"


def get_paths() -> Paths:
    """Resolve the data root, overridable via ``JP_QUANT_DATA_DIR``."""
    root = Path(os.environ.get("JP_QUANT_DATA_DIR", "data")).resolve()
    return Paths(data_dir=root)


def get_vintage() -> date:
    """Ingestion snapshot date; pin via ``JP_QUANT_VINTAGE`` (ISO) for reproducible runs."""
    pinned = os.environ.get("JP_QUANT_VINTAGE")
    return date.fromisoformat(pinned) if pinned else date.today()


def equity_by_symbol(symbol: str) -> EquitySeries:
    for series in EQUITY_UNIVERSE:
        if series.symbol == symbol:
            return series
    raise KeyError(f"unknown equity symbol: {symbol}")
