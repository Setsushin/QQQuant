from dataclasses import replace

import pandas as pd
import pytest

from jp_quant.synthesis import (
    TQQQ_SPEC,
    TRADING_DAYS,
    LeverageSpec,
    calibrate_financing_spread,
    compound_to_price,
    evaluate_fit,
    reconstruct_series,
    synthetic_daily_returns,
)


def _idx(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-01", periods=n)


def test_formula_matches_hand_computation() -> None:
    idx = _idx(1)
    u = pd.Series([0.01], index=idx)
    borrow = pd.Series([5.0], index=idx)  # 5% p.a.
    out = synthetic_daily_returns(u, borrow, TQQQ_SPEC)
    expected = 3 * 0.01 - 2 * 0.05 / TRADING_DAYS - 0.0095 / TRADING_DAYS
    assert out.iloc[0] == pytest.approx(expected)


def test_volatility_decay_on_roundtrip() -> None:
    idx = _idx(2)
    u = pd.Series([0.10, -1 / 11], index=idx)  # underlying returns exactly to start
    borrow = pd.Series([0.0, 0.0], index=idx)
    spec = LeverageSpec("X", 2.0, fee_annual=0.0, financing_spread=0.0)
    assert compound_to_price(u).iloc[-1] == pytest.approx(1.0)
    # 2x of a flat round-trip ends below start purely from path/volatility decay
    synth = synthetic_daily_returns(u, borrow, spec)
    assert compound_to_price(synth).iloc[-1] < 1.0


def test_evaluate_fit_identical_series() -> None:
    idx = _idx(20)
    r = pd.Series([0.002 * (1 if i % 2 else -1) for i in range(20)], index=idx)
    fit = evaluate_fit(r, r)
    assert fit.daily_return_corr == pytest.approx(1.0)
    assert fit.annualized_return_error == pytest.approx(0.0, abs=1e-12)
    assert fit.n_obs == 20


def test_calibrate_recovers_known_spread() -> None:
    n = 300
    idx = _idx(n)
    u = pd.Series([0.004 if i % 2 else -0.003 for i in range(n)], index=idx)
    borrow = pd.Series([5.0] * n, index=idx)
    base = LeverageSpec("X", 3.0, fee_annual=0.0095, financing_spread=0.0)

    actual = synthetic_daily_returns(u, borrow, replace(base, financing_spread=0.012))
    recovered = calibrate_financing_spread(u, borrow, actual, base)

    assert recovered == pytest.approx(0.012, abs=1e-3)
    fitted = synthetic_daily_returns(u, borrow, replace(base, financing_spread=recovered))
    assert abs(evaluate_fit(fitted, actual).annualized_return_error) < 1e-4


def test_reconstruct_uses_actual_where_present_else_synthetic() -> None:
    n = 100
    idx = _idx(n)
    u = pd.Series([0.003 if i % 2 else -0.002 for i in range(n)], index=idx)
    borrow = pd.Series([0.0] * n, index=idx)  # zero borrow/fee isolates synth = 2x underlying
    spec = LeverageSpec("X", 2.0, fee_annual=0.0, financing_spread=0.0)
    # actual exists only in the second half
    actual = pd.Series(
        [float("nan")] * 50 + [0.01 if i % 2 else -0.008 for i in range(50)], index=idx
    )

    rec = reconstruct_series(u, borrow, actual, spec, calibrate=False)
    rec_ret = rec.pct_change()

    assert len(rec) == n
    # second half follows the real ETF returns
    assert rec_ret.iloc[60] == pytest.approx(actual.iloc[60])
    # first half is purely synthetic (2x of underlying, no borrow/fee here)
    assert rec_ret.iloc[2] == pytest.approx(2 * u.iloc[2])
