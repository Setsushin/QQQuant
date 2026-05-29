"""Normalized column schemas for raw landed data."""

from __future__ import annotations

import pandas as pd

EQUITY_COLUMNS: list[str] = [
    "date",
    "symbol",
    "source",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "dividends",
    "splits",
    "adj_close",
    "adj_factor",
    "vintage",
]

MACRO_COLUMNS: list[str] = ["date", "series_id", "source", "value", "vintage"]


def empty_equity_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=EQUITY_COLUMNS)


def empty_macro_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=MACRO_COLUMNS)
