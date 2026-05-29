"""Cross-source data-quality checks (spec §5.1).

yfinance raw ``close`` (``auto_adjust=False``) and Stooq ``close`` are both
split-adjusted and dividend-unadjusted, so they should agree on overlapping
dates within a tight tolerance. Divergence flags an ingestion/adjustment bug.
"""

from __future__ import annotations

import pandas as pd


def cross_source_close_check(
    yf_frame: pd.DataFrame, stooq_frame: pd.DataFrame, *, rel_tol: float = 0.01
) -> pd.DataFrame:
    """Return rows whose yfinance vs Stooq close diverge by more than ``rel_tol``.

    An empty result means the check passes.
    """
    left = yf_frame[["date", "symbol", "close"]].rename(columns={"close": "close_yf"})
    right = stooq_frame[["date", "symbol", "close"]].rename(columns={"close": "close_stooq"})
    merged = left.merge(right, on=["date", "symbol"], how="inner")
    merged = merged[(merged["close_yf"] > 0) & (merged["close_stooq"] > 0)]
    merged["rel_diff"] = (merged["close_yf"] - merged["close_stooq"]).abs() / merged["close_stooq"]
    breaches: pd.DataFrame = merged[merged["rel_diff"] > rel_tol].reset_index(drop=True)
    return breaches
