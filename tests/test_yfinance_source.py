from datetime import date

import pandas as pd
import pytest

from jp_quant.ingestion.schema import EQUITY_COLUMNS
from jp_quant.ingestion.yfinance_source import to_raw_equity_frame

VINTAGE = date(2024, 6, 1)


def test_schema_and_adjustment_factor(yf_history: pd.DataFrame) -> None:
    out = to_raw_equity_frame(yf_history, symbol="QQQ", vintage=VINTAGE)
    assert list(out.columns) == EQUITY_COLUMNS
    assert len(out) == 2
    assert out["symbol"].unique().tolist() == ["QQQ"]
    assert out["source"].unique().tolist() == ["yfinance"]
    # adj_factor converts raw close into the adjusted close
    assert out.loc[0, "adj_factor"] == pytest.approx(403.5 / 404.0)
    assert (out["close"] * out["adj_factor"]).tolist() == pytest.approx([403.5, 401.5])


def test_empty_history_returns_empty_schema() -> None:
    out = to_raw_equity_frame(pd.DataFrame(), symbol="QQQ", vintage=VINTAGE)
    assert out.empty
    assert list(out.columns) == EQUITY_COLUMNS


def test_tz_aware_index_is_normalized(yf_history: pd.DataFrame) -> None:
    tz_history = yf_history.tz_localize("America/New_York")
    out = to_raw_equity_frame(tz_history, symbol="QQQ", vintage=VINTAGE)
    assert out["date"].dt.tz is None
    assert out["date"].tolist() == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]


def test_zero_close_falls_back_to_unit_factor() -> None:
    idx = pd.DatetimeIndex(["2024-01-02"], name="Date")
    history = pd.DataFrame(
        {"Close": [0.0], "Adj Close": [0.0], "Volume": [0]},
        index=idx,
    )
    out = to_raw_equity_frame(history, symbol="QQQ", vintage=VINTAGE)
    assert out.loc[0, "adj_factor"] == 1.0
