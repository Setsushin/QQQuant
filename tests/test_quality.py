import pandas as pd

from jp_quant.ingestion.quality import cross_source_close_check


def _frame(close: float) -> pd.DataFrame:
    return pd.DataFrame({"date": [pd.Timestamp("2024-01-02")], "symbol": ["QQQ"], "close": [close]})


def test_flags_breach_beyond_tolerance() -> None:
    breaches = cross_source_close_check(_frame(404.0), _frame(450.0), rel_tol=0.01)
    assert len(breaches) == 1
    assert breaches.loc[0, "symbol"] == "QQQ"


def test_passes_within_tolerance() -> None:
    breaches = cross_source_close_check(_frame(404.0), _frame(404.1), rel_tol=0.01)
    assert breaches.empty


def test_no_overlap_returns_empty() -> None:
    yf = _frame(404.0)
    stooq = _frame(404.0).assign(date=[pd.Timestamp("2024-01-03")])
    assert cross_source_close_check(yf, stooq).empty
