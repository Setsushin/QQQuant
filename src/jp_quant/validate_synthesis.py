"""Live validation of leveraged-ETF synthesis vs the real ETFs (spec §7.3).

Network-dependent (like smoke): fetches QQQ/TQQQ/QLD adjusted closes + the 3M
T-bill, calibrates the financing spread, and reports daily-return correlation +
annualized total-return error over each ETF's real-data overlap.

DoD (M2): corr > 0.99 and |annualized error| < 0.5%/yr. Run: `make validate-synthesis`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pandas as pd

from jp_quant.config import MacroSeries, equity_by_symbol, get_vintage
from jp_quant.ingestion.macro import fetch_fred
from jp_quant.ingestion.yfinance_source import fetch_equity
from jp_quant.synthesis import (
    QLD_SPEC,
    TQQQ_SPEC,
    calibrate_financing_spread,
    evaluate_fit,
    synthetic_daily_returns,
)

DTB3 = MacroSeries("DTB3", "3-Month Treasury Bill rate")

CORR_MIN = 0.99
ANN_ERROR_MAX = 0.005


def _adj_close(symbol: str, vintage: date) -> pd.Series:
    df = fetch_equity(equity_by_symbol(symbol), vintage=vintage)
    return df.set_index("date")["adj_close"].astype(float).sort_index()


def main() -> int:
    vintage = get_vintage()
    qqq_returns = _adj_close("QQQ", vintage).pct_change().dropna()
    borrow = fetch_fred(DTB3, vintage=vintage).set_index("date")["value"].astype(float).sort_index()

    all_pass = True
    for spec in (TQQQ_SPEC, QLD_SPEC):
        actual = _adj_close(spec.symbol, vintage).pct_change().dropna()
        idx = qqq_returns.index.intersection(actual.index)
        underlying, actual = qqq_returns.loc[idx], actual.loc[idx]

        spread = calibrate_financing_spread(underlying, borrow, actual, spec)
        synth = synthetic_daily_returns(underlying, borrow, replace(spec, financing_spread=spread))
        fit = evaluate_fit(synth, actual)

        passed = (
            fit.daily_return_corr > CORR_MIN and abs(fit.annualized_return_error) < ANN_ERROR_MAX
        )
        all_pass = all_pass and passed
        print(
            f"[{'OK' if passed else 'FAIL'}] {spec.symbol} (L={spec.leverage:g}): "
            f"corr={fit.daily_return_corr:.4f}  "
            f"ann_err={fit.annualized_return_error * 100:+.2f}%/yr  "
            f"spread={spread * 100:.2f}%  n={fit.n_obs}"
        )
    print("SYNTHESIS", "PASS" if all_pass else "FAIL")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
