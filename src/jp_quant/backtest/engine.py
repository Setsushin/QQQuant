"""Monthly-cadence backtest engine with weighted-average cost-basis tracking (spec §8).

Prices are **adjusted (total-return) closes**, so dividend reinvestment is already
baked in (F6). Trades execute at each contribution date's close. Position cost basis
uses the weighted-average method (総平均法に準ずる方法, §6.2) — the realized-gain hook
the Japan tax engine (M4) will consume.

Every trade pays a proportional commission (§F5) of ``DEFAULT_COMMISSION_RATE`` on its
notional — charged on contribution buys and on *both* legs of a conversion. It is the
engine default, so every comparison call site (report, equity curves, bootstrap) prices
the same friction; pass ``commission_rate=0.0`` to recover the frictionless mechanics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

DEFAULT_COMMISSION_RATE = 0.001
"""Per-trade commission as a fraction of notional (0.1%) — the comparison default (§F5)."""

_FLAT = 1e-12  # share count at or below which a position counts as closed (for opened tracking)


@dataclass
class Position:
    shares: float = 0.0
    cost_basis: float = 0.0  # total acquisition cost in base currency
    opened: pd.Timestamp | None = None  # date the position was last (re)opened from flat

    @property
    def avg_cost(self) -> float:
        return self.cost_basis / self.shares if self.shares else 0.0


@dataclass
class Portfolio:
    positions: dict[str, Position] = field(default_factory=dict)

    def buy(self, symbol: str, amount: float, price: float, commission: float = 0.0) -> float:
        """Buy ``amount`` of base currency worth at ``price``; returns shares acquired.

        ``commission`` (買付手数料) buys no shares but is part of the acquisition cost
        (取得費, §6.2), so the full ``amount`` is capitalised into the cost basis."""
        shares = (amount - commission) / price
        pos = self.positions.setdefault(symbol, Position())
        pos.shares += shares
        pos.cost_basis += amount
        return shares

    def sell(self, symbol: str, shares: float, price: float, commission: float = 0.0) -> float:
        """Sell ``shares`` at ``price``; returns realized gain (weighted-average basis).

        ``commission`` (譲渡費用) is deductible from the gain (§6)."""
        pos = self.positions[symbol]
        avg = pos.avg_cost
        realized = shares * (price - avg) - commission
        pos.shares -= shares
        pos.cost_basis -= shares * avg
        return realized


@dataclass(frozen=True)
class AllocationContext:
    date: pd.Timestamp
    history: pd.DataFrame
    """Adjusted prices up to and including ``date`` (no look-ahead beyond this row)."""
    portfolio: Portfolio


@dataclass(frozen=True)
class Convert:
    """Rebalance action: sell ``fraction`` of ``from_symbol``, buy ``to_symbol`` with proceeds."""

    from_symbol: str
    to_symbol: str
    fraction: float = 1.0


class Strategy(Protocol):
    @property
    def name(self) -> str: ...

    def target_allocation(self, ctx: AllocationContext) -> dict[str, float]:
        """Weights (summing to ~1) for *this month's contribution* across symbols."""
        ...

    def rebalance(self, ctx: AllocationContext) -> list[Convert]:
        """Conversions of existing holdings (e.g. exit leverage on recovery, §4.4)."""
        ...


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.Series
    trades: pd.DataFrame
    final_positions: dict[str, Position]
    total_contributed: float
    realized_gains: pd.Series
    """Realized gain (base ccy) per date from conversions; taxed at sale (§6)."""

    @property
    def final_value(self) -> float:
        return float(self.equity_curve.iloc[-1]) if len(self.equity_curve) else 0.0


def month_end_trade_dates(prices: pd.DataFrame) -> pd.DatetimeIndex:
    """The last available trading day of each calendar month in ``prices``."""
    idx = pd.DatetimeIndex(prices.index)
    last = pd.Series(idx, index=idx).groupby(idx.to_period("M")).last()
    return pd.DatetimeIndex(last.to_numpy())


def monthly_contributions(trade_dates: pd.DatetimeIndex, amount: float) -> pd.Series:
    return pd.Series(amount, index=trade_dates, dtype=float)


def lump_sum_contribution(date: pd.Timestamp, amount: float) -> pd.Series:
    return pd.Series([amount], index=pd.DatetimeIndex([date]), dtype=float)


def run_backtest(
    prices: pd.DataFrame,
    contributions: pd.Series,
    strategy: Strategy,
    commission_rate: float = DEFAULT_COMMISSION_RATE,
) -> BacktestResult:
    """Run ``strategy`` over ``prices`` (daily adjusted closes) given a contribution schedule.

    ``commission_rate`` is charged on every trade's notional (§F5); pass ``0.0`` for the
    frictionless mechanics. Deterministic (F8). Returns a daily mark-to-market equity
    curve, trade log, and final positions.
    """
    prices = prices.sort_index()
    portfolio = Portfolio()
    trade_log: list[dict[str, object]] = []
    realized_records: list[tuple[pd.Timestamp, float]] = []
    shares_snapshots: dict[pd.Timestamp, dict[str, float]] = {}

    contribs = contributions.sort_index()
    contrib_dates = pd.DatetimeIndex(contribs.index)
    for ts, cash_in in zip(contrib_dates, contribs.to_numpy(), strict=True):
        row = prices.loc[:ts].iloc[-1]
        ctx = AllocationContext(date=ts, history=prices.loc[:ts], portfolio=portfolio)

        # 1) rebalance existing holdings — conversions realize gains (taxed at sale, §6).
        #    Both legs pay commission: sell the source, then buy the target with net proceeds.
        for action in strategy.rebalance(ctx):
            pos = portfolio.positions.get(action.from_symbol)
            if pos is None or pos.shares <= 0:
                continue
            shares = pos.shares * action.fraction
            price_from, price_to = float(row[action.from_symbol]), float(row[action.to_symbol])
            gross = shares * price_from
            sell_fee = gross * commission_rate
            realized_records.append(
                (ts, portfolio.sell(action.from_symbol, shares, price_from, commission=sell_fee))
            )
            if pos.shares <= _FLAT:  # source fully exited → its holding clock resets
                pos.opened = None
            to_pos = portfolio.positions.get(action.to_symbol)
            to_was_flat = to_pos is None or to_pos.shares <= _FLAT
            proceeds = gross - sell_fee
            buy_fee = proceeds * commission_rate
            bought = portfolio.buy(action.to_symbol, proceeds, price_to, commission=buy_fee)
            if to_was_flat:
                portfolio.positions[action.to_symbol].opened = ts
            trade_log.append(
                {
                    "date": ts,
                    "symbol": action.from_symbol,
                    "shares": -shares,
                    "price": price_from,
                    "amount": -gross,
                    "commission": sell_fee,
                    "kind": "convert",
                }
            )
            trade_log.append(
                {
                    "date": ts,
                    "symbol": action.to_symbol,
                    "shares": bought,
                    "price": price_to,
                    "amount": proceeds,
                    "commission": buy_fee,
                    "kind": "convert",
                }
            )

        # 2) allocate this month's contribution
        for symbol, weight in strategy.target_allocation(ctx).items():
            amount = float(cash_in) * weight
            if amount <= 0:
                continue
            price = float(row[symbol])
            fee = amount * commission_rate
            existing = portfolio.positions.get(symbol)
            was_flat = existing is None or existing.shares <= _FLAT
            shares = portfolio.buy(symbol, amount, price, commission=fee)
            if was_flat:
                portfolio.positions[symbol].opened = ts
            trade_log.append(
                {
                    "date": ts,
                    "symbol": symbol,
                    "shares": shares,
                    "price": price,
                    "amount": amount,
                    "commission": fee,
                    "kind": "contribution",
                }
            )
        shares_snapshots[ts] = {s: p.shares for s, p in portfolio.positions.items()}

    first_trade = contrib_dates.min()
    snapshots = pd.DataFrame.from_dict(shares_snapshots, orient="index")
    held = snapshots.reindex(prices.index).ffill().fillna(0.0)
    equity = (held * prices[held.columns]).sum(axis=1)
    equity = equity[equity.index >= first_trade]

    if realized_records:
        gains = pd.Series(
            [g for _, g in realized_records],
            index=pd.DatetimeIndex([d for d, _ in realized_records]),
        )
        realized = gains.groupby(level=0).sum()
    else:
        realized = pd.Series(dtype=float)

    return BacktestResult(
        equity_curve=equity,
        trades=pd.DataFrame(trade_log),
        final_positions=dict(portfolio.positions),
        total_contributed=float(contributions.sum()),
        realized_gains=realized,
    )
