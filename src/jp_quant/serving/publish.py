"""Publish modeled results + current signals to the serving store (spec §5.3, §10).

The product plane reads these tables over its API; **no quant logic crosses the
seam** — everything here is already-computed output. The spec names Postgres as the
serving store, but the sink is kept behind ``write_serving_tables`` so the default
is a zero-ops DuckDB serving database (the analytical engine already in the repo);
swapping in Postgres is a connection change once the product plane (P1) consumes it.

Tables (schema ``serving``):
- ``strategy_metrics``       full-period §9 metrics per strategy
- ``strategy_equity``        monthly equity + drawdown per (strategy, date) — UI drill-downs
- ``walk_forward``           out-of-sample metrics per (window, strategy) over the grid
- ``crisis_case_studies``    per (episode, strategy) narrative rows (§9.5.1)
- ``bootstrap_percentiles``  p5/p50/p95 wealth curves per strategy (§9.5.2)
- ``current_signal``         each strategy's recommended allocation for the next buy
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from jp_quant.backtest.engine import (
    AllocationContext,
    Portfolio,
    month_end_trade_dates,
    monthly_contributions,
    run_backtest,
)
from jp_quant.backtest.report import MONTHLY_CONTRIBUTION_JPY, build_report
from jp_quant.backtest.scenarios import (
    bootstrap_equity_percentiles,
    crisis_case_studies,
    monthly_twr_returns,
)
from jp_quant.backtest.strategies import ALL_STRATEGIES
from jp_quant.backtest.validation import drawdown_grid, make_splits, trend_grid, walk_forward
from jp_quant.signals import TRADING_DAYS_YEAR, drawdown_from_high, sma
from jp_quant.tax import Account


def current_signals(
    prices: pd.DataFrame, strategies: list[object], *, base_symbol: str = "QQQ"
) -> pd.DataFrame:
    """Each strategy's target allocation for the *next* contribution given latest data."""
    as_of = pd.Timestamp(prices.index[-1])
    ctx = AllocationContext(date=as_of, history=prices, portfolio=Portfolio())
    base = prices[base_symbol]
    qqq_drawdown = float(drawdown_from_high(base, TRADING_DAYS_YEAR).iloc[-1])
    above_200dma = bool(base.iloc[-1] > sma(base, 200).iloc[-1])

    rows: list[dict[str, object]] = []
    for strat in strategies:
        alloc = strat.target_allocation(ctx)  # type: ignore[attr-defined]
        target = max(alloc, key=lambda s: alloc[s])
        rows.append(
            {
                "strategy": strat.name,  # type: ignore[attr-defined]
                "as_of": as_of,
                "target_symbol": target,
                "target_weight": float(alloc[target]),
                "allocation": json.dumps(alloc),
                "qqq_drawdown_52w": qqq_drawdown,
                "qqq_above_200dma": above_200dma,
            }
        )
    return pd.DataFrame(rows)


def _equity_curves_table(
    prices: pd.DataFrame, contributions: pd.Series, strategies: list[object]
) -> pd.DataFrame:
    """Monthly equity + running drawdown per strategy.

    Backs the Comparison-row drill-down: the UI doesn't need daily resolution, and
    month-end is consistent with how §9 metrics are reported.
    """
    frames: list[pd.DataFrame] = []
    for strat in strategies:
        result = run_backtest(prices, contributions, strat)  # type: ignore[arg-type]
        monthly = result.equity_curve.resample("ME").last().dropna()
        running_max = monthly.cummax()
        drawdown = monthly / running_max - 1.0
        frame = pd.DataFrame(
            {
                "strategy": strat.name,  # type: ignore[attr-defined]
                "date": monthly.index,
                "equity": monthly.to_numpy(dtype=float),
                "drawdown": drawdown.to_numpy(dtype=float),
            }
        )
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _bootstrap_table(
    prices: pd.DataFrame, contributions: pd.Series, strategies: list[object], *, n_paths: int
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for strat in strategies:
        result = run_backtest(prices, contributions, strat)  # type: ignore[arg-type]
        monthly = monthly_twr_returns(result.equity_curve, contributions)
        pctiles = bootstrap_equity_percentiles(monthly, n_paths=n_paths)
        if pctiles.empty:
            continue
        pctiles = pctiles.reset_index(names="step")
        pctiles.insert(0, "strategy", strat.name)  # type: ignore[attr-defined]
        frames.append(pctiles)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def build_serving_tables(
    prices: pd.DataFrame,
    *,
    strategies: list[object] | None = None,
    grid: list[object] | None = None,
    monthly_amount: float = MONTHLY_CONTRIBUTION_JPY,
    n_windows: int = 3,
    bootstrap_paths: int = 1000,
    account: Account = Account.SPECIFIED,
    rf_annual: float = 0.0,
) -> dict[str, pd.DataFrame]:
    headline = strategies if strategies is not None else list(ALL_STRATEGIES)
    full_grid = grid if grid is not None else [*ALL_STRATEGIES, *trend_grid(), *drawdown_grid()]

    contribs = monthly_contributions(month_end_trade_dates(prices), monthly_amount)
    metrics = build_report(prices, contribs, headline, account=account, rf_annual=rf_annual)
    splits = make_splits(prices.index, n_windows=n_windows)
    return {
        "strategy_metrics": metrics.reset_index(),
        "strategy_equity": _equity_curves_table(prices, contribs, headline),
        "walk_forward": walk_forward(
            prices,
            splits,
            full_grid,
            monthly_amount=monthly_amount,
            account=account,
            rf_annual=rf_annual,
        ),
        "crisis_case_studies": crisis_case_studies(
            prices, headline, monthly_amount=monthly_amount, account=account, rf_annual=rf_annual
        ),
        "bootstrap_percentiles": _bootstrap_table(
            prices, contribs, headline, n_paths=bootstrap_paths
        ),
        "current_signal": current_signals(prices, headline),
    }


def write_serving_tables(
    tables: dict[str, pd.DataFrame], duckdb_path: str, *, schema: str = "serving"
) -> None:
    import duckdb

    Path(duckdb_path).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(duckdb_path)
    try:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        for name, df in tables.items():
            con.register("tmp_df", df)
            con.execute(f"CREATE OR REPLACE TABLE {schema}.{name} AS SELECT * FROM tmp_df")
            con.unregister("tmp_df")
    finally:
        con.close()


def publish(prices: pd.DataFrame, duckdb_path: str, **kwargs: object) -> dict[str, pd.DataFrame]:
    tables = build_serving_tables(prices, **kwargs)  # type: ignore[arg-type]
    write_serving_tables(tables, duckdb_path)
    return tables


def main() -> None:
    from jp_quant.backtest.report import load_price_panel
    from jp_quant.config import get_paths

    paths = get_paths()
    panel = load_price_panel(str(paths.duckdb_path))
    # file stem must not equal the schema name, else DuckDB's catalog/schema ref is ambiguous
    out = str(paths.data_dir / "serving_store.duckdb")
    tables = publish(panel, out)
    for name, df in tables.items():
        print(f"serving.{name}: {len(df)} rows")
    print(f"published -> {out}")


if __name__ == "__main__":
    main()
