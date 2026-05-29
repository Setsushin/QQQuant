import numpy as np
import pandas as pd
import pytest

from jp_quant.backtest.engine import month_end_trade_dates, monthly_contributions
from jp_quant.backtest.metrics import (
    cagr,
    longest_underwater_months,
    max_drawdown,
    max_drawdown_duration_months,
    worst_rolling_return,
)
from jp_quant.backtest.report import build_report
from jp_quant.backtest.strategies import D3_TIERED

IDX = pd.bdate_range("2020-01-01", periods=10)  # Jan 1,2,3,6,7,8,9,10,13,14
WEALTH = pd.Series([1.0, 1.1, 1.2, 1.0, 0.9, 1.0, 1.25, 1.3, 1.2, 1.35], index=IDX)


def test_cagr_doubling_over_one_year() -> None:
    idx = pd.bdate_range("2020-01-01", "2021-01-01")
    wealth = pd.Series(np.linspace(1.0, 2.0, len(idx)), index=idx)
    years = (idx[-1] - idx[0]).days / 365.25
    assert cagr(wealth) == pytest.approx(2.0 ** (1.0 / years) - 1.0, rel=1e-9)


def test_drawdown_stats_hand_path() -> None:
    assert max_drawdown(WEALTH) == pytest.approx(0.9 / 1.2 - 1.0)  # -25%
    # deepest DD: prior peak 1.2 (Jan 3) → recovery 1.25 (Jan 9) = 6 calendar days
    assert max_drawdown_duration_months(WEALTH) == pytest.approx(6 / 30.44)
    assert longest_underwater_months(WEALTH) == pytest.approx(6 / 30.44)


def test_worst_rolling_return() -> None:
    assert worst_rolling_return(WEALTH, 3) == pytest.approx(0.9 / 1.1 - 1.0)  # -18.18%


def _panel() -> pd.DataFrame:
    idx = pd.bdate_range("2017-01-02", "2022-12-30")
    n = len(idx)
    ret = np.full(n, 0.0005)
    ret[0] = 0.0
    ret[730:770] = -0.018  # a >25% drawdown cluster to trigger the deep tier
    qqq_ret = pd.Series(ret, index=idx)

    def lev(mult: float) -> np.ndarray:
        return 100.0 * np.cumprod(1.0 + (mult * qqq_ret).to_numpy())

    return pd.DataFrame(
        {
            "QQQ": 100.0 * np.cumprod(1.0 + ret),
            "QLD": lev(2.0),
            "TQQQ": lev(3.0),
            "SGOV": 100.0 * np.cumprod(1.0 + np.full(n, 2e-5)),
            "IEF": 100.0 * np.cumprod(1.0 + np.full(n, 1e-4)),
        },
        index=idx,
    )


def test_build_report_covers_all_strategies_with_sane_metrics() -> None:
    panel = _panel()
    contribs = monthly_contributions(month_end_trade_dates(panel), 100_000.0)
    report = build_report(panel, contribs)

    assert len(report) == 9  # B0,B2,B3,T1,T2,D1-D4
    assert report["cagr"].notna().all()
    assert (report["max_drawdown"] <= 0).all()
    assert (report["ann_vol"] >= 0).all()

    # B0: pure QQQ-DCA — never deviates, never converts, and pays tax on its gain.
    b0 = report.loc["B0 QQQ-DCA"]
    assert b0["pct_months_deviation"] == 0.0
    assert b0["taxable_events_per_year"] == 0.0
    assert b0["tax_drag"] > 0.0  # positive gain → after-tax CAGR strictly lower
    assert b0["cagr_after_tax"] < b0["cagr"]

    # B3 60/40: every contribution buys IEF, so every month deviates from base QQQ.
    assert report.loc["B3 60/40-DCA"]["pct_months_deviation"] == pytest.approx(1.0)


def test_drawdown_tilt_generates_taxable_conversions() -> None:
    panel = _panel()
    contribs = monthly_contributions(month_end_trade_dates(panel), 100_000.0)
    report = build_report(panel, contribs, [D3_TIERED])
    # crash then recovery → leveraged lots are sold back to QQQ (a taxable event, §6)
    assert report.loc["D3 Tiered"]["taxable_events_per_year"] > 0.0
