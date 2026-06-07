import pandas as pd
import pytest

from jp_quant.backtest.engine import (
    Portfolio,
    lump_sum_contribution,
    month_end_trade_dates,
    monthly_contributions,
    run_backtest,
)
from jp_quant.backtest.strategies import B0_QQQ_DCA, B3_60_40_DCA


def test_b0_qqq_dca_matches_hand_computation() -> None:
    # Hand check: contribute 1200 at three month-ends, then hold one more month.
    idx = pd.to_datetime(["2020-01-31", "2020-02-28", "2020-03-31", "2020-04-30"])
    prices = pd.DataFrame({"QQQ": [100.0, 125.0, 80.0, 200.0]}, index=idx)
    contribs = monthly_contributions(pd.DatetimeIndex(idx[:3]), 1200.0)

    res = run_backtest(prices, contribs, B0_QQQ_DCA, commission_rate=0.0)

    # shares: 1200/100 + 1200/125 + 1200/80 = 12 + 9.6 + 15 = 36.6
    assert res.final_positions["QQQ"].shares == pytest.approx(36.6)
    assert res.total_contributed == pytest.approx(3600.0)
    # weighted-average cost basis = total cost / shares
    assert res.final_positions["QQQ"].avg_cost == pytest.approx(3600.0 / 36.6)
    # equity curve mark-to-market
    assert res.equity_curve.loc["2020-02-28"] == pytest.approx(21.6 * 125.0)
    assert res.equity_curve.loc["2020-03-31"] == pytest.approx(36.6 * 80.0)
    assert res.final_value == pytest.approx(36.6 * 200.0)  # 7320


def test_b1_lump_sum_via_schedule() -> None:
    idx = pd.to_datetime(["2020-01-31", "2020-04-30"])
    prices = pd.DataFrame({"QQQ": [100.0, 200.0]}, index=idx)

    res = run_backtest(
        prices, lump_sum_contribution(idx[0], 3600.0), B0_QQQ_DCA, commission_rate=0.0
    )

    assert res.final_positions["QQQ"].shares == pytest.approx(36.0)
    assert res.final_value == pytest.approx(7200.0)


def test_b3_60_40_split() -> None:
    idx = pd.to_datetime(["2020-01-31", "2020-02-29"])
    prices = pd.DataFrame({"QQQ": [100.0, 200.0], "IEF": [50.0, 55.0]}, index=idx)

    res = run_backtest(
        prices, monthly_contributions(pd.DatetimeIndex(idx[:1]), 1000.0), B3_60_40_DCA,
        commission_rate=0.0,
    )

    assert res.final_positions["QQQ"].shares == pytest.approx(6.0)  # 600/100
    assert res.final_positions["IEF"].shares == pytest.approx(8.0)  # 400/50
    assert res.final_value == pytest.approx(6 * 200.0 + 8 * 55.0)  # 1640


def test_portfolio_weighted_average_realized_gain() -> None:
    p = Portfolio()
    p.buy("QQQ", 1000.0, 100.0)  # 10 sh @100
    p.buy("QQQ", 1000.0, 200.0)  # 5 sh @200 → 15 sh, cost 2000, avg 133.33
    assert p.positions["QQQ"].avg_cost == pytest.approx(2000.0 / 15.0)

    gain = p.sell("QQQ", 6.0, 300.0)
    assert gain == pytest.approx(6.0 * (300.0 - 2000.0 / 15.0))
    assert p.positions["QQQ"].shares == pytest.approx(9.0)


def test_commission_charged_on_contribution_buys() -> None:
    # 0.1% commission: a 1000 buy at price 100 deploys 999 into shares, keeps full basis.
    idx = pd.to_datetime(["2020-01-31", "2020-02-29"])
    prices = pd.DataFrame({"QQQ": [100.0, 100.0]}, index=idx)
    contribs = monthly_contributions(pd.DatetimeIndex(idx[:1]), 1000.0)

    res = run_backtest(prices, contribs, B0_QQQ_DCA, commission_rate=0.001)

    pos = res.final_positions["QQQ"]
    assert pos.shares == pytest.approx((1000.0 - 1.0) / 100.0)  # 9.99
    assert pos.cost_basis == pytest.approx(1000.0)  # commission capitalised into 取得費
    assert res.final_value == pytest.approx(9.99 * 100.0)  # fee is a real drag on wealth


def test_conversion_pays_commission_on_both_legs() -> None:
    p = Portfolio()
    p.buy("QLD", 1000.0, 100.0)  # 10 sh @100
    # Sell 10 sh @120 with 0.1% fee, then buy QQQ @60 with the net proceeds, fee again.
    gross = 10.0 * 120.0
    sell_fee = gross * 0.001
    realized = p.sell("QLD", 10.0, 120.0, commission=sell_fee)
    assert realized == pytest.approx(10.0 * (120.0 - 100.0) - sell_fee)
    proceeds = gross - sell_fee
    buy_fee = proceeds * 0.001
    bought = p.buy("QQQ", proceeds, 60.0, commission=buy_fee)
    assert bought == pytest.approx((proceeds - buy_fee) / 60.0)


def test_engine_records_position_open_date_on_first_buy() -> None:
    idx = pd.to_datetime(["2020-01-31", "2020-02-29"])
    prices = pd.DataFrame({"QQQ": [100.0, 110.0]}, index=idx)
    contribs = monthly_contributions(pd.DatetimeIndex(idx), 1000.0)
    res = run_backtest(prices, contribs, B0_QQQ_DCA, commission_rate=0.0)
    # opened is stamped at the first buy and not bumped by the second contribution.
    assert res.final_positions["QQQ"].opened == pd.Timestamp("2020-01-31")


def test_month_end_trade_dates() -> None:
    idx = pd.bdate_range("2021-01-01", "2021-03-31")
    prices = pd.DataFrame({"QQQ": 1.0}, index=idx)
    ted = month_end_trade_dates(prices)
    assert len(ted) == 3
    assert ted[0] == pd.Timestamp("2021-01-29")  # last business day of Jan 2021
