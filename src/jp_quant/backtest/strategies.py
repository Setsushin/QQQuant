"""Strategy catalog (spec §4) — named points in the composable factor matrix.

Every strategy below is assembled from the orthogonal components in
:mod:`jp_quant.backtest.composable` (a base allocation x leverage trigger x trend gate x
exit rule), so the families are not bespoke classes but presets:

- **Baselines (§4.1)** — :class:`FixedAllocation`, never sell.
- **Trend-following (§4.2)** — ``sma_switch``: a full-stack switch into a leveraged sleeve
  above the 200-day SMA, else cash.
- **Drawdown tilt (§4.3-4.4)** — ``drawdown_tilt``: a contribution tilt keyed off QQQ's own
  drawdown, with recovery / time / never exits and an optional 200-day trend gate.
- **VIX tilt (§4.4a)** — ``vix_tilt``: the same contribution-tilt shape keyed off the VIX
  fear gauge, optionally gated by a trend MA (independent of VIX) that can also force-exit.

New combinations are just new factory calls; the data plane (report, walk-forward grid,
serving API) enumerates over ``ALL_STRATEGIES`` and the validation grids.
"""

from __future__ import annotations

from jp_quant.backtest.composable import (
    FixedAllocation,
    drawdown_tilt,
    sma_switch,
    vix_tilt,
)

# Baselines (§4.1) — B1 QQQ-LumpSum = B0 run with a lump_sum_contribution schedule.
B0_QQQ_DCA = FixedAllocation("B0 QQQ-DCA", {"QQQ": 1.0})
B2_TQQQ_DCA = FixedAllocation("B2 TQQQ-DCA", {"TQQQ": 1.0})
B3_60_40_DCA = FixedAllocation("B3 60/40-DCA", {"QQQ": 0.6, "IEF": 0.4})
B4_QLD_DCA = FixedAllocation("B4 QLD-DCA", {"QLD": 1.0})

# Trend-following (§4.2)
T1_SMA_TQQQ = sma_switch("T1 200-SMA-Switch", leveraged="TQQQ")
T2_SMA_QLD = sma_switch("T2 200-SMA-QLD", leveraged="QLD")
T3_SMA_QQQ = sma_switch("T3 200-SMA-QQQ", leveraged="QQQ")

# Drawdown tilt (§4.3)
_DD_TIERS = ((0.15, "QLD"), (0.25, "TQQQ"))
D1_DD15_QLD = drawdown_tilt("D1 Drawdown-15-QLD", tiers=((0.15, "QLD"),))
D2_DD25_TQQQ = drawdown_tilt("D2 Drawdown-25-TQQQ", tiers=((0.25, "TQQQ"),))
D3_TIERED = drawdown_tilt("D3 Tiered", tiers=_DD_TIERS)
D4_TIERED_GUARD = drawdown_tilt("D4 Tiered+200SMA", tiers=_DD_TIERS, trend_guard=True)
# Exit-logic variants on the tiered tilt (§4.4): time-based exit vs. never-sell.
D5_TIERED_TIME = drawdown_tilt("D5 Tiered+TimeExit12", tiers=_DD_TIERS, exit="time", hold_months=12)
D6_TIERED_HOLD = drawdown_tilt("D6 Tiered+NeverSell", tiers=_DD_TIERS, exit="never")

# VIX-triggered leverage tilt (§4.4a): three-tier ladder QQQ → QLD (VIX≥25) → TQQQ (VIX≥35).
_VIX_TIERS = ((25.0, "QLD"), (35.0, "TQQQ"))
V1_VIX_TILT = vix_tilt("V1 VIX-Tilt", tiers=_VIX_TIERS)
# V2: same ladder, gated by the 200-day MA so it won't lever below trend (blocks new tilts only).
V2_VIX_GUARD = vix_tilt("V2 VIX-Tilt+200SMA", tiers=_VIX_TIERS, trend_guard=True)
# V3: like V2 but also actively de-risks to plain QQQ when QQQ breaks below the 200-day MA.
V3_VIX_UPTREND = vix_tilt(
    "V3 VIX-Tilt+200SMA+DeRisk", tiers=_VIX_TIERS, trend_guard=True, exit_below_guard=True
)

ALL_STRATEGIES = [
    B0_QQQ_DCA,
    B2_TQQQ_DCA,
    B3_60_40_DCA,
    B4_QLD_DCA,
    T1_SMA_TQQQ,
    T2_SMA_QLD,
    T3_SMA_QQQ,
    D1_DD15_QLD,
    D2_DD25_TQQQ,
    D3_TIERED,
    D4_TIERED_GUARD,
    D5_TIERED_TIME,
    D6_TIERED_HOLD,
    V1_VIX_TILT,
    V2_VIX_GUARD,
    V3_VIX_UPTREND,
]
