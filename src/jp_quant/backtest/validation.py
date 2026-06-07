"""Walk-forward validation and parameter sweep (spec §4.5, §9.5).

Walk-forward runs each strategy on successive **out-of-sample** test windows while
the strategy still sees real trailing history (signals read ``prices.loc[:ts]``;
only the contribution schedule is windowed), so 200d/52w signals are never computed
on truncated history. The deliverable is *dispersion across windows and across the
full grid* — never a single best cell (§14: report the full parameter grid).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from jp_quant.backtest.composable import drawdown_tilt, sma_switch
from jp_quant.backtest.engine import month_end_trade_dates, monthly_contributions
from jp_quant.backtest.report import MONTHLY_CONTRIBUTION_JPY, build_report
from jp_quant.tax import Account


def trend_grid() -> list[object]:
    """SMA-switch family: leverage sleeve x SMA window (§4.2, §4.5)."""
    return [
        sma_switch(f"T:SMA{window}-{lev}", leveraged=lev, sma_window=window)
        for lev in ("QLD", "TQQQ")
        for window in (150, 200, 250)
    ]


def drawdown_grid() -> list[object]:
    """Drawdown-tilt family: tier set x recovery-exit band x 200-day trend guard (§4.3-4.5)."""
    tier_sets = {
        "15QLD": ((0.15, "QLD"),),
        "25TQQQ": ((0.25, "TQQQ"),),
        "tiered": ((0.15, "QLD"), (0.25, "TQQQ")),
    }
    return [
        drawdown_tilt(
            f"D:{label}-r{int(rec * 100)}{'-g' if guard else ''}",
            tiers=tiers,
            recover_within=rec,
            trend_guard=guard,
        )
        for label, tiers in tier_sets.items()
        for rec in (0.0, 0.05, 0.10)
        for guard in (False, True)
    ]


@dataclass(frozen=True)
class WalkForwardSplit:
    label: str
    train_start: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def make_splits(
    index: pd.Index, n_windows: int = 3, min_train_years: int = 5
) -> list[WalkForwardSplit]:
    """Expanding-train / contiguous-test splits over the price index (§4.5)."""
    idx = pd.DatetimeIndex(index)
    start = pd.Timestamp(idx[0])
    test_begin = start + pd.DateOffset(years=min_train_years)
    bounds = pd.date_range(test_begin, pd.Timestamp(idx[-1]), periods=n_windows + 1)
    return [
        WalkForwardSplit(
            label=f"{bounds[i].year}-{bounds[i + 1].year}",
            train_start=start,
            test_start=pd.Timestamp(bounds[i]),
            test_end=pd.Timestamp(bounds[i + 1]),
        )
        for i in range(n_windows)
    ]


def walk_forward(
    prices: pd.DataFrame,
    splits: list[WalkForwardSplit],
    strategies: list[object],
    *,
    monthly_amount: float = MONTHLY_CONTRIBUTION_JPY,
    account: Account = Account.SPECIFIED,
    rf_annual: float = 0.0,
) -> pd.DataFrame:
    """Long-form (window x strategy) §9 metrics, each computed on its test window only."""
    frames: list[pd.DataFrame] = []
    for sp in splits:
        month_ends = month_end_trade_dates(prices.loc[: sp.test_end])
        dates = month_ends[(month_ends >= sp.test_start) & (month_ends <= sp.test_end)]
        if len(dates) < 2:
            continue
        contribs = monthly_contributions(pd.DatetimeIndex(dates), monthly_amount)
        report = build_report(
            prices, contribs, strategies, account=account, rf_annual=rf_annual
        ).reset_index()
        report.insert(0, "window", sp.label)
        report.insert(1, "test_start", sp.test_start)
        report.insert(2, "test_end", sp.test_end)
        frames.append(report)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def dispersion(walk_forward_result: pd.DataFrame, metric: str = "cagr") -> pd.DataFrame:
    """Out-of-sample spread of ``metric`` per strategy across windows (min/median/max/std)."""
    grouped = walk_forward_result.groupby("name")[metric]
    return pd.DataFrame(
        {
            "min": grouped.min(),
            "median": grouped.median(),
            "max": grouped.max(),
            "std": grouped.std(ddof=0),
            "windows": grouped.count(),
        }
    )
