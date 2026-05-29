"""Synthesize pre-inception leveraged-ETF daily returns (spec §7).

Daily leveraged return ~= ``L*r_u - (L-1)*(borrow+spread)/252 - fee/252``, applied
and compounded daily, so volatility decay emerges naturally from the path. Used to
reconstruct QLD/TQQQ before their inception from QQQ total returns + a short rate.

All functions here are pure (no IO) so the formula is unit-tested offline; live
validation against the real ETFs lives in the validation entrypoint.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass(frozen=True)
class LeverageSpec:
    symbol: str
    leverage: float
    fee_annual: float
    """Expense ratio (fraction/yr); parameterized, verify per spec §7.2."""
    financing_spread: float = 0.0
    """Spread over the borrow rate (fraction/yr), calibrated in validation."""


QLD_SPEC = LeverageSpec("QLD", 2.0, 0.0095)
TQQQ_SPEC = LeverageSpec("TQQQ", 3.0, 0.0095)


@dataclass(frozen=True)
class SynthesisFit:
    daily_return_corr: float
    annualized_return_error: float
    """Synthesized CAGR minus actual CAGR over the overlap (signed)."""
    n_obs: int


def synthetic_daily_returns(
    underlying_returns: pd.Series,
    borrow_rate_annual_pct: pd.Series,
    spec: LeverageSpec,
) -> pd.Series:
    """Daily synthetic leveraged returns aligned to ``underlying_returns.index``.

    ``borrow_rate_annual_pct`` follows FRED convention (percent per annum, e.g. 5.24).
    """
    r_u = underlying_returns.astype(float)
    borrow = borrow_rate_annual_pct.reindex(r_u.index).ffill().bfill().astype(float) / 100.0
    daily_borrow = (spec.leverage - 1.0) * (borrow + spec.financing_spread) / TRADING_DAYS
    daily_fee = spec.fee_annual / TRADING_DAYS
    return spec.leverage * r_u - daily_borrow - daily_fee


def compound_to_price(returns: pd.Series, *, start_price: float = 1.0) -> pd.Series:
    """Compound a daily-return series into a price/total-return index."""
    return start_price * (1.0 + returns.astype(float)).cumprod()


def evaluate_fit(synth_returns: pd.Series, actual_returns: pd.Series) -> SynthesisFit:
    """Daily-return correlation and annualized total-return error on the overlap."""
    df = pd.concat([synth_returns.rename("s"), actual_returns.rename("a")], axis=1).dropna()
    corr = float(df["s"].corr(df["a"]))
    years = len(df) / TRADING_DAYS
    gross_s = float(np.prod((1.0 + df["s"]).to_numpy(dtype=float)))
    gross_a = float(np.prod((1.0 + df["a"]).to_numpy(dtype=float)))
    s_cagr = gross_s ** (1.0 / years) - 1.0
    a_cagr = gross_a ** (1.0 / years) - 1.0
    return SynthesisFit(
        daily_return_corr=corr, annualized_return_error=s_cagr - a_cagr, n_obs=len(df)
    )


def calibrate_financing_spread(
    underlying_returns: pd.Series,
    borrow_rate_annual_pct: pd.Series,
    actual_returns: pd.Series,
    spec: LeverageSpec,
    *,
    lo: float = 0.0,
    hi: float = 0.05,
    iters: int = 40,
) -> float:
    """Find the financing spread that drives the annualized return error toward zero.

    The error is monotonically decreasing in the spread (more financing cost → lower
    synthetic return), so we bisect. If even a zero spread already undershoots actual,
    return ``lo`` (a negative spread is not physically meaningful here).
    """

    def err(spread: float) -> float:
        synth = synthetic_daily_returns(
            underlying_returns, borrow_rate_annual_pct, replace(spec, financing_spread=spread)
        )
        return evaluate_fit(synth, actual_returns).annualized_return_error

    if err(lo) <= 0:
        return lo
    for _ in range(iters):
        mid = (lo + hi) / 2.0
        if err(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def reconstruct_series(
    underlying_returns: pd.Series,
    borrow_rate_annual_pct: pd.Series,
    actual_returns: pd.Series,
    spec: LeverageSpec,
    *,
    calibrate: bool = True,
    start_price: float = 1.0,
) -> pd.Series:
    """A continuous total-return price index: actual returns where the real ETF
    exists, synthetic returns (optionally calibrated to the overlap) before that.
    This is the full-history series downstream backtests consume.
    """
    fitted = spec
    overlap = underlying_returns.index.intersection(actual_returns.dropna().index)
    if calibrate and len(overlap) > 30:
        spread = calibrate_financing_spread(
            underlying_returns.loc[overlap],
            borrow_rate_annual_pct,
            actual_returns.loc[overlap],
            spec,
        )
        fitted = replace(spec, financing_spread=spread)
    synth = synthetic_daily_returns(underlying_returns, borrow_rate_annual_pct, fitted)
    combined = actual_returns.reindex(underlying_returns.index).fillna(synth)
    return compound_to_price(combined, start_price=start_price)
