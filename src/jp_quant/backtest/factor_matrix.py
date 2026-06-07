"""Factor matrix, validity rules, and combo→strategy builder (spec §4.5).

The composable strategy space (:mod:`jp_quant.backtest.composable`) is a product of
orthogonal axes. This module is the single source of truth for the *selectable options* per
axis, the rules that mark a combination meaningless (so the matrix UI can grey out invalid
cells and disable options whose data series are absent), and :func:`build_strategy` which
assembles a runnable strategy from a chosen cell.

``invalid_reason`` / ``required_series`` are pure predicates (no pandas, no backtest run) —
trivially serialisable to the front end. The 200-week gate option was intentionally dropped:
the only trend gate is QQQ's 200-day SMA.
"""

from __future__ import annotations

from dataclasses import dataclass

from jp_quant.backtest.composable import (
    NEVER_EXIT,
    NO_GATE,
    TRADING_DAYS_200D,
    ComposableSwitch,
    ComposableTilt,
    DrawdownTrigger,
    Exit,
    FixedAllocation,
    Gate,
    RecoveryExit,
    TimeExit,
    TrendBreachExit,
    TrendGate,
    TrendTrigger,
    Trigger,
    VixCalmExit,
    VixTrigger,
)
from jp_quant.backtest.engine import Strategy

# Selectable option ids per axis. Keep these in sync with the composable factories.
AXES: dict[str, tuple[str, ...]] = {
    "scope": ("fixed", "tilt", "switch"),
    "trigger": ("none", "drawdown", "vix", "trend"),
    # QQQ = unleveraged; meaningful only for a switch (= T3 200-SMA-QQQ). A QQQ "tilt" is no
    # tilt (it would equal buy-and-hold), and a fixed allocation already holds QQQ.
    "ladder": ("QQQ", "QLD", "TQQQ", "tiered"),
    "gate": ("none", "200d"),  # 200-week intentionally removed
    "exit": ("none", "recovery", "time", "never", "vixcalm", "trendbreach"),
}

# Leverage ladders per trigger family (the sleeve(s) a cleared tier buys).
_DRAWDOWN_LADDERS: dict[str, tuple[tuple[float, str], ...]] = {
    "QLD": ((0.15, "QLD"),),
    "TQQQ": ((0.25, "TQQQ"),),
    "tiered": ((0.15, "QLD"), (0.25, "TQQQ")),
}
_VIX_LADDERS: dict[str, tuple[tuple[float, str], ...]] = {
    "QLD": ((25.0, "QLD"),),
    "TQQQ": ((25.0, "TQQQ"),),
    "tiered": ((25.0, "QLD"), (35.0, "TQQQ")),
}


def scope_for(trigger: str) -> str:
    """The composition scope implied by a trigger: none→fixed, trend→switch, else→tilt."""
    return {"none": "fixed", "trend": "switch"}.get(trigger, "tilt")


@dataclass(frozen=True)
class Combo:
    """One cell of the factor matrix (option ids from :data:`AXES`)."""

    scope: str
    trigger: str = "none"
    ladder: str = "tiered"
    gate: str = "none"
    exit: str = "none"

    def as_dict(self) -> dict[str, str]:
        return {
            "scope": self.scope,
            "trigger": self.trigger,
            "ladder": self.ladder,
            "gate": self.gate,
            "exit": self.exit,
        }


def combo_of(trigger: str, ladder: str = "tiered", gate: str = "none", exit: str = "none") -> Combo:
    """Build a Combo with the scope implied by ``trigger`` (the UI only picks the other axes)."""
    return Combo(scope_for(trigger), trigger, ladder, gate, exit)


def _unknown_option(combo: Combo) -> str | None:
    for axis, value in combo.as_dict().items():
        if value not in AXES[axis]:
            return f"{axis}={value!r} is not a valid option"
    return None


def invalid_reason(combo: Combo) -> str | None:
    """Why ``combo`` is meaningless, or ``None`` if it is a valid strategy to build.

    Encodes the structural rules of the composition (§4.1-4.4a): e.g. a fixed allocation has
    no trigger/gate/exit, a full-stack switch's exit is implicit, and a contribution tilt
    needs both a leverage trigger and an exit rule."""
    if (bad := _unknown_option(combo)) is not None:
        return bad

    if combo.scope == "fixed":
        if combo.trigger != "none" or combo.gate != "none" or combo.exit != "none":
            return "fixed allocation buys and holds — it has no trigger, gate, or exit"
        if combo.ladder != "tiered":  # build() always holds QQQ; the ladder axis does not apply
            return "fixed allocation is plain buy-and-hold QQQ — the leverage ladder does not apply"
        return None

    if combo.trigger == "none":
        return "a leverage trigger is required outside fixed allocation"

    if combo.scope == "switch":
        if combo.trigger != "trend":
            return "a full-stack switch is driven by the trend trigger only"
        if combo.ladder == "tiered":
            return "a full-stack switch holds a single leveraged sleeve, not a tiered ladder"
        if combo.gate != "none":  # build() ignores it — the trend trigger IS the 200-day signal
            return "a full-stack switch has no separate gate — its trend trigger is the signal"
        if combo.exit != "none":
            return "switch exit is implicit (it flips on the trend signal); no separate exit"
        return None

    # scope == "tilt"
    if combo.trigger == "trend":
        return "the trend trigger is a full-stack switch, not a contribution tilt"
    if combo.ladder == "QQQ":
        return "a tilt into QQQ is no tilt — that is plain buy-and-hold (use the 'none' trigger)"
    if combo.exit == "none":
        return "a contribution tilt needs an exit rule"
    if combo.exit == "vixcalm" and combo.trigger != "vix":
        return "the VIX-calm exit only applies to a VIX trigger"
    if combo.exit == "trendbreach" and combo.gate == "none":
        return "the trend-breach exit needs a trend gate to define the breach"
    return None


def is_valid(combo: Combo) -> bool:
    return invalid_reason(combo) is None


def required_series(combo: Combo) -> frozenset[str]:
    """Signal-only series a combo needs in the panel (so the UI can disable VIX cells when the
    VIX series is absent)."""
    needs: set[str] = set()
    if combo.trigger == "vix" or combo.exit == "vixcalm":
        needs.add("VIX")
    return frozenset(needs)


def matrix_cells() -> list[dict[str, object]]:
    """Every (trigger, ladder, gate, exit) cell with its derived scope, validity, and required
    series — the payload the matrix UI consumes to render selectable vs. greyed options."""
    cells: list[dict[str, object]] = []
    for trigger in AXES["trigger"]:
        for ladder in AXES["ladder"]:
            for gate in AXES["gate"]:
                for exit in AXES["exit"]:
                    combo = combo_of(trigger, ladder, gate, exit)
                    cells.append(
                        {
                            **combo.as_dict(),
                            "valid": is_valid(combo),
                            "reason": invalid_reason(combo),
                            "requires": sorted(required_series(combo)),
                        }
                    )
    return cells


def _exit_rule(exit_id: str, gate: Gate) -> Exit:
    if exit_id == "time":
        return TimeExit()
    if exit_id == "never":
        return NEVER_EXIT
    if exit_id == "vixcalm":
        return VixCalmExit()
    if exit_id == "trendbreach":
        assert isinstance(gate, TrendGate)  # invalid_reason guarantees a gate is present
        return TrendBreachExit(gate)
    return RecoveryExit()


def build_strategy(combo: Combo, name: str) -> Strategy:
    """Assemble a runnable strategy from a *valid* matrix cell (raises on an invalid combo)."""
    if (reason := invalid_reason(combo)) is not None:
        raise ValueError(f"invalid factor combination: {reason}")
    if combo.scope == "fixed":
        return FixedAllocation(name, {"QQQ": 1.0})
    if combo.scope == "switch":
        return ComposableSwitch(name, TrendTrigger(leveraged=combo.ladder))
    gate: Gate = TrendGate(TRADING_DAYS_200D) if combo.gate == "200d" else NO_GATE
    trigger: Trigger = (
        DrawdownTrigger(_DRAWDOWN_LADDERS[combo.ladder])
        if combo.trigger == "drawdown"
        else VixTrigger(_VIX_LADDERS[combo.ladder])
    )
    return ComposableTilt(name, trigger, _exit_rule(combo.exit, gate), "QQQ", gate)

