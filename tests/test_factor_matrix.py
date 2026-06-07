import pytest

from jp_quant.backtest.composable import ComposableSwitch, ComposableTilt, FixedAllocation
from jp_quant.backtest.factor_matrix import (
    AXES,
    Combo,
    build_strategy,
    combo_of,
    invalid_reason,
    is_valid,
    matrix_cells,
    required_series,
    scope_for,
)


def test_200_week_gate_option_is_dropped() -> None:
    assert AXES["gate"] == ("none", "200d")
    assert "200w" not in AXES["gate"]


def test_fixed_allocation_rejects_trigger_gate_exit() -> None:
    assert is_valid(Combo(scope="fixed"))  # plain buy-and-hold
    assert invalid_reason(Combo(scope="fixed", trigger="drawdown")) is not None
    assert invalid_reason(Combo(scope="fixed", exit="recovery")) is not None
    assert invalid_reason(Combo(scope="fixed", gate="200d")) is not None


def test_tilt_needs_trigger_and_exit() -> None:
    assert invalid_reason(Combo(scope="tilt", trigger="none", exit="recovery")) is not None
    assert invalid_reason(Combo(scope="tilt", trigger="drawdown", exit="none")) is not None
    assert is_valid(Combo(scope="tilt", trigger="drawdown", exit="recovery"))
    assert is_valid(Combo(scope="tilt", trigger="vix", exit="vixcalm", gate="200d"))


def test_switch_is_trend_only_with_implicit_exit() -> None:
    assert is_valid(Combo(scope="switch", trigger="trend", ladder="QLD"))
    assert invalid_reason(Combo(scope="switch", trigger="vix", ladder="QLD")) is not None
    breach = Combo(scope="switch", trigger="trend", ladder="QLD", exit="recovery")
    assert invalid_reason(breach) is not None
    # the trend trigger cannot be a contribution tilt
    assert invalid_reason(Combo(scope="tilt", trigger="trend", exit="recovery")) is not None


def test_no_op_axes_are_rejected() -> None:
    # A switch ignores the gate (the trend trigger is the signal) and fixed ignores the ladder
    # (it always buys QQQ) — so those axes must not offer non-default, no-effect cells.
    assert invalid_reason(combo_of("trend", ladder="QLD", gate="200d")) is not None
    assert invalid_reason(combo_of("none", ladder="QLD")) is not None
    assert invalid_reason(combo_of("none", ladder="TQQQ")) is not None
    # The canonical cells stay valid.
    assert is_valid(combo_of("trend", ladder="QLD"))
    assert is_valid(combo_of("none"))


def test_exit_coherence_rules() -> None:
    # VIX-calm exit only with a VIX trigger; trend-breach exit needs a gate.
    assert invalid_reason(Combo(scope="tilt", trigger="drawdown", exit="vixcalm")) is not None
    breach_no_gate = Combo(scope="tilt", trigger="vix", exit="trendbreach", gate="none")
    assert invalid_reason(breach_no_gate) is not None
    assert is_valid(Combo(scope="tilt", trigger="vix", exit="trendbreach", gate="200d"))


def test_required_series_flags_vix() -> None:
    assert required_series(Combo(scope="tilt", trigger="vix", exit="vixcalm")) == frozenset({"VIX"})
    assert required_series(Combo(scope="tilt", trigger="drawdown", exit="recovery")) == frozenset()


def test_unknown_option_is_invalid() -> None:
    assert invalid_reason(Combo(scope="tilt", trigger="drawdown", gate="200w", exit="recovery"))


def test_switch_rejects_tiered_ladder() -> None:
    assert is_valid(combo_of("trend", ladder="QLD"))
    assert invalid_reason(combo_of("trend", ladder="tiered")) is not None


def test_qqq_ladder_is_switch_only() -> None:
    # An unleveraged QQQ "ladder" is the 200-SMA-QQQ trend switch (T3) — valid only for a switch.
    assert is_valid(combo_of("trend", ladder="QQQ"))
    assert isinstance(build_strategy(combo_of("trend", ladder="QQQ"), "T3"), ComposableSwitch)
    # For a contribution tilt, "tilting into QQQ" is no tilt (= buy-and-hold) → rejected.
    assert invalid_reason(combo_of("drawdown", ladder="QQQ", exit="recovery")) is not None
    assert invalid_reason(combo_of("vix", ladder="QQQ", exit="vixcalm")) is not None


def test_scope_is_derived_from_trigger() -> None:
    assert scope_for("none") == "fixed"
    assert scope_for("trend") == "switch"
    assert scope_for("drawdown") == "tilt"
    assert scope_for("vix") == "tilt"


def test_matrix_cells_cover_axes_and_mark_validity() -> None:
    cells = matrix_cells()
    assert len(cells) == 4 * 4 * 2 * 6  # trigger x ladder x gate x exit
    vix_cell = next(c for c in cells if c["trigger"] == "vix" and c["exit"] == "vixcalm")
    assert vix_cell["requires"] == ["VIX"]
    assert any(c["valid"] for c in cells) and any(not c["valid"] for c in cells)


def test_build_strategy_assembles_each_scope() -> None:
    assert isinstance(build_strategy(combo_of("none"), "fixed"), FixedAllocation)
    assert isinstance(build_strategy(combo_of("trend", ladder="TQQQ"), "t"), ComposableSwitch)
    tilt = build_strategy(combo_of("vix", ladder="tiered", gate="200d", exit="trendbreach"), "v")
    assert isinstance(tilt, ComposableTilt)


def test_build_strategy_rejects_invalid_combo() -> None:
    with pytest.raises(ValueError, match="invalid factor combination"):
        build_strategy(combo_of("none", exit="recovery"), "bad")
