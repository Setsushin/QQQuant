import pandas as pd
import pytest

from jp_quant.backtest.composable import drawdown_tilt, sma_switch, vix_tilt
from jp_quant.backtest.engine import (
    AllocationContext,
    Portfolio,
    monthly_contributions,
    run_backtest,
)
from jp_quant.backtest.strategies import (
    D1_DD15_QLD,
    D3_TIERED,
    D4_TIERED_GUARD,
    T1_SMA_TQQQ,
)
from jp_quant.signals import drawdown_from_high, sma, trailing_high


def test_signals_point_in_time() -> None:
    s = pd.Series([100.0, 110.0, 90.0, 95.0])
    assert trailing_high(s, 10).tolist() == [100.0, 110.0, 110.0, 110.0]
    assert drawdown_from_high(s, 10).iloc[2] == pytest.approx(90.0 / 110.0 - 1.0)
    assert sma(s, 2).iloc[1] == pytest.approx(105.0)


def _ctx(prices: pd.DataFrame, portfolio: Portfolio | None = None) -> AllocationContext:
    return AllocationContext(
        date=pd.Timestamp(prices.index[-1]), history=prices, portfolio=portfolio or Portfolio()
    )


def test_sma_switch_targets_leverage_above_sma_else_cash() -> None:
    strat = sma_switch("t", leveraged="TQQQ", cash="SGOV", sma_window=3)
    up = pd.DataFrame({"QQQ": [10.0, 11.0, 12.0, 20.0], "TQQQ": 1.0, "SGOV": 1.0})
    down = pd.DataFrame({"QQQ": [20.0, 18.0, 16.0, 5.0], "TQQQ": 1.0, "SGOV": 1.0})
    assert strat.target_allocation(_ctx(up)) == {"TQQQ": 1.0}
    assert strat.target_allocation(_ctx(down)) == {"SGOV": 1.0}


def test_sma_switch_rebalances_existing_stack() -> None:
    strat = sma_switch("t", leveraged="TQQQ", cash="SGOV", sma_window=3)
    down = pd.DataFrame({"QQQ": [20.0, 18.0, 16.0, 5.0], "TQQQ": 1.0, "SGOV": 1.0})
    pf = Portfolio()
    pf.buy("TQQQ", 100.0, 1.0)
    converts = strat.rebalance(_ctx(down, pf))
    assert [(c.from_symbol, c.to_symbol) for c in converts] == [("TQQQ", "SGOV")]


def test_drawdown_tilt_redirects_contribution_by_tier() -> None:
    # 52w high 100; current depths select the deepest tier cleared.
    base = [100.0] * 6
    prices_15 = pd.DataFrame({"QQQ": [*base, 84.0]})  # -16% → QLD tier
    prices_25 = pd.DataFrame({"QQQ": [*base, 74.0]})  # -26% → TQQQ tier
    prices_flat = pd.DataFrame({"QQQ": [*base, 99.0]})  # shallow → base
    assert D3_TIERED.target_allocation(_ctx(prices_15)) == {"QLD": 1.0}
    assert D3_TIERED.target_allocation(_ctx(prices_25)) == {"TQQQ": 1.0}
    assert D3_TIERED.target_allocation(_ctx(prices_flat)) == {"QQQ": 1.0}


def test_drawdown_tilt_recovery_exit_converts_leverage_to_base() -> None:
    pf = Portfolio()
    pf.buy("QLD", 100.0, 1.0)
    recovered = pd.DataFrame({"QQQ": [100.0, 80.0, 98.0]})  # within 5% of high → exit
    deep = pd.DataFrame({"QQQ": [100.0, 80.0, 80.0]})  # still down 20% → hold
    assert [c.to_symbol for c in D1_DD15_QLD.rebalance(_ctx(recovered, pf))] == ["QQQ"]
    assert D1_DD15_QLD.rebalance(_ctx(deep, pf)) == []


def test_drawdown_tilt_trend_guard_disables_leverage_below_trend() -> None:
    # Long downtrend: last price below the 200-day (here expanding) SMA → guard forces base.
    prices = pd.DataFrame({"QQQ": [200.0, 180.0, 150.0, 120.0, 90.0, 76.0]})
    guarded = D4_TIERED_GUARD.target_allocation(_ctx(prices))
    unguarded = D3_TIERED.target_allocation(_ctx(prices))
    assert guarded == {"QQQ": 1.0}
    assert unguarded != {"QQQ": 1.0}  # same drawdown would have tilted to leverage


def test_t1_runs_end_to_end_through_engine() -> None:
    idx = pd.bdate_range("2020-01-01", periods=260)
    ramp = pd.Series(range(260), index=idx, dtype=float) + 100.0
    prices = pd.DataFrame({"QQQ": ramp, "TQQQ": ramp, "SGOV": 1.0})
    contribs = monthly_contributions(pd.DatetimeIndex([idx[210], idx[240]]), 1000.0)
    res = run_backtest(prices, contribs, T1_SMA_TQQQ)
    # Uptrend the whole way → contributions go to TQQQ, never SGOV.
    assert "TQQQ" in res.final_positions
    assert res.final_positions.get("SGOV", None) is None or res.final_positions["SGOV"].shares == 0


def test_drawdown_tilt_time_exit_converts_after_hold_period() -> None:
    strat = drawdown_tilt("t", exit="time", hold_months=12, tiers=((0.15, "QLD"),))
    prices = pd.DataFrame({"QQQ": [100.0, 100.0]})
    pf = Portfolio()
    pf.buy("QLD", 100.0, 1.0)
    pf.positions["QLD"].opened = pd.Timestamp("2020-01-31")
    six_mo = AllocationContext(date=pd.Timestamp("2020-07-31"), history=prices, portfolio=pf)
    assert strat.rebalance(six_mo) == []  # held < 12 months → keep running
    one_yr = AllocationContext(date=pd.Timestamp("2021-01-31"), history=prices, portfolio=pf)
    assert [c.to_symbol for c in strat.rebalance(one_yr)] == ["QQQ"]  # 12 months → convert


def test_drawdown_tilt_never_sell_holds_through_recovery() -> None:
    strat = drawdown_tilt("t", exit="never", tiers=((0.15, "QLD"),))
    pf = Portfolio()
    pf.buy("QLD", 100.0, 1.0)
    recovered = pd.DataFrame({"QQQ": [100.0, 80.0, 98.0]})  # default exit would sell here
    assert strat.rebalance(_ctx(recovered, pf)) == []


def test_vix_tilt_routes_contribution_up_the_ladder_by_fear_level() -> None:
    strat = vix_tilt("v", tiers=((25.0, "QLD"), (35.0, "TQQQ")))
    calm = pd.DataFrame({"QQQ": [100.0, 101.0], "VIX": [12.0, 18.0]})  # below first tier
    fear = pd.DataFrame({"QQQ": [100.0, 90.0], "VIX": [20.0, 28.0]})  # ≥25 → QLD
    panic = pd.DataFrame({"QQQ": [100.0, 70.0], "VIX": [30.0, 42.0]})  # ≥35 → TQQQ
    assert strat.target_allocation(_ctx(calm)) == {"QQQ": 1.0}
    assert strat.target_allocation(_ctx(fear)) == {"QLD": 1.0}
    assert strat.target_allocation(_ctx(panic)) == {"TQQQ": 1.0}


def test_vix_tilt_unwinds_leverage_when_fear_subsides() -> None:
    strat = vix_tilt("v", tiers=((25.0, "QLD"),))
    pf = Portfolio()
    pf.buy("QLD", 100.0, 1.0)
    still_afraid = pd.DataFrame({"QQQ": [100.0, 90.0], "VIX": [30.0, 27.0]})  # ≥25 → hold
    calmed = pd.DataFrame({"QQQ": [100.0, 98.0], "VIX": [30.0, 18.0]})  # <25 → exit to base
    assert strat.rebalance(_ctx(still_afraid, pf)) == []
    assert [c.to_symbol for c in strat.rebalance(_ctx(calmed, pf))] == ["QQQ"]


def test_vix_tilt_falls_back_to_base_without_a_vix_column() -> None:
    strat = vix_tilt("v")
    no_vix = pd.DataFrame({"QQQ": [100.0, 90.0]})  # VIX series absent from the panel
    pf = Portfolio()
    pf.buy("QLD", 100.0, 1.0)
    assert strat.target_allocation(_ctx(no_vix)) == {"QQQ": 1.0}
    assert strat.rebalance(_ctx(no_vix, pf)) == []


def test_vix_tilt_trend_guard_blocks_leverage_below_ma() -> None:
    # Short series → the 200-day SMA is just the expanding mean of the supplied points.
    strat = vix_tilt("v", tiers=((25.0, "QLD"),), trend_guard=True)
    fear = [30.0, 32.0, 35.0, 38.0, 45.0]
    down = pd.DataFrame({"QQQ": [200.0, 180.0, 150.0, 120.0, 90.0], "VIX": fear})  # below MA
    up = pd.DataFrame({"QQQ": [90.0, 120.0, 150.0, 180.0, 200.0], "VIX": fear})  # above MA
    assert strat.target_allocation(_ctx(down)) == {"QQQ": 1.0}  # gate wins despite VIX ≥ 25
    assert strat.target_allocation(_ctx(up)) == {"QLD": 1.0}  # uptrend → tilt allowed


def test_vix_tilt_exit_below_guard_actively_de_risks() -> None:
    strat = vix_tilt("v", tiers=((25.0, "QLD"),), trend_guard=True, exit_below_guard=True)
    pf = Portfolio()
    pf.buy("QLD", 100.0, 1.0)
    # VIX still elevated (would normally hold), but QQQ has broken below its MA → force unwind.
    broke_down = pd.DataFrame({"QQQ": [200.0, 180.0, 150.0, 120.0, 90.0], "VIX": [30.0] * 5})
    assert [c.to_symbol for c in strat.rebalance(_ctx(broke_down, pf))] == ["QQQ"]
    # Without the active de-risk flag, the same breach holds the leverage (V2 behaviour).
    blocker = vix_tilt("v2", tiers=((25.0, "QLD"),), trend_guard=True)
    assert blocker.rebalance(_ctx(broke_down, pf)) == []
