"""Composable strategy factors (spec §4.5).

A strategy is a point in a factor matrix, built from orthogonal, independently-chosen
components rather than a bespoke class per family:

- **Trigger** — what picks the leveraged sleeve: drawdown tier, VIX tier, or trend.
- **Gate** — an *independent* trend regime (QQQ's 200-day SMA) that can withhold leverage,
  distinct from the trigger's own signal.
- **Exit** — how existing leverage is unwound: recovery band, time, never, VIX-calm, or a
  trend breach (and ``AnyExit`` to combine them).

Two composition *scopes* wire these into the engine's ``Strategy`` protocol:

- :class:`ComposableTilt` — a *contribution* tilt (§4.3): new money follows the trigger
  (subject to the gate); existing holdings are only touched by the exit.
- :class:`ComposableSwitch` — a *full-stack* trend switch (§4.2): the whole portfolio is
  converted to one signalled target.

The ``sma_switch`` / ``drawdown_tilt`` / ``vix_tilt`` factories assemble the common presets;
the catalog in ``strategies`` is just named calls to them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pandas as pd

from jp_quant.backtest.engine import AllocationContext, Convert
from jp_quant.signals import TRADING_DAYS_YEAR, drawdown_from_high, sma

TRADING_DAYS_200D = 200


def _months_held(opened: pd.Timestamp | None, now: pd.Timestamp) -> int:
    """Whole calendar months a position has been open; 0 if its open date is unknown."""
    if opened is None:
        return 0
    return (now.year - opened.year) * 12 + (now.month - opened.month)


def _leveraged(ctx: AllocationContext, base: str) -> list[str]:
    """Symbols held that are not the ``base`` sleeve (the leveraged lots to unwind)."""
    return [s for s, p in ctx.portfolio.positions.items() if s != base and p.shares > 0]


# --- Triggers: choose the sleeve this month's contribution buys -----------------------------
@runtime_checkable
class Trigger(Protocol):
    def chosen(self, ctx: AllocationContext, base: str) -> str: ...


@dataclass(frozen=True)
class DrawdownTrigger:
    """Tier into a leveraged sleeve as QQQ's drawdown from its 52w high deepens (§4.3)."""

    tiers: tuple[tuple[float, str], ...]
    signal_symbol: str = "QQQ"

    def chosen(self, ctx: AllocationContext, base: str) -> str:
        s = ctx.history[self.signal_symbol]
        dd = -float(drawdown_from_high(s, TRADING_DAYS_YEAR).iloc[-1])
        chosen = base
        for thresh, sym in self.tiers:  # ordered shallow→deep; deepest cleared wins
            if dd >= thresh:
                chosen = sym
        return chosen


@dataclass(frozen=True)
class VixTrigger:
    """Tier into a leveraged sleeve as the VIX fear gauge rises (§4.4a). VIX is a signal-only
    series; if absent from the panel the trigger falls back to ``base``."""

    tiers: tuple[tuple[float, str], ...]
    signal_symbol: str = "VIX"

    def chosen(self, ctx: AllocationContext, base: str) -> str:
        if self.signal_symbol not in ctx.history.columns:
            return base
        vix = float(ctx.history[self.signal_symbol].iloc[-1])
        chosen = base
        for level, sym in self.tiers:  # ordered low→high; highest cleared wins
            if vix >= level:
                chosen = sym
        return chosen


@dataclass(frozen=True)
class TrendTrigger:
    """Trend follow (§4.2): ``leveraged`` while the signal is above its SMA, else ``cash``."""

    leveraged: str
    cash: str = "SGOV"
    window: int = TRADING_DAYS_200D
    signal_symbol: str = "QQQ"

    def chosen(self, ctx: AllocationContext, base: str) -> str:
        s = ctx.history[self.signal_symbol]
        above = float(s.iloc[-1]) > float(sma(s, self.window).iloc[-1])
        return self.leveraged if above else self.cash


# --- Gate: an independent trend regime that can withhold leverage ---------------------------
@runtime_checkable
class Gate(Protocol):
    def blocks(self, ctx: AllocationContext) -> bool: ...


class NoGate:
    def blocks(self, ctx: AllocationContext) -> bool:
        return False


NO_GATE = NoGate()


@dataclass(frozen=True)
class TrendGate:
    """Block leverage while ``symbol`` is below its SMA over ``window`` trading days
    (200 ≈ a 200-day trend filter)."""

    window: int
    symbol: str = "QQQ"

    def blocks(self, ctx: AllocationContext) -> bool:
        if self.window <= 0 or self.symbol not in ctx.history.columns:
            return False
        s = ctx.history[self.symbol]
        return float(s.iloc[-1]) < float(sma(s, self.window).iloc[-1])


# --- Exits: how existing leverage is unwound ------------------------------------------------
@runtime_checkable
class Exit(Protocol):
    def converts(self, ctx: AllocationContext, base: str) -> list[Convert]: ...


class NeverExit:
    """Stop adding leverage but let the position run (§4.4)."""

    def converts(self, ctx: AllocationContext, base: str) -> list[Convert]:
        return []


NEVER_EXIT = NeverExit()


@dataclass(frozen=True)
class RecoveryExit:
    """Unwind to ``base`` once QQQ recovers within ``within`` of its 52w high (§4.4 default)."""

    within: float = 0.05
    signal_symbol: str = "QQQ"

    def converts(self, ctx: AllocationContext, base: str) -> list[Convert]:
        s = ctx.history[self.signal_symbol]
        dd = -float(drawdown_from_high(s, TRADING_DAYS_YEAR).iloc[-1])
        if dd >= self.within:  # not yet recovered → hold leverage
            return []
        return [Convert(sym, base) for sym in _leveraged(ctx, base)]


@dataclass(frozen=True)
class TimeExit:
    """Unwind each leveraged lot once it has been held ``months`` months (§4.4)."""

    months: int = 12

    def converts(self, ctx: AllocationContext, base: str) -> list[Convert]:
        return [
            Convert(sym, base)
            for sym in _leveraged(ctx, base)
            if _months_held(ctx.portfolio.positions[sym].opened, ctx.date) >= self.months
        ]


@dataclass(frozen=True)
class VixCalmExit:
    """Unwind to ``base`` once VIX falls below ``level`` (the fear that justified leverage)."""

    level: float = 25.0
    signal_symbol: str = "VIX"

    def converts(self, ctx: AllocationContext, base: str) -> list[Convert]:
        if self.signal_symbol not in ctx.history.columns:
            return []
        if float(ctx.history[self.signal_symbol].iloc[-1]) >= self.level:  # still fearful → hold
            return []
        return [Convert(sym, base) for sym in _leveraged(ctx, base)]


@dataclass(frozen=True)
class TrendBreachExit:
    """Actively de-risk: unwind to ``base`` when ``gate`` says we're below trend."""

    gate: TrendGate

    def converts(self, ctx: AllocationContext, base: str) -> list[Convert]:
        if not self.gate.blocks(ctx):
            return []
        return [Convert(sym, base) for sym in _leveraged(ctx, base)]


@dataclass(frozen=True)
class AnyExit:
    """Unwind a lot if *any* sub-exit calls for it (union of converts)."""

    exits: tuple[Exit, ...]

    def converts(self, ctx: AllocationContext, base: str) -> list[Convert]:
        out: list[Convert] = []
        seen: set[str] = set()
        for sub in self.exits:
            for c in sub.converts(ctx, base):
                if c.from_symbol not in seen:
                    seen.add(c.from_symbol)
                    out.append(c)
        return out


# --- Composition scopes ---------------------------------------------------------------------
@dataclass(frozen=True)
class FixedAllocation:
    """Allocate every contribution to a fixed set of weights; never sell (§4.1)."""

    name: str
    weights: dict[str, float]

    def target_allocation(self, ctx: AllocationContext) -> dict[str, float]:
        return dict(self.weights)

    def rebalance(self, ctx: AllocationContext) -> list[Convert]:
        return []


@dataclass(frozen=True)
class ComposableTilt:
    """Contribution tilt (§4.3): new money follows ``trigger`` unless ``gate`` blocks leverage;
    existing holdings are only converted by ``exit``."""

    name: str
    trigger: Trigger
    exit: Exit = NEVER_EXIT
    base: str = "QQQ"
    gate: Gate = NO_GATE

    def target_allocation(self, ctx: AllocationContext) -> dict[str, float]:
        if self.gate.blocks(ctx):  # below trend → no leverage, regardless of the trigger
            return {self.base: 1.0}
        return {self.trigger.chosen(ctx, self.base): 1.0}

    def rebalance(self, ctx: AllocationContext) -> list[Convert]:
        return self.exit.converts(ctx, self.base)


@dataclass(frozen=True)
class ComposableSwitch:
    """Full-stack trend switch (§4.2): hold one signalled target and convert everything to it."""

    name: str
    trigger: Trigger

    def _target(self, ctx: AllocationContext) -> str:
        return self.trigger.chosen(ctx, "")

    def target_allocation(self, ctx: AllocationContext) -> dict[str, float]:
        return {self._target(ctx): 1.0}

    def rebalance(self, ctx: AllocationContext) -> list[Convert]:
        target = self._target(ctx)
        return [
            Convert(sym, target)
            for sym, pos in ctx.portfolio.positions.items()
            if sym != target and pos.shares > 0
        ]


# --- Preset factories (common cells of the matrix) ------------------------------------------
def sma_switch(
    name: str,
    leveraged: str,
    cash: str = "SGOV",
    sma_window: int = TRADING_DAYS_200D,
    signal_symbol: str = "QQQ",
) -> ComposableSwitch:
    """200-day SMA trend switch (§4.2)."""
    return ComposableSwitch(name, TrendTrigger(leveraged, cash, sma_window, signal_symbol))


def drawdown_tilt(
    name: str,
    tiers: tuple[tuple[float, str], ...] = ((0.15, "QLD"), (0.25, "TQQQ")),
    recover_within: float = 0.05,
    trend_guard: bool = False,
    exit: str = "recovery",
    hold_months: int = 12,
    base: str = "QQQ",
) -> ComposableTilt:
    """Drawdown-triggered tilt (§4.3) with a recovery / time / never exit (§4.4). With
    ``trend_guard`` the tilt is gated by QQQ's 200-day SMA (no levering below trend)."""
    if exit == "never":
        rule: Exit = NEVER_EXIT
    elif exit == "time":
        rule = TimeExit(hold_months)
    else:
        rule = RecoveryExit(recover_within)
    gate: Gate = TrendGate(TRADING_DAYS_200D) if trend_guard else NO_GATE
    return ComposableTilt(name, DrawdownTrigger(tuple(tiers)), rule, base, gate)


def vix_tilt(
    name: str,
    tiers: tuple[tuple[float, str], ...] = ((25.0, "QLD"), (35.0, "TQQQ")),
    exit_vix: float | None = None,
    trend_guard: bool = False,
    exit_below_guard: bool = False,
    base: str = "QQQ",
) -> ComposableTilt:
    """VIX-triggered tilt (§4.4a). With ``trend_guard`` it is gated by QQQ's 200-day SMA;
    ``exit_below_guard`` additionally force-exits leverage on a trend breach."""
    tiers = tuple(tiers)
    calm: Exit = VixCalmExit(exit_vix if exit_vix is not None else tiers[0][0])
    gate: Gate = TrendGate(TRADING_DAYS_200D) if trend_guard else NO_GATE
    if exit_below_guard and trend_guard:
        rule: Exit = AnyExit((calm, TrendBreachExit(TrendGate(TRADING_DAYS_200D))))
    else:
        rule = calm
    return ComposableTilt(name, VixTrigger(tiers), rule, base, gate)
