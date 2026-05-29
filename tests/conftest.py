import pandas as pd
import pytest


@pytest.fixture
def yf_history() -> pd.DataFrame:
    """A yfinance-style ``Ticker.history(auto_adjust=False)`` frame."""
    idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], name="Date")
    return pd.DataFrame(
        {
            "Open": [400.0, 403.0],
            "High": [405.0, 406.0],
            "Low": [399.0, 401.0],
            "Close": [404.0, 402.0],
            "Adj Close": [403.5, 401.5],
            "Volume": [1_000_000, 1_100_000],
            "Dividends": [0.0, 0.0],
            "Stock Splits": [0.0, 0.0],
        },
        index=idx,
    )
