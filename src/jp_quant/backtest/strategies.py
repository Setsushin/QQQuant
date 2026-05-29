"""Strategy definitions (spec §4).

Two capital pools act independently (§4 capital model):
- **This month's contribution** — routed by ``target_allocation``.
- **Existing holdings** — only touched by ``rebalance`` (conversions).

Baselines (§4.1) never rebalance. Trend-following (§4.2) is a classic full-stack
switch, so it rebalances *all* holdings to the signalled target. Drawdown tilt
(§4.3) only redirects new contributions and converts leveraged lots back to QQQ on
recovery (§4.4 default exit) — it never rebalances the base stack.
"""

from __future__ import annotations

from dataclasses import dataclass

from jp_quant.backtest.engine import AllocationContext, Convert
from jp_quant.signals import TRADING_DAYS_200W, TRADING_DAYS_YEAR, drawdown_from_high, sma


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
class SmaSwitch:
    """200-day SMA trend switch (§4.2): full stack in ``leveraged`` when the signal is
    above its SMA, else in ``cash``. Both the contribution and existing holdings follow."""

    name: str
    leveraged: str
    cash: str = "SGOV"
    signal_symbol: str = "QQQ"
    sma_window: int = 200

    def _target(self, ctx: AllocationContext) -> str:
        s = ctx.history[self.signal_symbol]
        above = float(s.iloc[-1]) > float(sma(s, self.sma_window).iloc[-1])
        return self.leveraged if above else self.cash

    def target_allocation(self, ctx: AllocationContext) -> dict[str, float]:
        return {self._target(ctx): 1.0}

    def rebalance(self, ctx: AllocationContext) -> list[Convert]:
        target = self._target(ctx)
        return [
            Convert(sym, target)
            for sym, pos in ctx.portfolio.positions.items()
            if sym != target and pos.shares > 0
        ]


@dataclass(frozen=True)
class DrawdownTilt:
    """Drawdown-triggered leverage tilt (§4.3). Redirects this month's contribution to a
    leveraged sleeve once QQQ's drawdown from its 52w high clears a tier; reverts leveraged
    lots to ``base`` when QQQ recovers within ``recover_within`` of the high (§4.4)."""

    name: str
    base: str = "QQQ"
    tiers: tuple[tuple[float, str], ...] = ((0.15, "QLD"), (0.25, "TQQQ"))
    recover_within: float = 0.05
    guard_200w: bool = False
    signal_symbol: str = "QQQ"

    def _drawdown(self, ctx: AllocationContext) -> float:
        """Drawdown magnitude (>= 0) of the signal from its trailing 52w high."""
        s = ctx.history[self.signal_symbol]
        return -float(drawdown_from_high(s, TRADING_DAYS_YEAR).iloc[-1])

    def _below_200w(self, ctx: AllocationContext) -> bool:
        s = ctx.history[self.signal_symbol]
        return float(s.iloc[-1]) < float(sma(s, TRADING_DAYS_200W).iloc[-1])

    def target_allocation(self, ctx: AllocationContext) -> dict[str, float]:
        if self.guard_200w and self._below_200w(ctx):
            return {self.base: 1.0}
        dd = self._drawdown(ctx)
        chosen = self.base
        for thresh, sym in self.tiers:  # tiers ordered shallow→deep; deepest wins
            if dd >= thresh:
                chosen = sym
        return {chosen: 1.0}

    def rebalance(self, ctx: AllocationContext) -> list[Convert]:
        if self._drawdown(ctx) >= self.recover_within:
            return []
        return [
            Convert(sym, self.base)
            for sym, pos in ctx.portfolio.positions.items()
            if sym != self.base and pos.shares > 0
        ]


# Baselines (§4.1) — B1 QQQ-LumpSum = B0 run with a lump_sum_contribution schedule.
B0_QQQ_DCA = FixedAllocation("B0 QQQ-DCA", {"QQQ": 1.0})
B2_TQQQ_DCA = FixedAllocation("B2 TQQQ-DCA", {"TQQQ": 1.0})
B3_60_40_DCA = FixedAllocation("B3 60/40-DCA", {"QQQ": 0.6, "IEF": 0.4})

# Trend-following (§4.2)
T1_SMA_TQQQ = SmaSwitch("T1 200-SMA-Switch", leveraged="TQQQ")
T2_SMA_QLD = SmaSwitch("T2 200-SMA-QLD", leveraged="QLD")

# Drawdown tilt (§4.3)
D1_DD15_QLD = DrawdownTilt("D1 Drawdown-15-QLD", tiers=((0.15, "QLD"),))
D2_DD25_TQQQ = DrawdownTilt("D2 Drawdown-25-TQQQ", tiers=((0.25, "TQQQ"),))
D3_TIERED = DrawdownTilt("D3 Tiered", tiers=((0.15, "QLD"), (0.25, "TQQQ")))
D4_TIERED_GUARD = DrawdownTilt(
    "D4 Tiered+200WMA", tiers=((0.15, "QLD"), (0.25, "TQQQ")), guard_200w=True
)

ALL_STRATEGIES = [
    B0_QQQ_DCA,
    B2_TQQQ_DCA,
    B3_60_40_DCA,
    T1_SMA_TQQQ,
    T2_SMA_QLD,
    D1_DD15_QLD,
    D2_DD25_TQQQ,
    D3_TIERED,
    D4_TIERED_GUARD,
]
