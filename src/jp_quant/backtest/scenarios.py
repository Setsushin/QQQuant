"""Distribution view (spec §9.5): crisis case studies + stationary block bootstrap.

§9.5 is explicit that the effective sample size is the *number of deep-drawdown
episodes* (~5-6), not the number of months — so the primary lens is per-episode
narratives, and the bootstrap is secondary with a stated caveat.

**Crisis case studies (primary):** each real drawdown episode is replayed with real
trailing history (signals read the full panel up to each trade date; only the
contribution schedule is windowed). Episodes before an ETF's inception lean on
*synthesized* leverage and are flagged (`synthesized`) per §7.4.

**Stationary block bootstrap (secondary):** Politis-Romano resampling of monthly
returns with a geometric block length covering a full drawdown->recovery cycle
(~12-36 months). Caveat: block resampling weakens the autocorrelation /
drawdown-clustering structure these strategies exploit, so it *understates*
path-dependency — never IID-resample (§9.5.2).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from jp_quant.backtest.engine import month_end_trade_dates, monthly_contributions, run_backtest
from jp_quant.backtest.metrics import evaluate, investment_returns
from jp_quant.backtest.report import MONTHLY_CONTRIBUTION_JPY
from jp_quant.tax import Account

TQQQ_INCEPTION = pd.Timestamp("2010-02-01")  # episodes starting earlier use synthesized leverage


@dataclass(frozen=True)
class CrisisEpisode:
    name: str
    start: str
    end: str


CRISIS_EPISODES = [
    CrisisEpisode("dotcom", "2000-03-01", "2002-10-31"),
    CrisisEpisode("gfc", "2007-10-01", "2009-06-30"),
    CrisisEpisode("covid", "2020-02-01", "2020-12-31"),
    CrisisEpisode("rate-shock-2022", "2022-01-01", "2022-12-31"),
]


def crisis_case_studies(
    prices: pd.DataFrame,
    strategies: list[object],
    episodes: list[CrisisEpisode] | None = None,
    *,
    base_symbol: str = "QQQ",
    monthly_amount: float = MONTHLY_CONTRIBUTION_JPY,
    account: Account = Account.SPECIFIED,
    rf_annual: float = 0.0,
) -> pd.DataFrame:
    """One row per (episode, strategy): episode QQQ drawdown + the full §9 metric block.

    Captures entry (start), path (qqq_drawdown / max_drawdown), exit
    (taxable_events_per_year = conversions) and after-tax outcome (cagr_after_tax,
    mwr_after_tax) for a narrative read (§9.5.1)."""
    rows: list[dict[str, object]] = []
    for ep in episodes or CRISIS_EPISODES:
        start, end = pd.Timestamp(ep.start), pd.Timestamp(ep.end)
        if base_symbol not in prices or prices[base_symbol].loc[start:end].empty:
            continue
        base = prices[base_symbol].loc[start:end]
        qqq_drawdown = float((base / base.cummax() - 1.0).min())

        month_ends = month_end_trade_dates(prices.loc[:end])
        dates = month_ends[(month_ends >= start) & (month_ends <= end)]
        if len(dates) < 2:
            continue
        contribs = monthly_contributions(pd.DatetimeIndex(dates), monthly_amount)
        synthesized = start < TQQQ_INCEPTION
        for strat in strategies:
            result = run_backtest(prices, contribs, strat)  # type: ignore[arg-type]
            metrics = evaluate(
                result,
                contribs,
                name=strat.name,  # type: ignore[attr-defined]
                base_symbol=base_symbol,
                account=account,
                rf_annual=rf_annual,
            )
            rows.append(
                {
                    "episode": ep.name,
                    "start": start,
                    "end": end,
                    "qqq_drawdown": qqq_drawdown,
                    "synthesized": synthesized,
                    "strategy": metrics.name,
                    **{k: v for k, v in asdict(metrics).items() if k != "name"},
                }
            )
    return pd.DataFrame(rows)


def stationary_bootstrap_indices(
    n: int, length: int, expected_block: float, rng: np.random.Generator
) -> np.ndarray:
    """Politis-Romano index path: advance contiguously, restart at a uniform draw with
    probability 1/expected_block (geometric block lengths)."""
    p = 1.0 / expected_block
    out = np.empty(length, dtype=int)
    i = int(rng.integers(0, n))
    for t in range(length):
        out[t] = i
        i = int(rng.integers(0, n)) if rng.random() < p else (i + 1) % n
    return out


def bootstrap_equity_percentiles(
    returns: pd.Series,
    *,
    n_paths: int = 1000,
    expected_block: float = 18.0,
    horizon: int | None = None,
    percentiles: tuple[int, ...] = (5, 50, 95),
    seed: int = 0,
) -> pd.DataFrame:
    """Percentile wealth curves across ``n_paths`` stationary-bootstrap resamples of
    ``returns`` (resample monthly returns, §9.5.2). Columns ``p5``/``p50``/``p95``."""
    r = returns.to_numpy(dtype=float)
    n = len(r)
    if n == 0:
        return pd.DataFrame(columns=[f"p{p}" for p in percentiles])
    steps = horizon or n
    rng = np.random.default_rng(seed)
    wealth = np.empty((n_paths, steps))
    for k in range(n_paths):
        idx = stationary_bootstrap_indices(n, steps, expected_block, rng)
        wealth[k] = np.cumprod(1.0 + r[idx])
    pct = np.percentile(wealth, percentiles, axis=0)
    return pd.DataFrame(pct.T, columns=[f"p{p}" for p in percentiles])


def monthly_twr_returns(equity: pd.Series, contributions: pd.Series) -> pd.Series:
    """Compound the daily TWR series (§9.1) into monthly returns for resampling."""
    daily = investment_returns(equity, contributions)
    return (1.0 + daily).resample("ME").prod() - 1.0
