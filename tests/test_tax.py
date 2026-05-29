import pandas as pd
import pytest

from jp_quant.backtest.engine import monthly_contributions, run_backtest
from jp_quant.backtest.strategies import B0_QQQ_DCA
from jp_quant.tax import (
    Account,
    after_tax_on_liquidation,
    fx_attribution,
    money_weighted_return,
    withholding_tax,
)


def test_withholding_specified_vs_nisa() -> None:
    assert withholding_tax(1000.0, Account.SPECIFIED) == pytest.approx(203.15)
    assert withholding_tax(-500.0, Account.SPECIFIED) == 0.0  # loss → no tax
    assert withholding_tax(1000.0, Account.NISA_GROWTH) == 0.0


def test_after_tax_on_liquidation() -> None:
    r = after_tax_on_liquidation(3000.0, 2000.0, Account.SPECIFIED)
    assert r.realized_gain_jpy == pytest.approx(1000.0)
    assert r.tax_jpy == pytest.approx(203.15)
    assert r.aftertax_terminal_jpy == pytest.approx(2796.85)
    # NISA pays no tax
    nisa = after_tax_on_liquidation(3000.0, 2000.0, Account.NISA_GROWTH)
    assert nisa.aftertax_terminal_jpy == pytest.approx(3000.0)


def test_fx_attribution_sums_to_total() -> None:
    a = fx_attribution(10.0, 100.0, 110.0, 120.0, 150.0)
    assert a.underlying_jpy == pytest.approx(22000.0)
    assert a.fx_jpy == pytest.approx(40000.0)
    assert a.cross_jpy == pytest.approx(8000.0)
    assert a.total_jpy == pytest.approx(10.0 * (120.0 * 150.0 - 100.0 * 110.0))


def test_money_weighted_return_known_irr() -> None:
    cf = [(pd.Timestamp("2020-01-01"), -100.0), (pd.Timestamp("2022-01-01"), 121.0)]
    assert money_weighted_return(cf) == pytest.approx(0.10, abs=2e-3)


def test_b0_after_tax_matches_manual() -> None:
    # B0 in JPY: contribute 1000 in 2020 and 2021 @1000, hold to 2022 @1500.
    idx = pd.to_datetime(["2020-01-31", "2021-01-31", "2022-01-31"])
    prices_jpy = pd.DataFrame({"QQQ": [1000.0, 1000.0, 1500.0]}, index=idx)
    res = run_backtest(
        prices_jpy, monthly_contributions(pd.DatetimeIndex(idx[:2]), 1000.0), B0_QQQ_DCA
    )

    terminal_value = sum(p.shares * 1500.0 for p in res.final_positions.values())
    cost = sum(p.cost_basis for p in res.final_positions.values())
    atl = after_tax_on_liquidation(terminal_value, cost, Account.SPECIFIED)

    # manual: 2 shares, cost 2000 → terminal 3000, gain 1000, tax 203.15, after-tax 2796.85
    assert res.final_positions["QQQ"].shares == pytest.approx(2.0)
    assert atl.pretax_terminal_jpy == pytest.approx(3000.0)
    assert atl.realized_gain_jpy == pytest.approx(1000.0)
    assert atl.tax_jpy == pytest.approx(203.15)
    assert atl.aftertax_terminal_jpy == pytest.approx(2796.85)

    # after-tax money-weighted return is strictly below pre-tax
    pretax_cf = [(idx[0], -1000.0), (idx[1], -1000.0), (idx[2], atl.pretax_terminal_jpy)]
    aftertax_cf = [(idx[0], -1000.0), (idx[1], -1000.0), (idx[2], atl.aftertax_terminal_jpy)]
    assert money_weighted_return(aftertax_cf) < money_weighted_return(pretax_cf)
