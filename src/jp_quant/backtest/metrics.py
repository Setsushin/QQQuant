"""Evaluation metrics (spec §9), computed on a backtest result.

Returns are **time-weighted** (TWR): contribution inflows are stripped out of the
daily equity change so the curve reflects investment return, not deposits (§9.1).
The headline MWR/IRR comes from the dated cash flows (§9.1). All accounting is in
JPY, so any non-zero risk-free rate passed to Sharpe/Sortino must be a JPY rate
(§9.3); the default is 0, appropriate for the near-zero JPY rates over the period.

§9.5 (crisis case studies, block bootstrap) is out of scope here — that is M6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from jp_quant.backtest.engine import BacktestResult
from jp_quant.tax import Account, after_tax_on_liquidation, money_weighted_return

TRADING_DAYS = 252
DAYS_PER_MONTH = 30.44
ROLL_12M = 252
ROLL_36M = 756


def investment_returns(equity: pd.Series, contributions: pd.Series) -> pd.Series:
    """Daily TWR series: price-driven change with contribution inflows removed.

    On a contribution day the close-price purchase adds cash ``c`` to NAV with no
    price gain, so the true return is ``(V_t - c_t) / V_{t-1} - 1`` (conversions are
    value-neutral and need no adjustment)."""
    c = contributions.groupby(level=0).sum().reindex(equity.index).fillna(0.0)
    r = (equity - c) / equity.shift(1) - 1.0
    return r.iloc[1:].dropna()


def wealth_index(returns: pd.Series, anchor: pd.Timestamp | None = None) -> pd.Series:
    """Cumulative TWR wealth. ``anchor`` (the date one step before the first return,
    valued 1.0) makes ``wealth[-1] / wealth[0]`` equal the true total growth over the
    full span — without it the first return's step would be excluded from the horizon."""
    w = (1.0 + returns).cumprod()
    if anchor is None:
        return w
    anchored: pd.Series = pd.concat([pd.Series([1.0], index=pd.DatetimeIndex([anchor])), w])
    return anchored


def cagr(wealth: pd.Series) -> float:
    if len(wealth) < 2:
        return 0.0
    growth = float(wealth.iloc[-1] / wealth.iloc[0])
    years = (pd.Timestamp(wealth.index[-1]) - pd.Timestamp(wealth.index[0])).days / 365.25
    if years <= 0 or growth <= 0:
        return 0.0
    return float(growth ** (1.0 / years) - 1.0)


def annualized_vol(returns: pd.Series) -> float:
    return float(returns.std(ddof=1)) * math.sqrt(TRADING_DAYS) if len(returns) > 1 else 0.0


def sharpe(returns: pd.Series, rf_annual: float = 0.0) -> float:
    sd = returns.std(ddof=1)
    if len(returns) < 2 or sd == 0:
        return 0.0
    excess = returns - rf_annual / TRADING_DAYS
    return float(excess.mean() / sd) * math.sqrt(TRADING_DAYS)


def sortino(returns: pd.Series, rf_annual: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    excess = returns - rf_annual / TRADING_DAYS
    downside = excess[excess < 0]
    dd = float(np.sqrt((downside**2).mean())) if len(downside) else 0.0
    if dd == 0:
        return 0.0
    return float(excess.mean() / dd) * math.sqrt(TRADING_DAYS)


def drawdown_curve(wealth: pd.Series) -> pd.Series:
    return wealth / wealth.cummax() - 1.0


def max_drawdown(wealth: pd.Series) -> float:
    return float(drawdown_curve(wealth).min()) if len(wealth) else 0.0


def max_drawdown_duration_months(wealth: pd.Series) -> float:
    """Peak-to-recovery span (months) of the deepest drawdown; to series end if unrecovered."""
    dd = drawdown_curve(wealth)
    if dd.empty or dd.min() >= -1e-9:
        return 0.0
    trough = dd.idxmin()
    pre = dd[dd.index <= trough]
    peak_date = pre[pre >= -1e-9].index[-1]
    post = wealth[wealth.index >= trough]
    recovered = post[post >= float(wealth.loc[peak_date])]
    end = recovered.index[0] if len(recovered) else wealth.index[-1]
    return (pd.Timestamp(end) - pd.Timestamp(peak_date)).days / DAYS_PER_MONTH


def longest_underwater_months(wealth: pd.Series) -> float:
    """Longest consecutive span (months) spent below a prior peak."""
    dd = drawdown_curve(wealth)
    under = (dd < -1e-9).to_numpy()
    idx = wealth.index
    longest = 0.0
    start: pd.Timestamp | None = None
    for i, u in enumerate(under):
        if u and start is None:
            start = pd.Timestamp(idx[i - 1]) if i > 0 else pd.Timestamp(idx[i])
        elif not u and start is not None:
            longest = max(longest, (pd.Timestamp(idx[i]) - start).days)
            start = None
    if start is not None:
        longest = max(longest, (pd.Timestamp(idx[-1]) - start).days)
    return longest / DAYS_PER_MONTH


def worst_rolling_return(wealth: pd.Series, window_days: int) -> float:
    if len(wealth) <= window_days:
        return float(wealth.iloc[-1] / wealth.iloc[0] - 1.0) if len(wealth) else 0.0
    roll = wealth.pct_change(window_days).dropna()
    return float(roll.min()) if len(roll) else 0.0


@dataclass(frozen=True)
class StrategyMetrics:
    name: str
    # returns (§9.1)
    cagr: float
    cagr_after_tax: float
    total_return: float
    twr: float
    mwr: float
    mwr_after_tax: float
    # risk (§9.2)
    ann_vol: float
    max_drawdown: float
    max_dd_duration_months: float
    longest_underwater_months: float
    worst_rolling_12m: float
    worst_rolling_36m: float
    # risk-adjusted (§9.3)
    sharpe: float
    sortino: float
    calmar: float
    # behavioral (§9.4)
    tax_drag: float
    taxable_events_per_year: float
    pct_months_deviation: float


def _behavioral(
    result: BacktestResult, contributions: pd.Series, base_symbol: str, years: float
) -> tuple[float, float]:
    """(taxable conversion events per year, % of contribution months that deviate from base)."""
    months = pd.PeriodIndex(pd.DatetimeIndex(contributions.index), freq="M").unique()
    trades = result.trades
    if trades.empty or len(months) == 0:
        return 0.0, 0.0
    sells = trades[(trades["kind"] == "convert") & (trades["shares"] < 0)]
    events_per_year = len(sells) / years if years > 0 else 0.0

    t = trades.assign(month=pd.PeriodIndex(pd.DatetimeIndex(trades["date"]), freq="M"))
    deviating: set[pd.Period] = set()
    for month, g in t.groupby("month"):
        converted = (g["kind"] == "convert").any()
        contrib = g[g["kind"] == "contribution"]
        non_base = (contrib["symbol"] != base_symbol).any()
        if converted or non_base:
            deviating.add(month)  # type: ignore[arg-type]
    return events_per_year, len(deviating) / len(months)


def evaluate(
    result: BacktestResult,
    contributions: pd.Series,
    *,
    name: str | None = None,
    base_symbol: str = "QQQ",
    account: Account = Account.SPECIFIED,
    rf_annual: float = 0.0,
) -> StrategyMetrics:
    """Full §9 metric block for one backtest. After-tax assumes terminal liquidation (§6)."""
    equity = result.equity_curve
    returns = investment_returns(equity, contributions)
    anchor = pd.Timestamp(equity.index[0]) if len(equity) else None
    wealth = wealth_index(returns, anchor)

    twr = float(wealth.iloc[-1] / wealth.iloc[0] - 1.0) if len(wealth) else 0.0
    cg = cagr(wealth)
    mdd = max_drawdown(wealth)
    years = (
        (pd.Timestamp(wealth.index[-1]) - pd.Timestamp(wealth.index[0])).days / 365.25
        if len(wealth) > 1
        else 0.0
    )

    cost = sum(p.cost_basis for p in result.final_positions.values())
    atl = after_tax_on_liquidation(result.final_value, cost, account)
    terminal_dates = pd.DatetimeIndex(contributions.index)
    contrib_cf = [
        (d, -float(a)) for d, a in zip(terminal_dates, contributions.to_numpy(), strict=True)
    ]
    last = pd.Timestamp(equity.index[-1])
    mwr = money_weighted_return([*contrib_cf, (last, result.final_value)])
    mwr_at = money_weighted_return([*contrib_cf, (last, atl.aftertax_terminal_jpy)])

    # after-tax CAGR: scale terminal wealth by the after-tax/pre-tax ratio, same horizon
    ratio = atl.aftertax_terminal_jpy / result.final_value if result.final_value else 1.0
    cg_at = ((1.0 + cg) ** years * ratio) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    events_per_year, pct_dev = _behavioral(result, contributions, base_symbol, years)

    return StrategyMetrics(
        name=name or result.trades.attrs.get("name", "strategy"),
        cagr=cg,
        cagr_after_tax=cg_at,
        total_return=float(result.final_value / result.total_contributed - 1.0)
        if result.total_contributed
        else 0.0,
        twr=twr,
        mwr=mwr,
        mwr_after_tax=mwr_at,
        ann_vol=annualized_vol(returns),
        max_drawdown=mdd,
        max_dd_duration_months=max_drawdown_duration_months(wealth),
        longest_underwater_months=longest_underwater_months(wealth),
        worst_rolling_12m=worst_rolling_return(wealth, ROLL_12M),
        worst_rolling_36m=worst_rolling_return(wealth, ROLL_36M),
        sharpe=sharpe(returns, rf_annual),
        sortino=sortino(returns, rf_annual),
        calmar=cg / abs(mdd) if mdd < 0 else 0.0,
        tax_drag=cg - cg_at,
        taxable_events_per_year=events_per_year,
        pct_months_deviation=pct_dev,
    )
