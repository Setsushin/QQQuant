"""Point-in-time technical signals for strategies (spec §4).

All operate on a price history *up to and including* the evaluation date; callers
take ``.iloc[-1]`` for the current value, so there is no look-ahead.
"""

from __future__ import annotations

import pandas as pd

TRADING_DAYS_YEAR = 252  # ~52 weeks
TRADING_DAYS_200W = 1000  # 200 weeks * 5 trading days


def trailing_high(prices: pd.Series, window: int) -> pd.Series:
    return prices.rolling(window, min_periods=1).max()


def drawdown_from_high(prices: pd.Series, window: int) -> pd.Series:
    """Fractional drawdown from the trailing high (<= 0)."""
    return prices / trailing_high(prices, window) - 1.0


def sma(prices: pd.Series, window: int) -> pd.Series:
    return prices.rolling(window, min_periods=1).mean()
