"""Per-strategy metric report (spec §9.1-9.4).

``build_report`` is the pure, deterministic core: run every strategy over an
*identical* contribution schedule (§9.1 apples-to-apples) and tabulate the §9
metrics. ``main`` wires it to the DuckDB price lake, reconstructing the leveraged
sleeves (QLD/TQQQ) and a cash proxy (SGOV) so all nine strategies are runnable on
whatever QQQ history exists. Crisis case studies and the block bootstrap (§9.5)
are M6.
"""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from jp_quant.backtest.engine import month_end_trade_dates, monthly_contributions, run_backtest
from jp_quant.backtest.metrics import StrategyMetrics, evaluate
from jp_quant.backtest.strategies import ALL_STRATEGIES
from jp_quant.synthesis import QLD_SPEC, TQQQ_SPEC, compound_to_price, reconstruct_series
from jp_quant.tax import Account

MONTHLY_CONTRIBUTION_JPY = 100_000.0


def build_report(
    prices: pd.DataFrame,
    contributions: pd.Series,
    strategies: list[object] | None = None,
    *,
    base_symbol: str = "QQQ",
    account: Account = Account.SPECIFIED,
    rf_annual: float = 0.0,
) -> pd.DataFrame:
    """One row of §9 metrics per strategy, all sharing ``contributions`` and ``prices``."""
    rows: list[dict[str, object]] = []
    for strat in strategies or ALL_STRATEGIES:
        result = run_backtest(prices, contributions, strat)  # type: ignore[arg-type]
        m: StrategyMetrics = evaluate(
            result,
            contributions,
            name=strat.name,  # type: ignore[attr-defined]
            base_symbol=base_symbol,
            account=account,
            rf_annual=rf_annual,
        )
        rows.append(asdict(m))
    return pd.DataFrame(rows).set_index("name")


# The tradable universe (§8 F2). VIX and other auxiliary series are *not* tradable, so they
# don't drive the common-panel dropna; signal-only series are reattached afterwards.
UNIVERSE = ("QQQ", "QLD", "TQQQ", "SGOV", "IEF")
SIGNAL_SERIES = ("VIX",)  # non-tradable columns kept for strategy signals (e.g. vix_tilt, §4.4a)


def reconstruct_universe(panel: pd.DataFrame, borrow_annual_pct: pd.Series) -> pd.DataFrame:
    """Make the leveraged sleeves and cash continuous over QQQ's full span.

    QLD/TQQQ are synthesized before the real ETF and spliced to actuals (§7). SGOV is
    a *continuous* cash proxy: real SGOV returns where present (2020+), DTB3-compounded
    before — without this the real SGOV inception would truncate the whole panel.
    """
    out = panel.copy()
    qqq_ret = out["QQQ"].pct_change().dropna()
    borrow = borrow_annual_pct.reindex(qqq_ret.index).ffill().bfill().fillna(0.0)
    for spec in (QLD_SPEC, TQQQ_SPEC):
        actual = (
            out[spec.symbol].pct_change() if spec.symbol in out.columns else pd.Series(dtype=float)
        )
        out[spec.symbol] = reconstruct_series(qqq_ret, borrow, actual, spec)

    cash_ret = (borrow / 100.0 / 252.0).reindex(qqq_ret.index)
    if "SGOV" in out.columns:
        cash_ret = out["SGOV"].pct_change().reindex(qqq_ret.index).fillna(cash_ret)
    out["SGOV"] = compound_to_price(cash_ret.fillna(0.0))

    cols = [c for c in UNIVERSE if c in out.columns]
    tradable = out[cols].dropna()
    # Reattach signal-only series (VIX) aligned to the tradable span, ffilled over any gaps —
    # they inform strategies but are never allocated to, so they must not truncate the panel.
    for sig in SIGNAL_SERIES:
        if sig in out.columns:
            tradable[sig] = out[sig].reindex(tradable.index).ffill().bfill()
    return tradable


def load_price_panel(duckdb_path: str) -> pd.DataFrame:
    import duckdb

    con = duckdb.connect(duckdb_path, read_only=True)
    try:
        eq = con.execute(
            "select price_date, symbol, adjusted_close from main.stg_equity_prices"
        ).df()
        # Keep only the latest vintage per date — raw.* is append-only, so re-ingesting
        # stamps a new vintage that would otherwise duplicate every macro date (spec §5.3).
        macro = con.execute(
            "select date, value from raw.macro where series_id = 'DTB3' "
            "qualify row_number() over (partition by cast(date as date) order by vintage desc) = 1"
        ).df()
    finally:
        con.close()
    panel = eq.pivot(index="price_date", columns="symbol", values="adjusted_close").sort_index()
    panel.index = pd.DatetimeIndex(panel.index)
    borrow = pd.Series(macro["value"].to_numpy(dtype=float), index=pd.DatetimeIndex(macro["date"]))
    return reconstruct_universe(panel, borrow.sort_index())


def main() -> None:
    from jp_quant.config import get_paths

    panel = load_price_panel(str(get_paths().duckdb_path))
    schedule = monthly_contributions(month_end_trade_dates(panel), MONTHLY_CONTRIBUTION_JPY)
    report = build_report(panel, schedule)
    pd.set_option("display.float_format", lambda v: f"{v:,.4f}")
    print(report.T.to_string())


if __name__ == "__main__":
    main()
