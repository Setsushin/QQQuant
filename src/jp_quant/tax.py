"""Japan tax engine (spec §6) — a standalone library, no backtest dependency.

特定口座 taxes realized gains at 20.315%, withheld at sale, on a weighted-average
cost basis (総平均法に準ずる方法, §6.2). All accounting is in JPY: because a position's
JPY cost basis is fixed at purchase-time FX and proceeds use sale-time FX, the FX
gain is embedded in the realized JPY gain (§6.3). `fx_attribution` decomposes a gain
into underlying / FX / cross components for reporting.

`TaxLedger` models the 特定口座 源泉徴収あり flow over time: tax is withheld on each
realized gain, gains and losses net *within* a calendar year (損益通算, so a later loss
refunds earlier-withheld tax), and a year's *net* loss carries forward up to 3 years
(繰越控除) to offset later gains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import pandas as pd

TAX_RATE_SPECIFIED = 0.20315
LOSS_CARRYFORWARD_YEARS = 3  # 上場株式等の譲渡損失の繰越控除 (§6)


class Account(StrEnum):
    SPECIFIED = "特定口座"  # 源泉徴収あり, 20.315%
    NISA_GROWTH = "新NISA成長投資枠"  # 0%


def tax_rate(account: Account) -> float:
    return TAX_RATE_SPECIFIED if account == Account.SPECIFIED else 0.0


def withholding_tax(realized_gain_jpy: float, account: Account) -> float:
    """Tax withheld on a single realized gain in isolation (no netting/carry-forward)."""
    return tax_rate(account) * max(realized_gain_jpy, 0.0)


@dataclass
class TaxLedger:
    """Stateful 特定口座 tax accounting over a chronological stream of realized P/L (§6).

    Feed events in date order via :meth:`realize`; it returns the *tax cash flow* at that
    moment (``> 0`` withheld, ``< 0`` refunded). Within a calendar year gains and losses
    net (損益通算): the running tax withheld tracks ``rate * max(0, year_net)``, so a loss
    that follows gains refunds the over-withheld tax. A year that closes net-negative banks
    its loss as carry-forward, usable against the next ``carry_years`` years' gains
    (繰越控除); when a later gain is offset, the tax withheld on the offset portion is
    refunded. Call :meth:`close` once at the end to settle the final open year.
    """

    account: Account
    carry_years: int = LOSS_CARRYFORWARD_YEARS
    _year: int | None = field(default=None, init=False)
    _year_net: float = field(default=0.0, init=False)
    _year_withheld: float = field(default=0.0, init=False)
    _carry: list[list[float]] = field(default_factory=list, init=False)
    """Banked net losses as ``[incurred_year, remaining]`` pairs, oldest first."""

    @property
    def rate(self) -> float:
        return tax_rate(self.account)

    @property
    def carryforward_balance(self) -> float:
        """Unused banked losses still available to offset future gains."""
        return sum(remaining for _, remaining in self._carry)

    def realize(self, year: int, pl_jpy: float) -> float:
        """Record a realized gain/loss in calendar ``year``; return the tax cash flow now."""
        refund = self._advance_to(year)
        self._year_net += pl_jpy
        new_withheld = self.rate * max(0.0, self._year_net)
        delta = new_withheld - self._year_withheld
        self._year_withheld = new_withheld
        return delta - refund

    def close(self) -> float:
        """Settle the final open year (carry-forward may refund tax on an offset gain)."""
        if self._year is None:
            return 0.0
        return -self._settle_year(self._year)

    def _advance_to(self, year: int) -> float:
        if self._year is None:
            self._year = year
            return 0.0
        refund = 0.0
        while self._year < year:
            refund += self._settle_year(self._year)
            self._year += 1
            self._year_net = 0.0
            self._year_withheld = 0.0
        return refund

    def _settle_year(self, y: int) -> float:
        """Close year ``y``: expire stale carry, then bank a net loss or apply carry to a
        net gain. Returns the tax refunded by carry-forward offset (``>= 0``)."""
        self._carry = [b for b in self._carry if b[0] >= y - self.carry_years]
        if self._year_net < 0:
            self._carry.append([y, -self._year_net])
            return 0.0
        offset, target = 0.0, self._year_net
        for bucket in self._carry:
            if target <= 0:
                break
            used = min(bucket[1], target)
            bucket[1] -= used
            target -= used
            offset += used
        self._carry = [b for b in self._carry if b[1] > 1e-9]
        return self.rate * offset


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
