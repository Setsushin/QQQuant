"""Japan tax engine (spec §6) — a standalone library, no backtest dependency.

特定口座 taxes realized gains at 20.315%, withheld at sale, on a weighted-average
cost basis (総平均法に準ずる方法, §6.2). All accounting is in JPY: because a position's
JPY cost basis is fixed at purchase-time FX and proceeds use sale-time FX, the FX
gain is embedded in the realized JPY gain (§6.3). `fx_attribution` decomposes a gain
into underlying / FX / cross components for reporting. Loss carry-forward (3y) is a
stretch goal and is not modeled.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

TAX_RATE_SPECIFIED = 0.20315


class Account(StrEnum):
    SPECIFIED = "特定口座"  # 源泉徴収あり, 20.315%
    NISA_GROWTH = "新NISA成長投資枠"  # 0%


def tax_rate(account: Account) -> float:
    return TAX_RATE_SPECIFIED if account == Account.SPECIFIED else 0.0


def withholding_tax(realized_gain_jpy: float, account: Account) -> float:
    """Tax withheld on a realized gain. Losses incur no tax (no carry-forward modeled)."""
    return tax_rate(account) * max(realized_gain_jpy, 0.0)


@dataclass(frozen=True)
class AfterTaxResult:
    pretax_terminal_jpy: float
    realized_gain_jpy: float
    tax_jpy: float

    @property
    def aftertax_terminal_jpy(self) -> float:
        return self.pretax_terminal_jpy - self.tax_jpy


def after_tax_on_liquidation(
    terminal_value_jpy: float, cost_basis_jpy: float, account: Account
) -> AfterTaxResult:
    """After-tax terminal value if the whole portfolio is liquidated at the end."""
    gain = terminal_value_jpy - cost_basis_jpy
    return AfterTaxResult(terminal_value_jpy, gain, withholding_tax(gain, account))


@dataclass(frozen=True)
class FxAttribution:
    underlying_jpy: float
    fx_jpy: float
    cross_jpy: float

    @property
    def total_jpy(self) -> float:
        return self.underlying_jpy + self.fx_jpy + self.cross_jpy


def fx_attribution(
    shares: float, price0_usd: float, fx0: float, price1_usd: float, fx1: float
) -> FxAttribution:
    """Split a JPY gain into underlying / FX / cross terms (sums to the total JPY gain)."""
    d_price = price1_usd - price0_usd
    d_fx = fx1 - fx0
    return FxAttribution(
        underlying_jpy=shares * fx0 * d_price,
        fx_jpy=shares * price0_usd * d_fx,
        cross_jpy=shares * d_price * d_fx,
    )


def money_weighted_return(cashflows: list[tuple[pd.Timestamp, float]]) -> float:
    """Annualized IRR (money-weighted return) of dated cash flows (contributions
    negative, terminal value positive). Returns NaN if no sign change is bracketed.
    """
    if not cashflows:
        return 0.0
    t0 = min(d for d, _ in cashflows)

    def npv(rate: float) -> float:
        return float(
            sum(cf / (1.0 + rate) ** ((pd.Timestamp(d) - t0).days / 365.25) for d, cf in cashflows)
        )

    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < 1e-9:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0
